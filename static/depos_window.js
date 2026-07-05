/* depos_window.js — convierte el modal v8 (#depos) en ventana manipulable.
   3 estados: 'float' (movible + resize), 'left' / 'right' (acoplada a la tabla).
   Sin scroll: el cuerpo se ajusta por flex; el resize respeta min-w/min-h.
   Patrón adaptado de Rita (windowDrag.js + windowResize.js), reescrito para esta UI.
   Geometría pura en DeposWindowGeo (testeable con node). */
(function (root) {
  'use strict';

  // ── Geometría pura (sin DOM) ────────────────────────────────────────────────
  var Geo = {
    clamp: function (v, min, max) { return v < min ? min : (v > max ? max : v); },

    // Mantener accesible la barra de título: nunca dejar la ventana fuera de alcance.
    floatBounds: function (left, top, w, h, vw, vh, keep) {
      keep = keep || 90;
      return {
        left: Math.max(keep - w, Math.min(left, vw - keep)),
        top: Math.max(0, Math.min(top, vh - 30)),
      };
    },

    // Bordes cercanos al puntero (para iniciar resize).
    edgesAt: function (rect, cx, cy, edge) {
      edge = edge || 8;
      var within = cy >= rect.top - edge && cy <= rect.top + rect.height + edge &&
                   cx >= rect.left - edge && cx <= rect.left + rect.width + edge;
      if (!within) return { l: false, r: false, t: false, b: false };
      return {
        l: Math.abs(cx - rect.left) <= edge,
        r: Math.abs(cx - (rect.left + rect.width)) <= edge,
        t: Math.abs(cy - rect.top) <= edge,
        b: Math.abs(cy - (rect.top + rect.height)) <= edge,
      };
    },

    cursorFor: function (e) {
      if ((e.l && e.t) || (e.r && e.b)) return 'nwse-resize';
      if ((e.r && e.t) || (e.l && e.b)) return 'nesw-resize';
      if (e.l || e.r) return 'ew-resize';
      if (e.t || e.b) return 'ns-resize';
      return '';
    },

    // Nuevo rect al arrastrar un borde (ancla el lado opuesto), con min y viewport.
    resizeRect: function (start, edges, dx, dy, minW, minH, vw, vh) {
      var left = start.left, top = start.top, width = start.width, height = start.height;
      if (edges.r) width = start.width + dx;
      if (edges.b) height = start.height + dy;
      if (edges.l) { width = start.width - dx; left = start.left + dx; }
      if (edges.t) { height = start.height - dy; top = start.top + dy; }
      if (width < minW) { if (edges.l) left = start.left + (start.width - minW); width = minW; }
      if (height < minH) { if (edges.t) top = start.top + (start.height - minH); height = minH; }
      if (edges.l && left < 0) { width += left; left = 0; }
      if (edges.t && top < 0) { height += top; top = 0; }
      if (left + width > vw) width = Math.max(minW, vw - left);
      if (top + height > vh) height = Math.max(minH, vh - top);
      return { left: left, top: top, width: width, height: height };
    },

    // Rect del panel acoplado dentro de la zona (header Cuentas .. paginador).
    dockRect: function (zone, side, dockW) {
      return {
        left: side === 'right' ? zone.left + zone.width - dockW : zone.left,
        top: zone.top,
        width: dockW,
        height: zone.height,
      };
    },

    // Ancho del dock al arrastrar el divisor; deja >=KEEP px a la tabla.
    dockWidthFromPointer: function (zone, side, mouseX, minW, maxW, keepTable) {
      keepTable = keepTable || 240;
      var w = side === 'right' ? (zone.left + zone.width - mouseX) : (mouseX - zone.left);
      return Geo.clamp(w, minW, Math.min(maxW, zone.width - keepTable));
    },

    // Lado de acople durante el drag según el centro horizontal de la ventana; o null.
    snapZone: function (zone, panelCenterX, panelTop, frac) {
      frac = frac || 0.32;
      // sólo si la ventana está sobre la franja de la tabla (no muy arriba)
      if (panelTop > zone.top + zone.height) return null;
      if (panelCenterX > zone.left + zone.width * (1 - frac)) return 'right';
      if (panelCenterX < zone.left + zone.width * frac) return 'left';
      return null;
    },

    // Política de visibilidad del panel de depósitos por vista y rol (tanda 4).
    // - accounts: SIEMPRE visible, en la zona de la tabla (donde el usuario lo dejó).
    // - logs/activity: visible SOLO para SA, acoplado a la IZQUIERDA de esa vista
    //   ("sin estorbar"); su zona de dock es la sección misma.
    // - cualquier otra vista: OCULTO (nunca flotando encima — ese era el bug).
    // 'scope' guía el wiring: 'accounts' usa la preferencia del usuario; 'docked-left'
    // fuerza izquierda sin pisar esa preferencia; 'hidden' esconde el panel.
    sectionDock: function (section, isSA) {
      if (section === 'accounts') return { visible: true, scope: 'accounts', zoneId: 'accDockZone' };
      if (isSA && (section === 'logs' || section === 'activity'))
        return { visible: true, scope: 'docked-left', zoneId: section === 'logs' ? 'logsMain' : 'activityMain' };
      return { visible: false, scope: 'hidden', zoneId: null };
    },
  };

  // node export para tests
  if (typeof module !== 'undefined' && module.exports) { module.exports = { DeposWindowGeo: Geo }; }
  root.DeposWindowGeo = Geo;

  if (typeof document === 'undefined') return; // entorno node: sólo geometría

  // ── Wiring DOM ───────────────────────────────────────────────────────────────
  var MINW = 360, MINH = 500, DOCK_MINW = 320, DOCK_MAXW = 560, DOCK_GAP = 14;

  function DeposWindow() {}

  DeposWindow.init = function (win, opts) {
    opts = opts || {};
    var storageKey = opts.storageKey || 'deposWin';
    var zoneId = opts.dockZoneId || 'accDockZone';
    var onClose = opts.onClose || function () {};
    var titlebarSel = opts.titlebar || '.depos-titlebar';
    var dividerSel = opts.divider || '.dw-divider';
    var minW = opts.minW || MINW, minH = opts.minH || MINH;

    // Default 'right': el panel encaja a la derecha de la tabla (el espacio que
    // Robert reservó en la maqueta). `section` rige el modo efectivo por vista.
    var ST = { mode: 'right', section: 'accounts', float: null, dockW: { left: 400, right: 400 }, open: false };
    load();

    var zone = function () { return document.getElementById(zoneId); };
    var rectOf = function (el) {
      var r = el.getBoundingClientRect();
      return { left: r.left, top: r.top, width: r.width, height: r.height };
    };
    var vw = function () { return window.innerWidth; };
    var vh = function () { return window.innerHeight; };

    function zoneRect() {
      var z = zone();
      if (!z) return null;
      var r = z.getBoundingClientRect();
      if (r.height < 60) return null; // sección oculta → no dockear
      // #accDockZone envuelve la filterbar (Cuentas/buscador/Restaurar/Actualizar
      // visibles) ADEMÁS de la tabla (index.html:162-186) — su rect crudo empieza en
      // la filterbar, no en la tabla. El dock debe alinearse con la TABLA (línea que
      // Robert marcó), así que descontamos la filterbar del top/height si existe.
      var fb = z.querySelector('.filterbar-accounts');
      var fbH = fb ? fb.getBoundingClientRect().height : 0;
      return { left: r.left, top: r.top + fbH, width: r.width, height: r.height - fbH };
    }

    // Mismos márgenes que .pantalla-sheet (pantalla.css: left/right 20px, top 18px,
    // bottom 14px) — ancla contra #accountsMain, NO contra el viewport crudo. Así el
    // panel flotante respeta el mismo borde vertical que La Pantalla (visto en campo,
    // prod: con vw()/vh() el panel quedaba "un poco fuera" al no coincidir márgenes).
    function mainBounds() {
      var m = document.getElementById('accountsMain');
      var r = m ? m.getBoundingClientRect() : null;
      return (r && r.width > 0) ? r : { left: 0, top: 0, width: vw(), height: vh() };
    }

    function defaultFloat() {
      var mb = mainBounds();
      var w = Math.min(440, mb.width - 40);
      var h = Math.min(640, mb.height - 80);
      return { left: mb.left + mb.width - w - 20, top: mb.top + 18, width: w, height: h };
    }

    // Re-encuadra CUALQUIER rect flotante (nuevo o restaurado de localStorage) a los
    // márgenes vigentes de #accountsMain. Sin esto, un rect guardado de una sesión
    // previa (con otra altura de KPI/La Pantalla) queda fuera de cuadro y no se
    // autocorrige porque apply() solo llama defaultFloat() cuando ST.float es null.
    function clampFloat(r) {
      var mb = mainBounds();
      var w = Math.min(r.width, mb.width - 40);
      var h = Math.min(r.height, mb.height - 34);
      var minLeft = mb.left + 20, maxLeft = Math.max(minLeft, mb.left + mb.width - 20 - w);
      var minTop = mb.top + 18, maxTop = Math.max(minTop, mb.top + mb.height - 14 - h);
      return {
        left: Geo.clamp(r.left, minLeft, maxLeft),
        top: Geo.clamp(r.top, minTop, maxTop),
        width: w, height: h,
      };
    }

    function setZonePad(side, w) {
      var z = zone(); if (!z) return;
      z.classList.toggle('dock-l', side === 'left');
      z.classList.toggle('dock-r', side === 'right');
      z.style.setProperty('--dock-w', (w + DOCK_GAP) + 'px');
      if (!side) { z.classList.remove('dock-l', 'dock-r'); z.style.removeProperty('--dock-w'); }
    }

    // Suelta la compresión de TODAS las zonas dockeables (la activa cambia con la
    // sección). Evita que una zona quede comprimida al cambiar de vista.
    function clearAllZonePads() {
      ['accDockZone', 'logsMain', 'activityMain'].forEach(function (id) {
        var z = document.getElementById(id);
        if (z) { z.classList.remove('dock-l', 'dock-r'); z.style.removeProperty('--dock-w'); }
      });
    }

    // Modo efectivo según la sección: en logs/activity (SA) el panel se ancla a la
    // izquierda sin sobreescribir la preferencia de accounts (ST.mode).
    function pantallaAbierta() {
      var p = document.getElementById('pantalla');
      return !!p && !p.hidden;
    }
    function effectiveMode() {
      if (ST.section === 'logs' || ST.section === 'activity') return 'left';
      // Decisión de Robert (campo): con La Pantalla desplegada, el panel de depósitos
      // SIEMPRE queda debajo (dockeado a #accDockZone, que en el DOM vive después del
      // strip de La Pantalla) — nunca comparte su franja aunque el operador prefiera
      // flotante. Al cerrarse, vuelve a la preferencia guardada (ST.mode intacto).
      if (ST.mode === 'float' && pantallaAbierta()) return 'right';
      return ST.mode;
    }
    // En esas vistas el panel queda fijo (no se arrastra/redimensiona por el header).
    function sectionLocked() { return ST.section === 'logs' || ST.section === 'activity'; }

    function applyRect(r, anim) {
      win.style.transition = anim
        ? 'left .42s cubic-bezier(.22,.61,.36,1),top .42s cubic-bezier(.22,.61,.36,1),width .42s cubic-bezier(.22,.61,.36,1),height .42s cubic-bezier(.22,.61,.36,1)'
        : 'none';
      win.style.left = Math.round(r.left) + 'px';
      win.style.top = Math.round(r.top) + 'px';
      win.style.width = Math.round(r.width) + 'px';
      win.style.height = Math.round(r.height) + 'px';
    }

    function apply(anim) {
      win.classList.add('dw-on');
      var em = effectiveMode();
      var docked = em !== 'float';
      win.classList.toggle('dw-docked', docked);
      win.classList.toggle('dw-dock-left', em === 'left');
      win.classList.toggle('dw-dock-right', em === 'right');
      if (docked) {
        var z = zoneRect();
        if (!z) {
          // zona sin geometría (su sección está oculta). En accounts caemos a
          // flotante; en logs/activity NO flotamos encima de la vista → no-op.
          if (!sectionLocked()) { ST.mode = 'float'; return apply(anim); }
          return;
        }
        var w = ST.dockW[em] = Geo.clamp(ST.dockW[em], DOCK_MINW, Math.min(DOCK_MAXW, z.width - 240));
        applyRect(Geo.dockRect(z, em, w), anim);
        setZonePad(em, w);
      } else {
        if (!ST.float) ST.float = defaultFloat();
        ST.float = clampFloat(ST.float);
        setZonePad(null);
        applyRect(ST.float, anim);
      }
      syncBtns();
      save();
    }

    function syncBtns() {
      var bl = win.querySelector('.dw-dock-l'), br = win.querySelector('.dw-dock-r');
      if (bl) bl.classList.toggle('on', ST.mode === 'left');
      if (br) br.classList.toggle('on', ST.mode === 'right');
    }

    function save() {
      try { localStorage.setItem(storageKey, JSON.stringify(ST)); } catch (_) {}
    }
    function load() {
      try {
        var s = JSON.parse(localStorage.getItem(storageKey) || 'null');
        if (s && s.mode) { ST.mode = s.mode; ST.float = s.float || null; ST.dockW = s.dockW || ST.dockW; }
      } catch (_) {}
    }

    function setMode(m, anim) { ST.mode = m; apply(anim !== false); }

    // ── drag (barra de título) ────────────────────────────────────────────────
    var drag = null, hint = ensureHint();
    function ensureHint() {
      var h = document.getElementById('dwHint');
      if (!h) { h = document.createElement('div'); h.id = 'dwHint'; h.className = 'dw-hint'; document.body.appendChild(h); }
      return h;
    }
    function showHint(side) {
      var z = zoneRect();
      if (!side || !z) { hint.classList.remove('on'); return; }
      var r = Geo.dockRect(z, side, ST.dockW[side]);
      hint.style.left = r.left + 'px'; hint.style.top = r.top + 'px';
      hint.style.width = r.width + 'px'; hint.style.height = r.height + 'px';
      hint.classList.add('on');
    }

    function startDrag(e) {
      cancelAnims();
      if (ST.mode !== 'float') {
        // soltar a flotar en el punto actual, conservando tamaño visible
        var r0 = rectOf(win);
        ST.float = { left: r0.left, top: r0.top, width: Math.min(r0.width, 460), height: r0.height };
        ST.mode = 'float'; setZonePad(null); win.classList.remove('dw-docked', 'dw-dock-left', 'dw-dock-right');
        applyRect(ST.float, false);
      }
      var r = rectOf(win);
      drag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
      win.classList.add('dw-grabbing');
      win.style.transition = 'none';
      e.preventDefault();
    }
    function onDragMove(e) {
      if (!drag) return;
      var w = win.offsetWidth, h = win.offsetHeight;
      var b = Geo.floatBounds(e.clientX - drag.dx, e.clientY - drag.dy, w, h, vw(), vh());
      ST.float = { left: b.left, top: b.top, width: w, height: h };
      win.style.left = b.left + 'px'; win.style.top = b.top + 'px';
      var z = zoneRect();
      showHint(z ? Geo.snapZone(z, b.left + w / 2, b.top) : null);
    }
    function onDragUp() {
      if (!drag) return;
      win.classList.remove('dw-grabbing'); hint.classList.remove('on');
      var z = zoneRect();
      var side = z ? Geo.snapZone(z, ST.float.left + ST.float.width / 2, ST.float.top) : null;
      drag = null;
      if (side) setMode(side, true); else apply(false);
    }

    // ── resize (bordes, sólo en flotante) ─────────────────────────────────────
    var rz = null;
    function updateCursor(e) {
      if (rz || drag || ST.mode !== 'float') return;
      var ed = Geo.edgesAt(rectOf(win), e.clientX, e.clientY, 8);
      win.style.cursor = Geo.cursorFor(ed) || '';
    }
    function startResize(e, edges) {
      cancelAnims();
      var r = rectOf(win);
      rz = { start: r, edges: edges, sx: e.clientX, sy: e.clientY };
      win.classList.add('dw-resizing'); win.style.transition = 'none';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    }
    function onResizeMove(e) {
      if (!rz) return;
      var nr = Geo.resizeRect(rz.start, rz.edges, e.clientX - rz.sx, e.clientY - rz.sy, minW, minH, vw(), vh());
      ST.float = nr; applyRect(nr, false);
    }
    function onResizeUp() {
      if (!rz) return;
      rz = null; win.classList.remove('dw-resizing'); document.body.style.userSelect = '';
      win.style.cursor = ''; save();
    }

    // ── divisor del dock (recorrer el ancho) ──────────────────────────────────
    var dv = null;
    function startDivider(e) {
      var div = e.currentTarget; dv = { side: ST.mode };
      div.classList.add('on'); document.body.style.userSelect = 'none';
      e.preventDefault(); e.stopPropagation();
    }
    function onDividerMove(e) {
      if (!dv) return;
      var z = zoneRect(); if (!z) return;
      ST.dockW[dv.side] = Geo.dockWidthFromPointer(z, dv.side, e.clientX, DOCK_MINW, DOCK_MAXW);
      apply(false);
    }
    function onDividerUp() {
      if (!dv) return; dv = null; document.body.style.userSelect = '';
      var d = win.querySelector(dividerSel); if (d) d.classList.remove('on'); save();
    }

    function cancelAnims() {
      try {
        win.getAnimations && win.getAnimations().filter(function (a) { return a.playState !== 'finished'; })
          .forEach(function (a) { a.cancel(); });
      } catch (_) {}
    }

    // ── eventos ───────────────────────────────────────────────────────────────
    win.addEventListener('mousemove', updateCursor);
    win.addEventListener('mousedown', function (e) {
      if (rz || drag || dv) return;
      if (e.target.closest('.dw-btn')) return;            // controles: su propio handler
      if (e.target.closest(dividerSel)) return;           // divisor: su propio handler
      if (sectionLocked()) return;                        // logs/activity: panel fijo a la izquierda
      if (ST.mode === 'float') {
        var ed = Geo.edgesAt(rectOf(win), e.clientX, e.clientY, 8);
        if (ed.l || ed.r || ed.t || ed.b) { startResize(e, ed); return; }
      }
      // arrastra por el header, salvo controles interactivos (botones/inputs)
      if (e.target.closest(titlebarSel) && !e.target.closest('button,a,input,select,textarea')) startDrag(e);
    });
    document.addEventListener('mousemove', function (e) { onDragMove(e); onResizeMove(e); onDividerMove(e); });
    document.addEventListener('mouseup', function () { onDragUp(); onResizeUp(); onDividerUp(); });

    var div = win.querySelector(dividerSel);
    if (div) div.addEventListener('mousedown', startDivider);

    var bl = win.querySelector('.dw-dock-l'); if (bl) bl.addEventListener('click', function (e) { e.stopPropagation(); setMode(ST.mode === 'left' ? 'float' : 'left'); });
    var br = win.querySelector('.dw-dock-r'); if (br) br.addEventListener('click', function (e) { e.stopPropagation(); setMode(ST.mode === 'right' ? 'float' : 'right'); });
    var bx = win.querySelector('.dw-close'); if (bx) bx.addEventListener('click', function (e) { e.stopPropagation(); onClose(); });

    // reclamp al cambiar el viewport
    var rt;
    window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { if (ST.open) apply(false); }, 120); });

    // API pública del controlador
    var api = {
      show: function () { ST.open = true; ST._hiddenBySection = false; apply(false); },
      hide: function () { ST.open = false; clearAllZonePads(); ST._hiddenBySection = false; }, // cierre explícito
      // apply() reserva espacio en accDockZone (setZonePad) como efecto lateral. Sin
      // el guard de ST.open, cualquier relayout de fondo (el resize listener de abajo,
      // o el ResizeObserver de app.js que dispara en CADA toggle de La Pantalla) volvía
      // a reservar ese hueco aunque el panel estuviera cerrado — mesa de cuentas quedaba
      // comprimida con espacio vacío sin ventana visible ahí (visto en campo, prod).
      relayout: function () { if (ST.open) apply(false); },
      isDocked: function () { return effectiveMode() !== 'float'; },
      mode: function () { return effectiveMode(); },
      // Política por vista/rol (tanda 4). Recibe la sección destino y si el viewer
      // es SA. Decide: visible+dónde, u oculto (sin flotar encima de otra vista).
      reanchorForSection: function (section, isSA) {
        ST.section = section;
        var rootEl = document.getElementById('deposRoot');
        var isOpen = rootEl && !rootEl.classList.contains('hidden');
        // panel cerrado y no oculto-por-sección: no forzar nada (no debe aparecer solo).
        if (!isOpen && !ST._hiddenBySection) return;
        var pol = Geo.sectionDock(section, !!isSA);
        if (!pol.visible) {
          clearAllZonePads();
          if (rootEl) { rootEl.classList.add('hidden'); rootEl.setAttribute('aria-hidden', 'true'); }
          ST._hiddenBySection = true;
          return;
        }
        if (ST._hiddenBySection && rootEl) {
          rootEl.classList.remove('hidden'); rootEl.setAttribute('aria-hidden', 'false');
        }
        ST._hiddenBySection = false;
        clearAllZonePads();
        zoneId = pol.zoneId || 'accDockZone';
        apply(true);
      },
    };
    win.__deposWin = api;
    DeposWindow._instance = api;
    return api;
  };

  root.DeposWindow = DeposWindow;
})(typeof window !== 'undefined' ? window : this);
