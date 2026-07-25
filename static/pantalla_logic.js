(function (root) {
  function splitTransactions(movs) {
    const list = Array.isArray(movs) ? movs : [];
    return list.reduce((acc, m) => {
      if (m && m.source === 'dashboard') acc.botmexico.push(m);
      else acc.betmexico.push(m);
      return acc;
    }, { botmexico: [], betmexico: [] });
  }

  const MX_STATES = [
    'Aguascalientes', 'Baja California', 'Baja California Sur', 'Campeche', 'Chiapas',
    'Chihuahua', 'Ciudad de México', 'Coahuila', 'Colima', 'Durango', 'Estado de México',
    'Guanajuato', 'Guerrero', 'Hidalgo', 'Jalisco', 'Michoacán', 'Morelos', 'Nayarit',
    'Nuevo León', 'Oaxaca', 'Puebla', 'Querétaro', 'Quintana Roo', 'San Luis Potosí',
    'Sinaloa', 'Sonora', 'Tabasco', 'Tamaulipas', 'Tlaxcala', 'Veracruz', 'Yucatán', 'Zacatecas'
  ];
  const MX_STATES_BY_UPPER = MX_STATES.reduce((acc, s) => {
    acc[s.toUpperCase()] = s;
    return acc;
  }, {});

  // Abreviaturas POSTALES reales (SEPOMEX) — verificadas 2026-07-10 contra direcciones
  // reales de campo (prod, `accounts.address`): NO vienen separadas por comas; el
  // Estado es el ÚLTIMO token del string, en abreviatura postal (no el código CURP de
  // 2 letras). Ej.: "C MELITON ALBAÑEZ 2145 FRACC PERLA 23040 LA PAZ B.C.S." → BCS.
  // estadoFrom() vivía roto para el 100% de las cuentas reales: solo soportaba 5
  // abreviaturas (regex al final del string SIN separar por espacio) y exigía coma
  // como fallback — las direcciones reales no traen coma en ningún lado.
  const MX_ABBR = {
    AGS: 'Aguascalientes', BC: 'Baja California', BCS: 'Baja California Sur',
    CAMP: 'Campeche', CHIS: 'Chiapas', CHIH: 'Chihuahua',
    CDMX: 'Ciudad de México', DF: 'Ciudad de México',
    COAH: 'Coahuila', COL: 'Colima', DGO: 'Durango',
    MEX: 'Estado de México', EDOMEX: 'Estado de México',
    GTO: 'Guanajuato', GRO: 'Guerrero', HGO: 'Hidalgo', JAL: 'Jalisco', MICH: 'Michoacán',
    MOR: 'Morelos', NAY: 'Nayarit', NL: 'Nuevo León', OAX: 'Oaxaca', PUE: 'Puebla',
    QRO: 'Querétaro', QROO: 'Quintana Roo', QR: 'Quintana Roo', SLP: 'San Luis Potosí',
    SIN: 'Sinaloa', SON: 'Sonora', TAB: 'Tabasco', TAMPS: 'Tamaulipas', TAM: 'Tamaulipas',
    TLAX: 'Tlaxcala', VER: 'Veracruz', YUC: 'Yucatán', ZAC: 'Zacatecas',
  };

  function estadoFrom(address) {
    if (!address || !String(address).trim()) return null;
    const addr = String(address).trim();

    // Formato real de campo (sin comas): el Estado es el ÚLTIMO token, a veces con
    // puntos (B.C.S., OAX., GTO.). Se prueba primero — es el formato observado en
    // el 100% de las direcciones de prod.
    const lastTok = addr.split(/\s+/).pop().replace(/\./g, '').toUpperCase();
    if (MX_ABBR[lastTok]) return MX_ABBR[lastTok];

    // Fallback: formato con comas + nombre completo del estado (si alguna vez aparece).
    const lastSegment = addr.split(',').pop().trim();
    const canonical = MX_STATES_BY_UPPER[lastSegment.toUpperCase()];
    if (canonical) return canonical;

    return null;
  }

  function formatHito(ev) {
    if (!ev) return { label: '—', cls: 'proc', tone: 'proc' };
    if (ev.kind === 'deposit') {
      if (ev.status === 'approved') return { label: 'completado', cls: 'ok', tone: 'ok' };
      if (ev.code === '3DS_REQUIRED' || ev.reason === '3DS') return { label: '3DS', cls: 'threeds', tone: 'threeds' };
      if (ev.status === 'processing' || ev.status === 'pending' || ev.status === 'proc') return { label: 'en proceso', cls: 'proc', tone: 'proc' };
      return { label: 'rechazado', cls: 'fail', tone: 'fail' };
    }
    if (ev.kind === 'login') return { label: 'login', cls: 'ok', tone: 'ok' };
    return { label: ev.kind || '—', cls: 'proc', tone: 'proc' };
  }

  // ── Medida del piso de la tabla + tope del panel KPI (persiana coherente) ──
  // panelReserve: px que SIEMPRE quedan para filterbar + pagebar + minRows filas
  // (piso operativo: nunca menos de minRows cuentas visibles). Reemplaza el
  // TABLE_RESERVE=300 fijo que no medía cuántas filas cabían.
  function panelReserve({ filterbarH, pagebarH, rowH, minRows }) {
    return filterbarH + pagebarH + rowH * minRows;
  }
  // panelMaxH: tope de altura del panel KPI. Si el viewport no da ni para el
  // reserve + el piso del panel, cae a un fallback razonable.
  function panelMaxH({ mainH, reserve, minPanelH, fallback }) {
    return mainH > reserve + minPanelH ? mainH - reserve : fallback;
  }
  // toggleTarget: decide plegar/desplegar por GEOMETRÍA (qué tan cerca está el
  // alto actual del tope vs del default), no por un flag que se desincroniza si
  // el operador arrastró el vgutter a un punto intermedio.
  function toggleTarget({ currentH, collapsedH, expandedH }) {
    return currentH < (collapsedH + expandedH) / 2 ? 'expand' : 'collapse';
  }

  // anchoredPanelH: alto del panel KPI (y de La Pantalla, que lo copia) tal que la
  // barra "Cuentas" quede a la misma altura que la etiqueta "Sistema" del menú
  // lateral (regla de Robert, campo 2026-07-09: "que Sistema quede a la altura de
  // Cuentas... el límite para ambos, lo que quepa arriba sin deformar la interfaz").
  // delta = cuánto hay que crecer/encoger el panel para que Cuentas alcance a Sistema;
  // se suma al alto ACTUAL del panel (no se asume nada del layout, solo se mide).
  function anchoredPanelH({ currentPanelH, filterbarTop, sistemaTop, minH }) {
    const delta = sistemaTop - filterbarTop;
    return Math.max(minH, Math.round(currentPanelH + delta));
  }

  // ── _withdrawBtnState: estado del botón/panel de retiro dedicado (lógica pura) ──
  // d.balance_real = saldo Real; d._wd_pending = true si hay retiro no-terminal (lo calcula
  // el render de pantalla.js vía _wdStatusFromRow antes de llamar esta función — desacopla
  // la lógica pura del DOM-dependent).
  function _withdrawBtnState(d, role) {
    if (role !== 'superadmin') return { render: false, disabled: true, tooltip: '' };
    const balance = parseFloat((d && d.balance_real) || 0) || 0;
    if (balance < 100) return { render: true, disabled: true, tooltip: 'Saldo < $100' };
    if (d && d._wd_pending) return { render: true, disabled: false, tooltip: 'Retiro en curso…' };
    return { render: true, disabled: false, tooltip: 'Retirar' };
  }

  const api = { splitTransactions, estadoFrom, formatHito, panelReserve, panelMaxH, toggleTarget, anchoredPanelH, _withdrawBtnState };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PantallaLogic = api;
})(typeof window !== 'undefined' ? window : globalThis);
