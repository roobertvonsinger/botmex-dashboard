/* depos_logic.js — Lógica pura del modal de depósitos v8 (C1).
   Sin DOM: testeable con `node --test`. UMD-lite: browser global `DeposLogic` + module.exports. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.DeposLogic = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // La UI impone las reglas: 1 cuenta + reps>1 = programado; 1 (o 0) cuenta + reps=1 = único; varias = multi.
  function deriveMode(nAccounts, reps) {
    if (nAccounts > 1) return 'multi';
    return reps > 1 ? 'scheduled' : 'single';
  }

  function presetsForMode(mode) {
    if (mode === 'multi') {
      return {
        presets: [10, 50, 1000], manual: false, repsVisible: false,
        note: 'Montos fijos para varias cuentas · $1000 fuerza 3DS',
      };
    }
    // single + scheduled comparten controles (1 cuenta)
    return {
      presets: [100], manual: true, repsVisible: true,
      note: '$100 o escribe el monto · ($10 a $499)',
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
    if (!s) return 'Formato: numero|MMYY|CVV';
    const parts = s.replace(/\s/g, '').split('|').filter(Boolean);
    if (parts.length === 3) {
      const [num, exp, cvv] = parts;
      if (!/^\d{13,19}$/.test(num)) return 'Número de tarjeta inválido';
      if (!/^(0[1-9]|1[0-2])\/?(\d{2}|\d{4})$/.test(exp)) return 'Vencimiento inválido (MMYY)';
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
    return 'Formato: numero|MMYY|CVV';
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

  return { deriveMode, presetsForMode, mapPhaseToScene, phaseToPct, validatePipe, parseCombo, fmtMoney };
});
