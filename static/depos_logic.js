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

  return { deriveMode, presetsForMode };
});
