const assert = require('assert');
const P = require('./pantalla_logic.js');

const movs = [
  { source: 'dashboard', amount: 50, state: 'ok' },
  { source: 'betmexico', kind: 'withdrawal', amount: 300 },
  { source: 'dashboard', amount: 10, state: 'fail' },
];
const s = P.splitTransactions(movs);
assert.strictEqual(s.botmexico.length, 2, 'botmexico = source dashboard');
assert.strictEqual(s.betmexico.length, 1, 'betmexico = el resto');
assert.strictEqual(s.botmexico[0].amount, 50);

// Formato real de campo (sin comas, abreviatura postal al final) — bug 2026-07-10:
// estadoFrom() nunca matcheaba ninguna dirección real de prod (ver pantalla_logic.js).
assert.strictEqual(P.estadoFrom('CALLE MAYORCA 107 FRACC LAS CALIFORNIAS 22404 TIJUANA B.C'), 'Baja California');
assert.strictEqual(P.estadoFrom('C MELITON ALBAÑEZ 2145 FRACC PERLA 23040 LA PAZ B.C.S.'), 'Baja California Sur');
assert.strictEqual(P.estadoFrom('AV /PINOS S/N COL EUCALIPTOS 68050 OAXACA DE JUAREZ OAX.'), 'Oaxaca');
assert.strictEqual(P.estadoFrom('C CUARTO SOL 1 - SECCION PARQUES 54720 CUAUTITLAN IZCALLI MEX'), 'Estado de México');
assert.strictEqual(P.estadoFrom('C POZA RICA 1580 FRACC 18 DE MARZO 44960 GUADALAJARA JAL'), 'Jalisco');
assert.strictEqual(P.estadoFrom('CAPIZAHUATL 401 FRACC COPORO Y CERRO AZUL I 90401 APIZACO TLAX.'), 'Tlaxcala');
// Fallback con comas + nombre completo (si alguna vez aparece en ese formato).
assert.strictEqual(P.estadoFrom('AV JUAREZ 12, GUADALAJARA, JALISCO'), 'Jalisco');
assert.strictEqual(P.estadoFrom(''), null);
assert.strictEqual(P.estadoFrom(null), null);
assert.strictEqual(P.estadoFrom('DIRECCION SIN ESTADO RECONOCIBLE 123'), null);

const h = P.formatHito({ kind: 'deposit', status: 'approved', amount: 50 });
assert.strictEqual(h.tone, 'ok');
const h2 = P.formatHito({ kind: 'deposit', code: '3DS_REQUIRED' });
assert.strictEqual(h2.tone, 'threeds');

// ── panelReserve: px reservados a la tabla (filterbar + pagebar + 10 filas) ──
assert.strictEqual(P.panelReserve({ filterbarH: 48, pagebarH: 44, rowH: 34, minRows: 10 }), 432, 'panelReserve suma filterbar+pagebar+10 filas');
assert.strictEqual(P.panelReserve({ filterbarH: 0, pagebarH: 0, rowH: 30, minRows: 10 }), 300, 'panelReserve solo filas');

// ── panelMaxH: tope del panel KPI; cae al fallback en viewports chicos ──
assert.strictEqual(P.panelMaxH({ mainH: 900, reserve: 432, minPanelH: 96, fallback: 460 }), 468, 'panelMaxH normal = mainH - reserve');
assert.strictEqual(P.panelMaxH({ mainH: 400, reserve: 432, minPanelH: 96, fallback: 460 }), 460, 'panelMaxH viewport chico cae a fallback');

// ── toggleTarget: dirección por geometría (punto medio), sin flag externo ──
assert.strictEqual(P.toggleTarget({ currentH: 212, collapsedH: 212, expandedH: 468 }), 'expand', 'toggleTarget desde plegada → expandir');
assert.strictEqual(P.toggleTarget({ currentH: 468, collapsedH: 212, expandedH: 468 }), 'collapse', 'toggleTarget desde desplegada → plegar');
assert.strictEqual(P.toggleTarget({ currentH: 300, collapsedH: 212, expandedH: 468 }), 'expand', 'toggleTarget bajo el punto medio → expandir');
assert.strictEqual(P.toggleTarget({ currentH: 400, collapsedH: 212, expandedH: 468 }), 'collapse', 'toggleTarget sobre el punto medio → plegar');

// ── anchoredPanelH: crece/encoge el panel para que Cuentas alcance a Sistema ──
assert.strictEqual(
  P.anchoredPanelH({ currentPanelH: 212, filterbarTop: 534, sistemaTop: 381, minH: 96 }),
  96, 'Sistema arriba de Cuentas → encoge (212-153=59, pero el piso minH=96 gana)'
);
assert.strictEqual(
  P.anchoredPanelH({ currentPanelH: 212, filterbarTop: 300, sistemaTop: 534, minH: 96 }),
  446, 'Sistema abajo de Cuentas → crece (534-300=234 más)'
);
assert.strictEqual(
  P.anchoredPanelH({ currentPanelH: 212, filterbarTop: 500, sistemaTop: 100, minH: 96 }),
  96, 'delta negativo grande no baja del piso minH'
);
assert.strictEqual(
  P.anchoredPanelH({ currentPanelH: 300, filterbarTop: 400, sistemaTop: 400, minH: 96 }),
  300, 'ya alineado (delta=0) → sin cambio'
);

console.log('OK pantalla_logic');
