/* strip_logic.js — lógica pura del orden de los módulos del strip superior
   (cards Actividad / Recientes / Pool). Sin DOM → testeable con `node`.
   El wiring DOM (drag por el grip, persistencia, aplicar orden) vive en app.js
   (initStripReorder). Las proporciones de ancho son por SLOT (posición), no por
   card: reordenar mueve la card al slot destino y toma su ancho. */
(function (root) {
  'use strict';

  var DEFAULT = ['activity', 'recientes', 'pool'];

  var StripLogic = {
    DEFAULT: DEFAULT,

    // Normaliza un orden arbitrario a exactamente los 3 módulos válidos, sin
    // duplicados y completando los que falten (en su orden default). Resiliente
    // a localStorage corrupto o a un módulo agregado/quitado en el futuro.
    sanitize: function (order) {
      var seen = {}, out = [];
      (Array.isArray(order) ? order : []).forEach(function (m) {
        if (DEFAULT.indexOf(m) !== -1 && !seen[m]) { seen[m] = true; out.push(m); }
      });
      DEFAULT.forEach(function (m) { if (!seen[m]) out.push(m); });
      return out;
    },

    // Intercambia (swap) las posiciones de `fromId` y `toId`: arrastrar una card y
    // soltarla sobre otra las permuta — "intercambiables de lugar" (Robert).
    // Predecible y simétrico para 3 cards. Devuelve un NUEVO array saneado.
    reorder: function (order, fromId, toId) {
      var cur = StripLogic.sanitize(order);
      if (fromId === toId) return cur;
      var a = cur.indexOf(fromId), b = cur.indexOf(toId);
      if (a === -1 || b === -1) return cur;
      var t = cur[a]; cur[a] = cur[b]; cur[b] = t;
      return cur;
    },

    isDefault: function (order) {
      var s = StripLogic.sanitize(order);
      return s[0] === DEFAULT[0] && s[1] === DEFAULT[1] && s[2] === DEFAULT[2];
    },
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = { StripLogic: StripLogic };
  root.StripLogic = StripLogic;
})(typeof window !== 'undefined' ? window : this);
