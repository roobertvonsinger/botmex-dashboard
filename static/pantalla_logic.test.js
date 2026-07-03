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

assert.strictEqual(P.estadoFrom('CALLE MAYORCA 107 FRACC LAS CALIFORNIAS 22404 TIJUANA B.C'), 'B.C.');
assert.strictEqual(P.estadoFrom('AV JUAREZ 12, GUADALAJARA, JALISCO'), 'Jalisco');
assert.strictEqual(P.estadoFrom(''), null);
assert.strictEqual(P.estadoFrom(null), null);

const h = P.formatHito({ kind: 'deposit', status: 'approved', amount: 50 });
assert.strictEqual(h.tone, 'ok');
const h2 = P.formatHito({ kind: 'deposit', code: '3DS_REQUIRED' });
assert.strictEqual(h2.tone, 'threeds');

console.log('OK pantalla_logic');
