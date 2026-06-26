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
