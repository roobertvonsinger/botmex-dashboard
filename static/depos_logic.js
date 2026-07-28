/* depos_logic.js — Lógica pura del modal de depósitos v8 (C1).
   Sin DOM: testeable con `node --test`. UMD-lite: browser global `DeposLogic` + module.exports. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.DeposLogic = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // La UI impone las reglas: 1 cuenta + reps>1 = programado; 1 (o 0) cuenta + reps=1 = único; varias = multi.
  // `forced` ('auto') gana a todo: modo auto = el sistema elige cuentas y montos (Task F).
  function deriveMode(nAccounts, reps, forced) {
    if (forced === 'auto') return 'auto';
    if (nAccounts > 1) return 'multi';
    return reps > 1 ? 'scheduled' : 'single';
  }

  function presetsForMode(mode) {
    if (mode === 'auto') return {
      presets: [150], manual: false, repsVisible: false,
      note: 'El sistema selecciona cuentas y montos automáticamente',
      cardsOnly: true,
    };
    if (mode === 'multi') {
      // Tope real del backend = DEP_MAX_PER_TXN $499 (deposits.py:1641). $1000
      // daba HTTP 400 SIEMPRE (preset roto). 490 = monto alto dentro del cap.
      // Forzar 3DS de verdad (>499) requiere subir el cap = decisión operacional de Robert.
      return {
        presets: [10, 50, 490], manual: false, repsVisible: false,
        note: 'Montos fijos para varias cuentas · $490 = monto alto (tope $499)',
      };
    }
    // single + scheduled comparten controles (1 cuenta)
    return {
      presets: [10, 50, 150, 300, 490], manual: true, repsVisible: true,
      note: 'Toca un monto o escríbelo · ($10 a $499)',
    };
  }

  // Mapeo fase backend -> escena v8. Un *_retry SIEMPRE muestra la escena retry.
  const _SCENE = {
    login_start: 'login', login_done: 'login', login_reused: 'login',
    gateway_begin: 'form', gateway_begin_done: 'form',
    gateway_submit: 'processing', gateway_submit_done: 'processing',
    gateway_check: 'processing', gateway_check_done: 'processing',
    implicit_3ds_detected: 'processing',
    done: 'done',
  };
  function mapPhaseToScene(name) {
    if (typeof name === 'string' && name.endsWith('_retry')) return 'retry';
    return _SCENE[name] || 'login';
  }

  const _PCT = {
    login_start: 14, login_done: 14, login_reused: 14,
    gateway_begin: 40, gateway_begin_done: 40,
    gateway_submit: 70, gateway_submit_done: 70,
    gateway_check: 82, gateway_check_done: 82, implicit_3ds_detected: 82,
    done: 100,
  };
  // null = la fase no mueve el % (ej. un retry mantiene el progreso actual).
  function phaseToPct(name) {
    if (typeof name === 'string' && name.endsWith('_retry')) return null;
    return name in _PCT ? _PCT[name] : null;
  }

  // Valida pipe de tarjeta. Devuelve null si OK, o string de error (semántica de app.js:3896).
  // Soporta NNNN|MMYY|CVV (3 partes) y NNNN|MM|YY|CVV (4 partes).
  function validatePipe(s) {
    if (!s) return 'Formato: numero|MM|AAAA|CVV';
    const parts = s.replace(/\s/g, '').split('|').filter(Boolean);
    if (parts.length === 3) {
      const [num, exp, cvv] = parts;
      if (!/^\d{13,19}$/.test(num)) return 'Número de tarjeta inválido';
      if (!/^(0[1-9]|1[0-2])\/?(\d{2}|\d{4})$/.test(exp)) return 'Vencimiento inválido';
      if (!/^\d{3,4}$/.test(cvv)) return 'CVV inválido';
      return null;
    }
    if (parts.length === 4) {
      const [num, mm, yy, cvv] = parts;
      if (!/^\d{13,19}$/.test(num)) return 'Número de tarjeta inválido';
      if (!/^(0?[1-9]|1[0-2])$/.test(mm)) return 'Mes inválido';
      if (!/^\d{2,4}$/.test(yy)) return 'Año inválido';
      if (!/^\d{3,4}$/.test(cvv)) return 'CVV inválido';
      return null;
    }
    return 'Formato: numero|MM|AAAA|CVV';
  }

  // Parte el combo en el PRIMER ':' (la password puede contener ':').
  function parseCombo(s) {
    if (typeof s !== 'string') return null;
    const i = s.indexOf(':');
    if (i < 0) return null;
    return { email: s.slice(0, i), password: s.slice(i + 1) };
  }

  function fmtMoney(n) {
    const v = Number(n) || 0;
    return '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // ¿el resultado es un rechazo REAL de BetMexico (visible al operador, L2) o un error
  // NUESTRO de infraestructura (invisible/humanizado, L3)?
  function isRealRejection(code) {
    return /BANK_REJECTED|3DS|INSUF|EXPIRED|AUTOEXCLUS|KYC|LOGIN_DENIED|PENDING_NOT_APPLIED|CARD_LOCKED/.test((code || '').toUpperCase());
  }
  // Mensaje humano para el operador — NUNCA expone el result_code crudo (L3).
  function humanError(code) {
    const c = (code || '').toUpperCase();
    if (c.indexOf('BANK_REJECTED') >= 0) return 'Tarjeta rechazada por el banco';
    if (c.indexOf('3DS') >= 0) return 'Requiere verificación 3DS';
    if (c.indexOf('INSUF') >= 0) return 'Fondos insuficientes';
    if (c.indexOf('EXPIRED') >= 0) return 'Tarjeta vencida';
    if (c.indexOf('AUTOEXCLUS') >= 0) return 'Cuenta autoexcluida';
    if (c.indexOf('KYC') >= 0) return 'Cuenta requiere KYC';
    if (c.indexOf('LOGIN_DENIED') >= 0) return 'Credenciales inválidas';
    if (c.indexOf('CARD_LOCKED') >= 0) return 'Tarjeta ya aprobada en otra cuenta — bloqueada';
    return 'No se pudo completar, intenta de nuevo'; // error nuestro: humanizado, sin tripas
  }

  // Formato CANÓNICO ÚNICO de la UI: NNNN|MM|YYYY|CVV (año 4 dígitos, sin /).
  // Normaliza cualquier pipe (3 o 4 partes, año 2 o 4 díg) a ese formato.
  function canonicalPipe(s) {
    const parts = String(s || '').replace(/\s/g, '').split('|').filter(Boolean);
    if (parts.length < 3) return s; // no es un pipe; devolver tal cual
    let num, exp, cvv;
    if (parts.length >= 4) { num = parts[0]; exp = parts[1] + parts[2]; cvv = parts[3]; }
    else { num = parts[0]; exp = parts[1]; cvv = parts[2]; }
    const nd = num.replace(/\D/g, ''), ed = exp.replace(/\D/g, ''), cd = cvv.replace(/\D/g, '');
    let mm, yyyy;
    if (ed.length >= 6) { mm = ed.slice(0, 2); yyyy = ed.slice(2, 6); }
    else if (ed.length >= 4) { mm = ed.slice(0, 2); yyyy = '20' + ed.slice(2, 4); }
    else { mm = ed.slice(0, 2).padStart(2, '0'); yyyy = '????'; }
    return nd + '|' + mm + '|' + yyyy + '|' + cd;
  }

  return { deriveMode, presetsForMode, mapPhaseToScene, phaseToPct, validatePipe, parseCombo, fmtMoney, isRealRejection, humanError, canonicalPipe };
});
