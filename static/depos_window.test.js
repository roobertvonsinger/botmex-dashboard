/* Tests node de la geometría pura de depos_window. Correr: node depos_window.test.js */
const { DeposWindowGeo: G } = require('./depos_window.js');

let pass = 0, fail = 0;
function eq(a, b, msg) {
  const ok = JSON.stringify(a) === JSON.stringify(b);
  if (ok) { pass++; } else { fail++; console.error('FAIL ' + msg + '\n  got ' + JSON.stringify(a) + '\n  exp ' + JSON.stringify(b)); }
}
function ok(cond, msg) { if (cond) pass++; else { fail++; console.error('FAIL ' + msg); } }

// clamp
eq(G.clamp(5, 0, 10), 5, 'clamp dentro');
eq(G.clamp(-3, 0, 10), 0, 'clamp bajo');
eq(G.clamp(99, 0, 10), 10, 'clamp alto');

// floatBounds — la titlebar nunca se pierde
let b = G.floatBounds(-500, -200, 400, 600, 1280, 800, 90);
ok(b.left >= 90 - 400, 'floatBounds left no se pierde por izquierda');
ok(b.top >= 0, 'floatBounds top no negativo');
b = G.floatBounds(5000, 5000, 400, 600, 1280, 800, 90);
ok(b.left <= 1280 - 90, 'floatBounds left no se pierde por derecha');
ok(b.top <= 800 - 30, 'floatBounds top no pasa el fondo');

// edgesAt
let r = { left: 100, top: 100, width: 200, height: 150 };
eq(G.edgesAt(r, 100, 175, 8).l, true, 'edge izquierdo detectado');
eq(G.edgesAt(r, 300, 175, 8).r, true, 'edge derecho detectado');
eq(G.edgesAt(r, 200, 100, 8).t, true, 'edge superior detectado');
eq(G.edgesAt(r, 200, 250, 8).b, true, 'edge inferior detectado');
let center = G.edgesAt(r, 200, 175, 8);
ok(!center.l && !center.r && !center.t && !center.b, 'centro sin bordes');
let far = G.edgesAt(r, 500, 500, 8);
ok(!far.l && !far.r && !far.t && !far.b, 'fuera del rect sin bordes');

// cursorFor
eq(G.cursorFor({ l: true, t: true }), 'nwse-resize', 'cursor esquina NW');
eq(G.cursorFor({ r: true, t: true }), 'nesw-resize', 'cursor esquina NE');
eq(G.cursorFor({ r: true }), 'ew-resize', 'cursor horizontal');
eq(G.cursorFor({ b: true }), 'ns-resize', 'cursor vertical');

// resizeRect — borde derecho expande, opuesto anclado
let start = { left: 100, top: 100, width: 200, height: 150 };
let rr = G.resizeRect(start, { r: true }, 50, 0, 360, 460, 2000, 2000);
eq(rr.width, 360, 'resize derecho respeta minW');
eq(rr.left, 100, 'resize derecho no mueve left');
// borde izquierdo: al achicar por debajo de min, ancla el lado derecho
rr = G.resizeRect(start, { l: true }, 500, 0, 50, 50, 2000, 2000);
ok(rr.width === 50, 'resize izquierdo respeta minW');
ok(rr.left === start.left + (start.width - 50), 'resize izquierdo ancla lado derecho');
// no salir del viewport por arriba/izquierda
rr = G.resizeRect({ left: 10, top: 10, width: 100, height: 100 }, { l: true, t: true }, -100, -100, 50, 50, 2000, 2000);
ok(rr.left >= 0 && rr.top >= 0, 'resize no sale del viewport (origen)');

// dockRect
let zone = { left: 200, top: 120, width: 800, height: 500 };
eq(G.dockRect(zone, 'right', 400), { left: 600, top: 120, width: 400, height: 500 }, 'dockRect derecha');
eq(G.dockRect(zone, 'left', 400), { left: 200, top: 120, width: 400, height: 500 }, 'dockRect izquierda');

// dockWidthFromPointer — deja espacio a la tabla
let w = G.dockWidthFromPointer(zone, 'right', 700, 320, 560, 240);
ok(w >= 320 && w <= 560, 'dock width en rango');
ok(w <= zone.width - 240, 'dock width deja >=240 a la tabla');
w = G.dockWidthFromPointer(zone, 'right', 100, 320, 560, 240); // arrastre a la izq = más ancho
eq(w, 560, 'dock width no pasa de maxW');
w = G.dockWidthFromPointer(zone, 'right', 990, 320, 560, 240); // arrastre al borde der = más angosto
eq(w, 320, 'dock width no baja de minW');

// snapZone
let z = { left: 200, top: 120, width: 800, height: 500 };
eq(G.snapZone(z, 950, 200, 0.32), 'right', 'snap derecha');
eq(G.snapZone(z, 260, 200, 0.32), 'left', 'snap izquierda');
eq(G.snapZone(z, 600, 200, 0.32), null, 'snap centro = null');
eq(G.snapZone(z, 950, 9000, 0.32), null, 'snap nulo si la ventana está muy abajo del área');

// sectionDock — política de visibilidad por vista/rol (tanda 4)
// accounts: visible para ambos roles, zona de la tabla
eq(G.sectionDock('accounts', true), { visible: true, scope: 'accounts', zoneId: 'accDockZone' }, 'accounts SA → visible tabla');
eq(G.sectionDock('accounts', false), { visible: true, scope: 'accounts', zoneId: 'accDockZone' }, 'accounts operador → visible tabla');
// logs/activity: SOLO SA, acoplado a la izquierda de esa vista
eq(G.sectionDock('logs', true), { visible: true, scope: 'docked-left', zoneId: 'logsMain' }, 'logs SA → dock izq logsMain');
eq(G.sectionDock('activity', true), { visible: true, scope: 'docked-left', zoneId: 'activityMain' }, 'activity SA → dock izq activityMain');
eq(G.sectionDock('logs', false), { visible: false, scope: 'hidden', zoneId: null }, 'logs operador → oculto');
eq(G.sectionDock('activity', false), { visible: false, scope: 'hidden', zoneId: null }, 'activity operador → oculto');
// resto de vistas: oculto para ambos
['pool', 'notifications', 'health', 'admin', 'bin-stats'].forEach(function (s) {
  eq(G.sectionDock(s, true), { visible: false, scope: 'hidden', zoneId: null }, s + ' SA → oculto');
  eq(G.sectionDock(s, false), { visible: false, scope: 'hidden', zoneId: null }, s + ' operador → oculto');
});

console.log((fail ? '✗' : '✓') + ' depos_window.geo: ' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
