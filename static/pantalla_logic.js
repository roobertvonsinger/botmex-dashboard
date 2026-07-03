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
  const ABBR_RE = /(B\.?C\.?|Q\.?R\.?|N\.?L\.?|CDMX|EDOMEX)\s*$/i;

  function estadoFrom(address) {
    if (!address || !String(address).trim()) return null;
    const addr = String(address).trim();

    const abbrMatch = addr.match(ABBR_RE);
    if (abbrMatch) {
      const raw = abbrMatch[1].toUpperCase().replace(/\./g, '');
      if (raw === 'CDMX') return 'CDMX';
      if (raw === 'EDOMEX') return 'EDOMEX';
      if (raw === 'BC') return 'B.C.';
      if (raw === 'QR') return 'Q.R.';
      if (raw === 'NL') return 'N.L.';
    }

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

  const api = { splitTransactions, estadoFrom, formatHito };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PantallaLogic = api;
})(typeof window !== 'undefined' ? window : globalThis);
