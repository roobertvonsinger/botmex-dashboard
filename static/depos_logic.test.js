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
test('presetsForMode single: [100] manual, reps visible', () => {
  const p = D.presetsForMode('single');
  assert.deepEqual(p.presets, [100]);
  assert.equal(p.manual, true);
  assert.equal(p.repsVisible, true);
});
test('presetsForMode multi: [10,50,1000] sin manual, reps oculto', () => {
  const p = D.presetsForMode('multi');
  assert.deepEqual(p.presets, [10, 50, 1000]);
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
