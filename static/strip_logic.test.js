/* Tests de StripLogic (orden de módulos del strip). Correr: node strip_logic.test.js */
const { StripLogic } = require('./strip_logic.js');

let pass = 0, fail = 0;
function eq(actual, expected, name) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { pass++; }
  else { fail++; console.error(`✗ ${name}\n   esperado: ${e}\n   obtuvo:   ${a}`); }
}

const D = ['activity', 'recientes', 'pool'];

// sanitize
eq(StripLogic.sanitize(null), D, 'sanitize(null) → default');
eq(StripLogic.sanitize([]), D, 'sanitize([]) → default');
eq(StripLogic.sanitize(['pool']), ['pool', 'activity', 'recientes'], 'sanitize parcial completa el resto');
eq(StripLogic.sanitize(['pool', 'pool', 'activity']), ['pool', 'activity', 'recientes'], 'sanitize quita duplicados');
eq(StripLogic.sanitize(['x', 'pool', 'recientes', 'y', 'activity']), ['pool', 'recientes', 'activity'], 'sanitize ignora módulos inválidos');
eq(StripLogic.sanitize(['recientes', 'pool', 'activity']), ['recientes', 'pool', 'activity'], 'sanitize respeta orden válido');

// reorder (swap)
eq(StripLogic.reorder(D, 'activity', 'pool'), ['pool', 'recientes', 'activity'], 'swap extremos');
eq(StripLogic.reorder(D, 'activity', 'recientes'), ['recientes', 'activity', 'pool'], 'swap adyacentes 0-1');
eq(StripLogic.reorder(D, 'recientes', 'pool'), ['activity', 'pool', 'recientes'], 'swap adyacentes 1-2');
eq(StripLogic.reorder(D, 'pool', 'pool'), D, 'swap consigo mismo = no-op');
eq(StripLogic.reorder(D, 'activity', 'zzz'), D, 'swap con id inválido = no-op');
// swap es involutivo: aplicarlo dos veces vuelve al original
eq(StripLogic.reorder(StripLogic.reorder(D, 'activity', 'pool'), 'activity', 'pool'), D, 'doble swap vuelve al origen');
// no muta el input
const orig = D.slice();
StripLogic.reorder(orig, 'activity', 'pool');
eq(orig, D, 'reorder no muta el array de entrada');

// isDefault
eq(StripLogic.isDefault(D), true, 'isDefault(default)=true');
eq(StripLogic.isDefault(['pool', 'recientes', 'activity']), false, 'isDefault(reordenado)=false');
eq(StripLogic.isDefault(null), true, 'isDefault(null)=true (sanea a default)');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
