const test = require('node:test');
const assert = require('node:assert');
const D = require('./depos_logic.js');

// ── Task 1: deriveMode + presetsForMode ──
test('deriveMode: 1 cuenta reps=1 -> single', () => {
  assert.equal(D.deriveMode(1, 1), 'single');
});
test('deriveMode: 1 cuenta reps>1 -> scheduled', () => {
  assert.equal(D.deriveMode(1, 5), 'scheduled');
});
test('deriveMode: 0 cuentas (vacío) -> single', () => {
  assert.equal(D.deriveMode(0, 1), 'single');
});
test('deriveMode: varias cuentas -> multi (ignora reps)', () => {
  assert.equal(D.deriveMode(3, 9), 'multi');
});
test('presetsForMode single: valores sugeridos manual, reps visible', () => {
  const p = D.presetsForMode('single');
  assert.deepEqual(p.presets, [10, 50, 150, 300, 490]);
  assert.equal(p.manual, true);
  assert.equal(p.repsVisible, true);
});
test('presetsForMode multi: [10,50,490] (alineado al cap $499) sin manual, reps oculto', () => {
  const p = D.presetsForMode('multi');
  assert.deepEqual(p.presets, [10, 50, 490]); // $1000 daba HTTP 400 (cap DEP_MAX_PER_TXN)
  assert.equal(p.manual, false);
  assert.equal(p.repsVisible, false);
});
test('presetsForMode scheduled: como single (reps visible)', () => {
  const p = D.presetsForMode('scheduled');
  assert.equal(p.repsVisible, true);
  assert.equal(p.manual, true);
});

// ── Task 2: mapPhaseToScene + phaseToPct ──
test('mapPhaseToScene: login family', () => {
  ['login_start', 'login_done', 'login_reused'].forEach(n =>
    assert.equal(D.mapPhaseToScene(n), 'login'));
});
test('mapPhaseToScene: begin family -> form (pero *_retry gana)', () => {
  assert.equal(D.mapPhaseToScene('gateway_begin'), 'form');
  assert.equal(D.mapPhaseToScene('gateway_begin_done'), 'form');
  assert.equal(D.mapPhaseToScene('gateway_begin_retry'), 'retry'); // un retry siempre muestra escena retry
});
test('mapPhaseToScene: submit/check -> processing', () => {
  ['gateway_submit', 'gateway_submit_done', 'gateway_check', 'gateway_check_done', 'implicit_3ds_detected'].forEach(n =>
    assert.equal(D.mapPhaseToScene(n), 'processing'));
});
test('mapPhaseToScene: retry transitorio -> retry', () => {
  ['login_retry', 'gateway_check_retry'].forEach(n =>
    assert.equal(D.mapPhaseToScene(n), 'retry'));
});
test('mapPhaseToScene: done', () => {
  assert.equal(D.mapPhaseToScene('done'), 'done');
});
test('phaseToPct monotonic', () => {
  assert.equal(D.phaseToPct('login_start'), 14);
  assert.equal(D.phaseToPct('gateway_begin'), 40);
  assert.equal(D.phaseToPct('gateway_submit'), 70);
  assert.equal(D.phaseToPct('gateway_check'), 82);
  assert.equal(D.phaseToPct('done'), 100);
  assert.equal(D.phaseToPct('login_retry'), null); // retry no mueve %
});

// ── Task 3: validatePipe (null=ok, string=error; alineado a app.js:3896) + parseCombo + fmtMoney ──
test('validatePipe 4 partes válido -> null', () =>
  assert.equal(D.validatePipe('4111111111111111|12|30|123'), null));
test('validatePipe 3 partes (MMYY) válido -> null', () =>
  assert.equal(D.validatePipe('4111111111111111|1230|123'), null));
test('validatePipe acepta espacios y / en exp', () => {
  assert.equal(D.validatePipe('4111111111111111 | 12/30 | 123'), null);
});
test('validatePipe mes inválido -> string error', () => {
  assert.ok(typeof D.validatePipe('4111111111111111|13|30|123') === 'string');
});
test('validatePipe basura -> string error', () => {
  assert.ok(typeof D.validatePipe('hola') === 'string');
  assert.ok(typeof D.validatePipe('4111|12|30') === 'string'); // num corto
});
test('validatePipe vacío -> string error', () => {
  assert.ok(typeof D.validatePipe('') === 'string');
});
test('parseCombo split en primer :', () => {
  assert.deepEqual(D.parseCombo('a@b.mx:Pass:word!'), { email: 'a@b.mx', password: 'Pass:word!' });
});
test('parseCombo sin : -> null', () => assert.equal(D.parseCombo('nope'), null));
test('fmtMoney', () => {
  assert.equal(D.fmtMoney(512), '$512.00');
  assert.equal(D.fmtMoney(1234.5), '$1,234.50');
});

// ── canonicalPipe: formato único NNNN|MM|YYYY|CVV (Robert 2026-06-27) ──
test('canonicalPipe normaliza todos los formatos a NNNN|MM|YYYY|CVV', () => {
  assert.equal(D.canonicalPipe('4111411141114111|12|2030|123'), '4111411141114111|12|2030|123'); // ya canónico
  assert.equal(D.canonicalPipe('4111411141114111|12|30|123'), '4111411141114111|12|2030|123');   // año 2 díg
  assert.equal(D.canonicalPipe('4111411141114111|1230|123'), '4111411141114111|12|2030|123');     // MMYY junto (3 partes)
  assert.equal(D.canonicalPipe('4111411141114111|12/30|123'), '4111411141114111|12|2030|123');    // con diagonal
  assert.equal(D.canonicalPipe('5119164448115445|06|26|910'), '5119164448115445|06|2026|910');
});

// ── Task 7: clasificación de resultado (real vs nuestro) + humanización (L3) ──
test('isRealRejection: estados reales de BetMexico', () => {
  ['BANK_REJECTED', '3DS_REQUIRED', 'INSUFFICIENT_FUNDS', 'CARD_EXPIRED', 'AUTOEXCLUSION', 'KYC_PENDING', 'LOGIN_DENIED'].forEach(c =>
    assert.equal(D.isRealRejection(c), true, c));
});
test('isRealRejection: errores nuestros NO son reales', () => {
  ['LOGIN_FAILED', 'RETRY_CAPTCHA', 'BEGIN_ERROR', 'PROXY_ERROR', '', undefined].forEach(c =>
    assert.equal(D.isRealRejection(c), false, String(c)));
});
test('humanError: nunca expone el código crudo', () => {
  assert.equal(D.humanError('BANK_REJECTED'), 'Tarjeta rechazada por el banco');
  assert.equal(D.humanError('3DS_REQUIRED'), 'Requiere verificación 3DS');
  assert.equal(D.humanError('LOGIN_DENIED'), 'Credenciales inválidas');
  // error nuestro: humanizado genérico, sin tripas
  assert.equal(D.humanError('RETRY_CAPTCHA'), 'No se pudo completar, intenta de nuevo');
  assert.equal(D.humanError('PROXY_504'), 'No se pudo completar, intenta de nuevo');
});
