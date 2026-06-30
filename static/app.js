// Botmexico v2 — vanilla, sin frameworks.

const FRASES = [
  "El saldo habla; los demás, que murmuren.",
  "Calladito, cargadito, y a la siguiente cuenta.",
  "Que sude el banco — nosotros a cuadrar. 🇲🇽",
  "Hoy el panel se ve verde, y no es de envidia.",
  "El que madruga agarra las LIVE.",
  "Menos ansiedad, más actividad.",
  "Disciplina de monje, hambre de tianguis.",
  "Cada cuenta cuenta y cada peso pesa.",
  "Si el proxy aguanta, aquí aguantamos todos.",
  "No es suerte, mi rey: es que le sabemos.",
  "Trabaja en silencio y deja que el saldo grite.",
  "Las cuentas no se cuadran solas, éntrale.",
  "Respira hondo: hay LIVE pa' rato.",
  "El billete es penoso; invítalo con confianza.",
  "Aquí se chambea bonito, no se sufre feo.",
];

const esc = s => s == null ? '' : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

const state = {
  section: 'accounts',
  status: 'LIVE',
  grade: '',
  view: 'detail',   // vista única (Robert mató el toggle Simple/Detallada)
  rows: [],
  user: null,
  page: 1,
  pageSize: 50,
  lockHours: 2,
  filterInUse: false,
  cardsOnly: false,  // filter: solo cuentas con al menos 1 tarjeta
};


const selectedIds = new Set();
let markedSet = new Set();   // emails marcados con 📌 (privado por usuario)
let searchQuery = '';
let activityRows = [];
let activityFilter = { kind: '', who: null, time: 'all', q: '' };
let activityPage = 1;
let activityPageSize = 50;
const _actNewIds = new Set();   // ids/keys de eventos llegados via SSE — para animar como nuevos
let notifications = [];
let _evtSrc = null;
let _sortCol = null, _sortDir = -1;

// ─── Detalle de cuenta inline (acordeón) ───
// expandedAccountId: id de la cuenta cuyo panel de detalle está desplegado
// (o null). detailDataCache: cache del JSON de /details por id, para re-inyectar
// el panel tras un re-render de renderTable (SSE/sort/filtro) sin re-fetch ni
// flicker. Se invalida al cerrar o al pedir refresh explícito.
let expandedAccountId = null;
const detailDataCache = {};
// Paginación interna de movimientos por cuenta (10 por página). Persiste entre
// re-inyecciones del panel. Independiente del paginador de la tabla completa.
const _mvPage = {};
const _MV_PER_PAGE = 10;
// Nodo DOM del panel inline. Se PRESERVA entre re-renders de renderTable (SSE/
// sort/filtro): se re-inserta el mismo nodo en vez de reconstruir el HTML, para
// no resetear el estado del DOM (p.ej. <details open> de transacciones, focus).
// Solo se reconstruye en acciones explícitas (abrir cuenta, fetch, ver más, etc).
let _expandedNode = null;
// Mientras un panel está abierto, los reload() disparados por SSE (lock/unlock/
// depósito de OTROS operadores) se DIFIEREN: reconstruir la tabla debajo del
// panel lo destruía/reinsertaba y robaba los clicks del usuario. Se aplica un
// reload al cerrar el panel.
let _deferredTableRender = false;
function _liveReload() {
  if (expandedAccountId) { _deferredTableRender = true; return; }
  reload();
}
function _flushDeferredRender() {
  if (_deferredTableRender) { _deferredTableRender = false; reload(); }
}

function sortRows(col) {
  if (_sortCol === col) _sortDir = -_sortDir;
  else { _sortCol = col; _sortDir = -1; }
  const numeric = ['balance_total', 'balance_real', 'last_deposit_amount', 'check_count', 'cards_count'];
  const text    = ['email', 'status', 'grade', 'locked_by'];
  state.rows.sort((a, b) => {
    if (text.includes(col)) {
      const av = String(a[col] || '').toLowerCase();
      const bv = String(b[col] || '').toLowerCase();
      return av.localeCompare(bv) * _sortDir;
    }
    const av = numeric.includes(col) ? (a[col] || 0) : (parseTs(a[col] || '').getTime() || 0);
    const bv = numeric.includes(col) ? (b[col] || 0) : (parseTs(b[col] || '').getTime() || 0);
    return (av - bv) * _sortDir;
  });
  state.page = 1;
  renderTable();
}

const $ = sel => document.querySelector(sel);
const $$ = sel => document.querySelectorAll(sel);

const fmtMoney = v => `$${(v || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Cuenta regresiva hacia un timestamp ISO. Devuelve {text, expired, urgent}.
const fmtUntil = ts => {
  if (!ts || ts === 'N/A') return null;
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return null;
  const diff = (d.getTime() - Date.now()) / 1000;
  if (diff <= 0) return { text: 'venció', expired: true, urgent: true };
  if (diff < 60) return { text: `${Math.floor(diff)}s`, expired: false, urgent: true };
  if (diff < 3600) return { text: `${Math.floor(diff/60)}m`, expired: false, urgent: diff < 600 };
  if (diff < 86400) {
    const h = Math.floor(diff/3600), m = Math.floor((diff%3600)/60);
    return { text: m ? `${h}h ${m}m` : `${h}h`, expired: false, urgent: false };
  }
  return { text: `${Math.floor(diff/86400)}d`, expired: false, urgent: false };
};

const parseTs = ts => {
  if (!ts || ts === 'N/A') return new Date(NaN);
  const mx = ts.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (mx) { const [, dd, mm, yyyy, h, mi, ss] = mx; return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +(ss || 0)); }
  const iso = ts.match(/^(\d{4})-(\d{2})-(\d{2})[\sT](\d{2}):(\d{2}):(\d{2})/);
  if (iso) { const [, yyyy, mm, dd, h, mi, ss] = iso; return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +ss); }
  return new Date(ts);
};
const fmtAgo = ts => {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return '—';
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 0) return '—';
  if (diff < 60) return `${Math.floor(diff)}s`;
  if (diff < 3600) return `${Math.floor(diff/60)}m`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h`;
  return `${Math.floor(diff/86400)}d`;
};
// Fecha + hora absoluta (para bitácora persistente — saber qué hiciste antier)
const fmtAbs = ts => {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return '';
  const sameDay = d.toDateString() === new Date().toDateString();
  const opts = sameDay
    ? { hour: '2-digit', minute: '2-digit', hour12: false }
    : { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false };
  return d.toLocaleString('es-MX', opts).replace('.', '');
};
// Fecha con año (para historial de transacciones donde 673d necesitas saber 2023)
const fmtAbsYear = ts => {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return '';
  const sameYear = d.getFullYear() === new Date().getFullYear();
  const opts = sameYear
    ? { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }
    : { day: '2-digit', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false };
  return d.toLocaleString('es-MX', opts).replace(/\./g, '');
};
const gradeClass = g => ({ 'A+': 'Aplus', A: 'A', B: 'B', C: 'C', D: 'D' })[g] || 'U';

// ─── CURP calculator (estimado, no oficial — homoclave queda como X+verif) ───
const _CURP_STATES = {
  // claves CURP oficiales (2 letras) — busca substring case-insensitive en address
  'AGUASCALIENTES': 'AS', 'BAJA CALIFORNIA SUR': 'BS', 'BAJA CALIFORNIA': 'BC',
  'CAMPECHE': 'CC', 'CHIAPAS': 'CS', 'CHIHUAHUA': 'CH',
  'CIUDAD DE MEXICO': 'DF', 'DISTRITO FEDERAL': 'DF', 'CDMX': 'DF', 'D.F.': 'DF',
  'COAHUILA': 'CL', 'COLIMA': 'CM', 'DURANGO': 'DG', 'GUANAJUATO': 'GT',
  'GUERRERO': 'GR', 'HIDALGO': 'HG', 'JALISCO': 'JC', 'ESTADO DE MEXICO': 'MC',
  'EDOMEX': 'MC', 'EDO. DE MEXICO': 'MC', 'EDO. MEX': 'MC',
  'MICHOACAN': 'MN', 'MORELOS': 'MS', 'NAYARIT': 'NT', 'NUEVO LEON': 'NL',
  'OAXACA': 'OC', 'PUEBLA': 'PL', 'QUERETARO': 'QT', 'QUINTANA ROO': 'QR',
  'SAN LUIS POTOSI': 'SP', 'S.L.P': 'SP', 'SLP': 'SP',
  'SINALOA': 'SL', 'SONORA': 'SR', 'TABASCO': 'TC', 'TAMAULIPAS': 'TS',
  'TLAXCALA': 'TL', 'VERACRUZ': 'VZ', 'YUCATAN': 'YN', 'ZACATECAS': 'ZS',
};
const _CURP_VOWELS = 'AEIOU';
const _CURP_CONS = 'BCDFGHJKLMNÑPQRSTVWXYZ';
const _CURP_BAD_WORDS = new Set(['BACA','BAKA','BUEI','BUEY','CACA','CACO','CAGA','CAGO','CAKA','CAKO','COGE','COGI','COJA','COJE','COJI','COJO','COLA','CULO','FALO','FETO','GETA','GUEI','GUEY','JETA','JOTO','KACA','KACO','KAGA','KAGO','KAKA','KAKO','KOGE','KOGI','KOJA','KOJE','KOJI','KOJO','KOLA','KULO','LILO','LOCA','LOCO','LOKA','LOKO','MAME','MAMO','MEAR','MEAS','MEON','MIAR','MION','MOCO','MOKO','MULA','MULO','NACA','NACO','PEDA','PEDO','PENE','PIPI','PITO','POPO','PUTA','PUTO','QULO','RATA','ROBA','ROBE','ROBO','RUIN','SENO','TETA','VACA','VAGA','VAGO','VAKA','VUEI','VUEY','WUEI','WUEY']);
const _CURP_FIRST_NAME_SKIP = new Set(['JOSE', 'MARIA', 'MA.', 'MA', 'J.', 'J']);

function _normalizeName(s) {
  if (!s) return '';
  // Quita acentos, ñ→Ñ se queda
  return s.toUpperCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^A-ZÑ\s]/g, ' ')
    .replace(/\s+/g, ' ').trim();
}
// Partículas que RENAPO ignora en apellidos (DA, DE, DEL, etc)
const _CURP_PARTICLES = new Set(['DA','DAS','DE','DEL','DER','DI','DIE','DD','EL','LA','LAS','LE','LES','LO','LOS','MAC','MC','VAN','VON','Y']);

function _stripParticles(tokens) {
  // Elimina partículas iniciales del componente (apellido)
  while (tokens.length > 1 && _CURP_PARTICLES.has(tokens[0])) tokens.shift();
  return tokens.join(' ');
}

function _splitFullname(fullname) {
  // BetMexico guarda "Nombre(s) Apellido1 Apellido2" — pero apellidos
  // compuestos (DE LA CRUZ, DEL VALLE) requieren manejo especial.
  const all = _normalizeName(fullname).split(' ').filter(Boolean);
  if (all.length === 0) return null;
  if (all.length === 1) return { nombre: all[0], ap1: '', ap2: '' };
  if (all.length === 2) return { nombre: all[0], ap1: all[1], ap2: '' };

  // Walk desde el final agarrando los últimos 2 grupos (apellidos)
  // Un grupo termina cuando encuentra una palabra que NO es partícula.
  // ej. "JUAN PEREZ DE LA CRUZ" → nombre=JUAN, ap1=PEREZ, ap2=DE LA CRUZ
  // ej. "MARIA DEL CARMEN LOPEZ HERNANDEZ" → nombre=MARIA DEL CARMEN, ap1=LOPEZ, ap2=HERNANDEZ
  // Heurística simple: tomar último token + cualquier partícula previa = ap2.
  // Después siguiente token + partículas = ap1. El resto = nombre.
  let i = all.length - 1;
  // ap2: token + partículas hacia atrás
  let ap2End = i;
  while (i > 0 && _CURP_PARTICLES.has(all[i - 1])) i--;
  const ap2Tokens = all.slice(i, ap2End + 1);
  i--;
  // ap1
  let ap1End = i;
  while (i > 0 && _CURP_PARTICLES.has(all[i - 1])) i--;
  const ap1Tokens = i >= 0 ? all.slice(i, ap1End + 1) : [];
  // nombre: lo que queda
  let nombreTokens = i > 0 ? all.slice(0, i) : [];
  // Si el primer nombre es José/María y hay más, usar el siguiente
  if (nombreTokens.length > 1 && _CURP_FIRST_NAME_SKIP.has(nombreTokens[0])) {
    nombreTokens = nombreTokens.slice(1);
  }
  // Saltar partículas tipo "DEL/DE LA" entre nombres (María DEL Carmen → Carmen)
  while (nombreTokens.length > 1 && _CURP_PARTICLES.has(nombreTokens[0])) {
    nombreTokens = nombreTokens.slice(1);
  }
  return {
    nombre: (nombreTokens[0] || ''),  // solo PRIMER nombre real
    ap1: _stripParticles(ap1Tokens),
    ap2: _stripParticles(ap2Tokens),
  };
}

function _firstInternalVowel(s) {
  if (!s) return 'X';
  for (let i = 1; i < s.length; i++) if (_CURP_VOWELS.includes(s[i])) return s[i];
  return 'X';
}
function _firstInternalConsonant(s) {
  if (!s) return 'X';
  for (let i = 1; i < s.length; i++) {
    const c = s[i];
    // Ñ no cuenta como consonante para CURP — se busca otra
    if (_CURP_CONS.includes(c)) return c;
  }
  return 'X';
}
// Códigos cortos de estados para detección por sigla (NL, JC, DF, etc.)
const _CURP_STATE_CODES = ['AS','BC','BS','CC','CL','CM','CS','CH','DF','DG','GT','GR','HG','JC','MC','MN','MS','NT','NL','OC','PL','QT','QR','SP','SL','SR','TC','TS','TL','VZ','YN','ZS'];
// Aliases comunes de siglas usadas en direcciones
const _CURP_CODE_ALIASES = {
  'NL': 'NL', 'JAL': 'JC', 'EDOMEX': 'MC', 'EDO MEX': 'MC',
  'BCN': 'BC', 'BCS': 'BS', 'CDMX': 'DF', 'DF': 'DF',
  'AGS': 'AS', 'CHIH': 'CH', 'CHIS': 'CS', 'COAH': 'CL',
  'DGO': 'DG', 'GTO': 'GT', 'GRO': 'GR', 'HGO': 'HG',
  'MICH': 'MN', 'MOR': 'MS', 'NAY': 'NT', 'OAX': 'OC',
  'PUE': 'PL', 'QRO': 'QT', 'SLP': 'SP', 'SIN': 'SL',
  'SON': 'SR', 'TAB': 'TC', 'TAMS': 'TS', 'TAMPS': 'TS',
  'TLAX': 'TL', 'VER': 'VZ', 'YUC': 'YN', 'ZAC': 'ZS',
  'CAMP': 'CC', 'MEX': 'MC', 'MEXICO': 'MC', 'EDO DE MEXICO': 'MC',
  'QROO': 'QR', 'Q ROO': 'QR',
};

function _detectStateCode(address) {
  if (!address) return 'NE';
  const norm = _normalizeName(address).replace(/\./g, '');
  const aSpaced = ' ' + norm + ' ';
  // 1. Match nombre completo del estado
  for (const [key, code] of Object.entries(_CURP_STATES)) {
    const k = key.replace(/\./g, '');
    if (aSpaced.includes(' ' + k + ' ') || aSpaced.endsWith(' ' + k)) return code;
  }
  // 2. Match aliases comunes (SLP, NL, EDOMEX, etc) — token-bounded
  const tokens = norm.split(/\s+/);
  for (const tok of tokens) {
    if (_CURP_CODE_ALIASES[tok]) return _CURP_CODE_ALIASES[tok];
  }
  // 3. Match siglas tipo "S.L.P" → "S L P" → reconstrucción de iniciales
  // Busca secuencias de 2-4 iniciales separadas por puntos/espacios
  const initialsMatches = address.toUpperCase().match(/\b[A-Z](?:\.|\s+)[A-Z](?:\.|\s+)?[A-Z]?\.?/g) || [];
  for (const m of initialsMatches) {
    const compact = m.replace(/[^A-Z]/g, '');
    if (_CURP_CODE_ALIASES[compact]) return _CURP_CODE_ALIASES[compact];
    if (_CURP_STATE_CODES.includes(compact)) return compact;
  }
  return 'NE';
}
function _inferSex(nombre) {
  // Heurística: nombres femeninos comunes; si termina en 'A' es femenino mayoría;
  // por default H si no se decide
  const FEM = new Set(['ANA','MARIA','MARIANA','SOFIA','LUCIA','ELENA','LAURA','SARA','ADRIANA','ANDREA','ANGELA','ANGELES','BEATRIZ','CARMEN','CECILIA','CLAUDIA','CRISTINA','DANIELA','DIANA','DOLORES','DULCE','ELIZABETH','ESPERANZA','FATIMA','FRANCISCA','GABRIELA','GLORIA','GUADALUPE','HORTENSIA','INES','IRENE','IRMA','ISABEL','JAZMIN','JESSICA','JIMENA','JOSEFINA','JUANA','JULIANA','JULIA','KARLA','LETICIA','LIDIA','LILIANA','LILY','LIZ','LUPITA','MAGDALENA','MARGARITA','MARTHA','MARIBEL','MELISSA','MERCEDES','MICHELLE','MIRIAM','MONICA','NANCY','NATALIA','NORMA','OLIVIA','PALOMA','PAOLA','PATRICIA','PAULA','PILAR','PRISCILA','RAQUEL','REBECA','ROCIO','ROSA','ROSARIO','SANDRA','SILVIA','SUSANA','TANIA','TERESA','VALERIA','VANESSA','VERONICA','VICTORIA','VIRGINIA','XIMENA','YESENIA','YOLANDA','ZULEMA']);
  if (!nombre) return 'X';
  if (FEM.has(nombre)) return 'M';
  // Termina en A pero no es nombre conocido → asumir M
  if (nombre.endsWith('A')) return 'M';
  return 'H';
}
function _curpVerifier(curp17) {
  // Algoritmo oficial: cada char tiene un valor (0-9 / A-Z), suma ponderada, resta 10.
  const map = '0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ';
  let sum = 0;
  for (let i = 0; i < 17; i++) {
    const v = map.indexOf(curp17[i]);
    if (v < 0) return '0';
    sum += v * (18 - i);
  }
  const ver = (10 - (sum % 10)) % 10;
  return String(ver);
}
function computeCurp(fullname, birthdate, address, sexOverride) {
  const split = _splitFullname(fullname);
  if (!split || !split.ap1 || !split.nombre || !birthdate) return null;
  // Fecha: acepta YYYY-MM-DD o YYYY-MM-DDT...
  const m = birthdate.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const [, yyyy, mm, dd] = m;
  const yy = yyyy.slice(2);

  // Pos 1: primera letra del primer apellido. Si es Ñ → X (regla RENAPO).
  let p1 = split.ap1[0] || 'X';
  if (p1 === 'Ñ') p1 = 'X';
  // Pos 2: primera vocal interna del primer apellido
  let p2 = _firstInternalVowel(split.ap1);
  // Pos 3: primera letra del segundo apellido (X si no hay)
  let p3 = split.ap2 ? (split.ap2[0] || 'X') : 'X';
  if (p3 === 'Ñ') p3 = 'X';
  // Pos 4: primera letra del nombre (de pila)
  let p4 = split.nombre[0] || 'X';
  if (p4 === 'Ñ') p4 = 'X';

  // Si las primeras 4 forman palabra inconveniente, pos 2 → X
  let prefix = p1 + p2 + p3 + p4;
  if (_CURP_BAD_WORDS.has(prefix)) prefix = p1 + 'X' + p3 + p4;

  const sex = (sexOverride === 'H' || sexOverride === 'M')
    ? sexOverride : _inferSex(split.nombre);
  const state = _detectStateCode(address);
  const c1 = _firstInternalConsonant(split.ap1);
  const c2 = split.ap2 ? _firstInternalConsonant(split.ap2) : 'X';
  const c3 = _firstInternalConsonant(split.nombre);

  // Pos 17: '0' si nació <2000, 'A' si ≥2000 (default RENAPO).
  // El contador sube por homonimia (0,1,2... o A,B,C...) pero la mayoría queda en 0/A.
  const homo = parseInt(yyyy, 10) >= 2000 ? 'A' : '0';
  const curp17 = `${prefix}${yy}${mm}${dd}${sex}${state}${c1}${c2}${c3}${homo}`;
  const ver = _curpVerifier(curp17);
  return curp17 + ver;
}
// Tiers de saldo:
//   ≥ $50      → hot   (verde radiactivo + glow + flicker)
//   $10–$49.99 → mid   (blanco)
//   < $10      → low   (gris)
const balanceCls = v => {
  const n = Number(v) || 0;
  if (n >= 50) return 'hot';
  if (n >= 10) return 'mid';
  return 'low';
};
function getVisible() {
  if (state.refreshMode) return state.refreshMode.updatedRows;
  return state.filterInUse ? state.rows.filter(r => r.locked_by) : state.rows;
}

function getPaged() {
  const v = getVisible();
  const totalPages = Math.max(1, Math.ceil(v.length / state.pageSize));
  if (state.page > totalPages) state.page = totalPages;
  const start = (state.page - 1) * state.pageSize;
  return { rows: v.slice(start, start + state.pageSize), total: v.length, totalPages };
}

// ─── toast ───
let _toastTimer = null;
function toast(msg, kind = '') {
  const el = $('#toast');
  el.className = `toast ${kind}`;
  el.textContent = msg;
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add('hidden'), 2500);
}

// ─── greeting + frase ───
function tickGreeting() {
  const now = new Date();
  $('#sbDate').textContent = now.toLocaleDateString('es-MX', { weekday: 'short', day: '2-digit', month: 'short' }).replace('.', '');
  $('#sbTime').textContent = now.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
}
let fraseIdx = Math.floor(Math.random() * FRASES.length);
function tickFrase() {
  $('#fraseTxt').textContent = `"${FRASES[fraseIdx]}"`;
  $('#fraseTxt').style.animation = 'none';
  void $('#fraseTxt').offsetWidth;
  $('#fraseTxt').style.animation = 'fraseFade 600ms ease-out';
  fraseIdx = (fraseIdx + 1) % FRASES.length;
}

// ─── auth/me bootstrap ───
async function loadMe() {
  const r = await fetch('/api/auth/me').catch(() => null);
  if (!r || r.status === 401) { window.location.href = '/login'; return; }
  const me = await r.json();
  state.user = me;
  $('#sbGreetName').textContent = me.username || '—';
  $('#sbUserName').textContent = me.username || '—';
  $('#sbUserRole').textContent = me.role || '—';
  $('#sbUserAv').textContent = (me.username || '··').slice(0, 2).toUpperCase();
  // Roles
  const isSuper = me.role === 'superadmin';
  const isAdmin = me.role === 'admin' || isSuper;
  const isUser  = !isAdmin;

  // El strip (#adminPanel) ahora es VISIBLE a operadores con contenido por rol.
  // `no-kpis` se mantiene SOLO para ocultar los filtros SA-only del topbar
  // (status/grade/view) — ver style.css §no-kpis. La regla que ocultaba el strip
  // (body.no-kpis #adminPanel) se eliminó en el CSS, así que el strip ya se muestra.
  if (!isSuper) {
    document.body.classList.add('no-kpis');
  }
  // Vista única Detallada para todos — el toggle Simple/Detallada se eliminó.
  state.view = 'detail';
  // Logs y Health solo superadmin
  if (!isSuper) {
    $('#navLogs').style.display = 'none';
    $('#navHealth').style.display = 'none';
  }
  // BINes (inteligencia de tarjetas) solo superadmin
  if (!isSuper) {
    const nb = $('#navBinStats'); if (nb) nb.style.display = 'none';
  }
  // Online (roster de operadores) solo superadmin — los pares NO se ven entre sí (D7)
  if (!isSuper) {
    const so = document.querySelector('.sb-online'); if (so) so.style.display = 'none';
  }
  // Pool solo superadmin
  if (!isSuper) {
    const np = $('#navPool'); if (np) np.style.display = 'none';
    const na = $('#navAdmin'); if (na) na.style.display = 'none';
  }
  // Liberar (asignar a otros) solo superadmin — el "admin" NO debe verlo (vista secreta)
  if (!isSuper) {
    $('#cmdRelease').closest('.cmd-release-wrap').style.display = 'none';
  }
  // Trastienda solo SA (es feature de dosificación tuya)
  if (!isSuper) {
    $('#cmdTrastienda').style.display = 'none';
  }
  // Vista premium del sidebar: admin solo ve xCAPTCHA + Proxies (oculta WSai y En uso)
  if (!isSuper) {
    const wsaiRow = $('#stWsai')?.closest('div');
    if (wsaiRow) wsaiRow.style.display = 'none';
    const inUseRow = $('#stInUse')?.closest('div');
    if (inUseRow) inUseRow.style.display = 'none';
  }
  // Page sizes según rol
  const sizes = isSuper ? [20, 50, 100, 200, 500] : [20, 30, 50];
  const sel = $('#pageSize');
  sel.innerHTML = sizes.map(n => `<option value="${n}">${n}</option>`).join('');
  state.pageSize = sizes[0];
  sel.value = String(state.pageSize);
}

// ─── data fetchers ───
async function fetchAccounts() {
  const url = new URL('/api/accounts', location.origin);
  url.searchParams.set('status', state.status);
  if (state.grade) url.searchParams.set('grade', state.grade);
  if (searchQuery) url.searchParams.set('q', searchQuery);
  if (state.cardsOnly) url.searchParams.set('cards_only', 'true');
  url.searchParams.set('limit', '500');
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
async function fetchStats() {
  const r = await fetch('/api/stats');
  if (!r.ok) return null;
  return r.json();
}
async function fetchCombos(ids) {
  const r = await fetch('/api/accounts/combos', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ ids }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ─── tabla ───
function renderTable() {
  const paged = getPaged();
  const visible = paged.rows;
  const t = $('#accTable');
  // Calcula ancho del combo más largo (en chars) — fija la columna
  const maxComboLen = visible.reduce((m, r) => Math.max(m, (r.email||'').length + 1 + (r.password||'').length), 28);
  // +4ch de margen — justo para no truncar, menos desperdicio horizontal
  t.style.setProperty('--combo-width', `${Math.min(maxComboLen + 4, 60)}ch`);
  const _th = (col, label, cls = '') => {
    const on = _sortCol === col;
    const ic = on ? (_sortDir === 1 ? ' ↑' : ' ↓') : '';
    return `<th class="th-sort${on ? ' sort-on' : ''} ${cls}" data-sort="${col}">${label}${ic}</th>`;
  };
  const cols = state.view === 'simple'
    ? `<tr>
        <th class="grade-bar-th"></th>
        <th class="sel-cell"><input type="checkbox" id="selAll"></th>
        ${_th('balance_total','Saldo','num')}${_th('email','Cuenta')}
        <th class="row-details-th"></th>
        ${_th('last_deposit_date','Últ. depósito')}
        <th class="row-icons-th"></th>
      </tr>`
    : `<tr>
        <th class="grade-bar-th"></th>
        <th class="sel-cell"><input type="checkbox" id="selAll"></th>
        ${_th('balance_total','Saldo','num')}${_th('email','Cuenta')}
        <th class="row-details-th"></th>
        ${_th('last_deposit_date','Últ. depósito')}
        ${_th('last_checked_at','Últ. check')}${_th('check_count','Checks','num')}
        <th class="row-icons-th"></th>
      </tr>`;
  const thead = t.querySelector('thead');
  thead.innerHTML = cols;
  // Listeners directos en cada th-sort (evita problemas de delegation)
  thead.querySelectorAll('th.th-sort').forEach(th => {
    th.addEventListener('click', ev => {
      ev.stopPropagation();
      sortRows(th.dataset.sort);
    });
  });

  const colspan = state.view === 'simple' ? 7 : 9;
  const rowsHtml = visible.map(r => {
    const g = gradeClass(r.grade);
    const until = r.locked_by ? fmtUntil(r.locked_until) : null;
    const lockedCls = r.locked_by ? (until?.expired ? 'row-locked row-lock-expired' : 'row-locked') : '';
    const selCls = selectedIds.has(r.id) ? 'row-sel' : '';
    const checked = selectedIds.has(r.id) ? 'checked' : '';
    const dep = r.last_deposit_amount
      ? `<b>${fmtMoney(r.last_deposit_amount)}</b><span class="ago">${fmtAgo(r.last_deposit_date)}</span>`
      : '<span class="dim">sin dep.</span>';
    const combo = `${r.email}:${r.password || ''}`;
    const opCol = r.locked_color || 'accent';
    const opClass = r.locked_by ? `op-row-${opCol}` : '';
    const trasClass = r.published_to_pool === 0 ? 'row-trastienda' : '';
    const trClasses = `r-grade-${g} ${lockedCls} ${selCls} ${opClass} ${trasClass}`.trim();
    const lockChip = r.locked_by
      ? `<span class="lock-chip op-${esc(opCol)} ${until?.expired ? 'expired' : ''}" title="Lockeada por ${esc(r.locked_by)}${until ? ` · ${until.expired ? 'vencido' : `vence en ${until.text}`}` : ''}">🔒 ${esc(r.locked_by)}${until && !until.expired ? ` <span class="lock-chip-time dim">${until.text}</span>` : ''}</span>`
      : '';
    const isSA = state.user?.role === 'superadmin';
    const trTitle = isSA ? `Grade ${esc(r.grade) || '?'}` : '';
    // Iconos de fila: 💳 (tarjetas), 📝 (notas), siempre + (quick add), 📌 (marcador) + botón Detalles
    const hasCards = (r.cards_count || 0) > 0;
    const hasNotes = (r.notes_count || 0) > 0;
    const isMarked = markedSet.has(r.email);
    let iconsHtml = '';
    if (hasCards) {
      iconsHtml += `<button class="row-ic ic-cards" data-id="${r.id}" data-email="${esc(r.email)}" title="${r.cards_count} tarjeta${r.cards_count>1?'s':''}">💳<sup>${r.cards_count}</sup></button>`;
    }
    if (hasNotes) {
      iconsHtml += `<button class="row-ic ic-notes" data-id="${r.id}" data-email="${esc(r.email)}" title="${r.notes_count} nota${r.notes_count>1?'s':''}">📝<sup>${r.notes_count}</sup></button>`;
    }
    iconsHtml += `<button class="row-ic ic-add" data-id="${r.id}" data-email="${esc(r.email)}" title="Añadir nota rápida">+ Nota</button>`;
    iconsHtml += `<button class="row-ic ic-mark${isMarked?' on':''}" data-mark-email="${esc(r.email)}" title="${isMarked?'Quitar marca':'Fijar para después'}">📌</button>`;

    // Botón "Detalles" premium — único acceso al modal
    const detailsBtn = `<button class="row-details" data-id="${r.id}" title="Ver detalles completos de la cuenta">
      <span class="row-details-text">detalles</span>
      <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.938a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z" clip-rule="evenodd"/>
      </svg>
    </button>`;

    // Botón ↻ por fila — actualiza SOLO esta cuenta al instante
    const refreshOneBtn = `<button class="row-refresh-one" data-id="${r.id}" title="Actualizar SOLO esta cuenta (login fresh + fetch live)">↻</button>`;
    if (state.view === 'simple') {
      return `<tr class="${trClasses}" data-id="${r.id}" title="${trTitle || ''}">
        <td class="grade-bar-cell" title="Grade ${esc(r.grade) || '?'}"></td>
        <td class="sel-cell" title="Click selecciona la fila"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
        <td class="num" title="Saldo total disponible"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span>${refreshOneBtn}</td>
        <td class="combo d-copy" data-combo="${esc(combo)}" title="Click para copiar combo"><b data-id="${r.id}" data-combo="${esc(combo)}">${esc(combo)}</b>${lockChip}</td>
        <td class="row-details-cell">${detailsBtn}</td>
        <td class="dep" title="Último depósito hecho">${dep}</td>
        <td class="row-icons">${iconsHtml}</td>
      </tr>`;
    }
    return `<tr class="${trClasses}" data-id="${r.id}" title="${trTitle || ''}">
      <td class="grade-bar-cell" title="Grade ${esc(r.grade) || '?'}"></td>
      <td class="sel-cell" title="Click selecciona la fila"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
      <td class="num" title="Saldo total disponible"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span>${refreshOneBtn}</td>
      <td class="combo d-copy" data-combo="${esc(combo)}" title="Click para copiar combo"><b data-id="${r.id}" data-combo="${esc(combo)}">${esc(combo)}</b></td>
      <td class="row-details-cell">${detailsBtn}</td>
      <td class="dep" title="Último depósito hecho">${dep}</td>
      <td class="dep dim" title="Cuándo se actualizó por última vez">${fmtAgo(r.last_checked_at)}</td>
      <td class="num" title="Total de veces actualizada">${r.check_count || 0}</td>
      <td class="row-icons">${iconsHtml}</td>
    </tr>`;
  }).join('');

  t.querySelector('tbody').innerHTML = rowsHtml || `<tr><td colspan="${colspan}" class="loading">Sin cuentas</td></tr>`;

  // Re-inyecta el panel de detalle inline (acordeón) tras reconstruir el tbody.
  // renderTable reescribe innerHTML completo en cada tick SSE/sort/filtro, así
  // que el acordeón sobrevive re-renders re-inyectándose desde expandedAccountId.
  _injectExpandedDetail();

  // selectAll en sync con visible
  const allChecked = visible.length > 0 && visible.every(r => selectedIds.has(r.id));
  const selAll = $('#selAll');
  if (selAll) selAll.checked = allChecked;

  renderPagination(paged);
  updateCmdBar();
  _updateResetBtn();
}

function renderPagination(paged) {
  $('#pbVisibleCount').textContent = `${paged.rows.length} de ${paged.total}`;
  const c = $('#pbPages');
  if (paged.totalPages <= 1) { c.innerHTML = ''; return; }
  const cur = state.page, last = paged.totalPages;
  // Mostrar al menos 10 números visibles + 1 y last + ellipsis
  const WINDOW = 10;
  const range = new Set([1, last]);
  // Ventana centrada en cur
  let start = Math.max(2, cur - Math.floor(WINDOW / 2));
  let end = Math.min(last - 1, start + WINDOW - 1);
  // Si chocamos con el final, expandir hacia atrás
  start = Math.max(2, end - WINDOW + 1);
  for (let i = start; i <= end; i++) range.add(i);
  const uniq = [...range].sort((a, b) => a - b);
  let html = `<button class="pg-btn" data-pg="prev" ${cur === 1 ? 'disabled' : ''}>‹</button>`;
  let prev = 0;
  for (const p of uniq) {
    if (p - prev > 1) html += `<span class="pg-gap">…</span>`;
    html += `<button class="pg-btn ${p === cur ? 'on' : ''}" data-pg="${p}">${p}</button>`;
    prev = p;
  }
  html += `<button class="pg-btn" data-pg="next" ${cur === last ? 'disabled' : ''}>›</button>`;
  c.innerHTML = html;
}

function renderStats(s) {
  if (!s) return;
  const visible = getVisible();
  $('#navCount').textContent = s.live;
  $('#countLabel').textContent = `${visible.length} / ${s.live.toLocaleString()}`;
  $('#stInUse').textContent = s.inUse;
}

// ─── command bar ───
function updateCmdBar() {
  const n = selectedIds.size;
  const bar = $('#cmdBar');
  $('#cmdSelCount').textContent = n;
  // Sync con drawer en modo Multi: cuando el operador tickea/destickea cuentas
  // en la tabla atrás (drawer empuja, no bloquea), reflejamos en _depAccountIds
  // para que renderMultiAccounts se actualice live. Solo si NO hay misión multi
  // corriendo (durante un run, las cuentas están fijas).
  if (_depDrawerOpen && _depMode === 'multi' && !_depMmRunId) {
    _depAccountIds = [...selectedIds].slice(0, 5);
    try { renderMultiAccounts(); } catch {}
  }
  if (n === 0) { bar.classList.add('hidden'); return; }
  bar.classList.remove('hidden');

  // sumas
  const selRows = state.rows.filter(r => selectedIds.has(r.id));
  const totalBal = selRows.reduce((s, r) => s + (r.balance_total || 0), 0);
  $('#cmdStats').textContent = `Σ ${fmtMoney(totalBal)}`;

  // Depositar visible 1-5 cuentas (>5 → tope del matchmaker)
  $('#cmdDeposit').style.display = (n >= 1 && n <= 5) ? '' : 'none';
  $('#cmdDeposit').textContent = n === 1 ? '💳 Depositar' : `💳 Depositar (${n})`;

  // Label dinámico: claro qué hace según estado
  const tBtn = $('#cmdTrastienda');
  if (tBtn && tBtn.style.display !== 'none') {
    const selRowsArr = state.rows.filter(r => selectedIds.has(r.id));
    const allPub = selRowsArr.every(r => r.published_to_pool !== 0);
    const someHidden = selRowsArr.some(r => r.published_to_pool === 0);
    if (someHidden) {
      tBtn.innerHTML = '🎁 Publicar a Pool';
      tBtn.title = 'Hacer visibles a los operadores';
      tBtn.classList.add('cmd-btn-hl');
    } else {
      tBtn.innerHTML = '📤 Quitar de Pool';
      tBtn.title = 'Ocultar de la vista de operadores';
      tBtn.classList.remove('cmd-btn-hl');
    }
  }
}

async function copySelectedCombos() {
  if (selectedIds.size === 0) { toast('Nada seleccionado', 'error'); return; }
  try {
    const data = await fetchCombos(Array.from(selectedIds));
    const txt = data.combos.map(c => `${c.email}:${c.password}`).join('\n');
    await navigator.clipboard.writeText(txt);
    toast(`✓ ${data.combos.length} combo${data.combos.length > 1 ? 's' : ''} copiado${data.combos.length > 1 ? 's' : ''}`, 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function bulkLock() {
  if (selectedIds.size === 0) return;
  const op = state.user?.username || 'op';
  let ok = 0, fail = 0;
  for (const id of selectedIds) {
    const r = await fetch(`/api/accounts/${id}/lock`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ operator: op, hours: state.lockHours }),
    });
    if (r.ok) ok++; else fail++;
  }
  toast(`🔒 Lock ${state.lockHours}h: ${ok} ok${fail ? `, ${fail} fallidos` : ''}`, fail ? 'error' : 'success');
  await reload();
}
async function bulkUnlock() {
  if (selectedIds.size === 0) return;
  let ok = 0, fail = 0;
  for (const id of selectedIds) {
    const r = await fetch(`/api/accounts/${id}/unlock`, { method: 'POST' });
    if (r.ok) ok++; else fail++;
  }
  toast(`🔓 Unlock: ${ok} ok${fail ? `, ${fail} fallidos` : ''}`, fail ? 'error' : 'success');
  await reload();
}

async function bulkTrastienda() {
  if (selectedIds.size === 0) return;
  const sel = state.rows.filter(r => selectedIds.has(r.id));
  // Decidir dirección: si todas están publicadas → a trastienda; si no → a pool.
  const allPublished = sel.every(r => r.published_to_pool !== 0);
  const publish = !allPublished;  // si todas públicas, las ocultamos; si no, las publicamos
  try {
    const r = await fetch('/api/accounts/publish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ids: Array.from(selectedIds), publish }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    toast(publish
      ? `📥 ${data.changed} a la pool (visibles)`
      : `📤 ${data.changed} a trastienda (ocultas)`,
      'success');
    await reload();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

function deselectAll() {
  selectedIds.clear();
  renderTable();
}

// ─── Actividad (event log en vivo) ───
async function fetchActivity() {
  const url = new URL('/api/activity', location.origin);
  url.searchParams.set('limit', '200');
  if (activityFilter.who != null) url.searchParams.set('operator_id', activityFilter.who);
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  return Array.isArray(j) ? j : (j.feed || []);
}

function actionLabel(kind) {
  if (kind === 'deposit') return '💳 Depósito';
  if (kind === 'lock') return '🔒 Lock';
  if (kind === 'unlock') return '🔓 Unlock';
  if (kind === 'note') return '📝 Nota';
  if (kind === 'scheduled') return '⏱️ Scheduled';
  if (kind === 'scheduled_phase') return '⏳ Fase';
  if (kind === 'scheduled_aborted') return '⏱️ Abortado';
  if (kind === 'scheduled_cancelled') return '⏱️ Cancelado';
  if (kind?.startsWith('prewarm_')) return '· login bg';  // auditoría interna, sin ruido
  return kind;
}

// Labels y formato para fases del scheduled (Task 5 deposit-live-progress).
// Compactos, monoespaciados, con emoji de la fase y check/cross del resultado.
function _schedPhaseLabel(name, data) {
  data = data || {};
  const ms = data.duration_ms ? ` <span class="dim">(${data.duration_ms}ms)</span>` : '';
  switch (name) {
    case 'login_start':         return '🔑 Login…';
    case 'login_done':          return (data.ok ? '🔑 ✓' : '🔑 ✗') + ms + (data.from_cache ? ' <span class="dim">cache</span>' : '');
    case 'login_reused':        return '♻️ Sesión reutilizada';
    case 'gateway_begin':       return '📝 Orden…';
    case 'gateway_begin_done':  return (data.ok ? '📝 ✓' : '📝 ✗') + ms + (data.order_id ? ` <span class="dim mono">${esc(String(data.order_id).slice(0, 12))}</span>` : '');
    case 'gateway_submit':      return '💳 Tarjeta…';
    case 'gateway_submit_done': {
      const code = data.result_code || '';
      const tag = data.is_3ds ? '💳 3DS' : (code === 'BANK_APPROVED' ? '💳 ✓' : '💳 ✗');
      return tag + ms + (code ? ` <span class="dim mono">${esc(code)}</span>` : '');
    }
    case 'gateway_check':       return '✓ Verificando…';
    case 'gateway_check_done':  return (data.check_error ? '✓ ✗' : '✓ ✓') + ms;
    case 'done':                return data.success ? '✓ Aprobado' : '✗ Rechazado';
    default:                    return esc(name);
  }
}
function statusPill(e) {
  if (e.kind === 'deposit') {
    const c = e.status === 'approved' ? 'var(--accent)'
            : e.status === 'rejected' ? 'var(--danger)'
            : 'var(--text-muted)';
    return `<span style="color:${c}">${esc(e.status || '—')}</span>${e.reason ? `<span class="dim mono"> · ${esc(e.reason).slice(0, 40)}</span>` : ''}`;
  }
  if (e.kind === 'lock') return `<span class="dim">activo</span>`;
  if (e.kind === 'unlock') return `<span class="dim">liberado</span>`;
  if (e.kind === 'note') return `<span class="dim mono" title="${esc(e.text || '')}">${esc((e.text || '').slice(0, 60))}</span>`;
  if (e.kind === 'scheduled') {
    const ok = !!e.success;
    const col = ok ? 'var(--accent)' : 'var(--danger)';
    const iter = (e.iter != null && e.total != null) ? `<span class="dim mono">${e.iter}/${e.total}</span> ` : '';
    return `${iter}<span style="color:${col}">${ok ? 'aprobado' : 'rechazado'}</span>${e.code ? `<span class="dim mono"> · ${esc(e.code)}</span>` : ''}`;
  }
  if (e.kind === 'scheduled_phase') {
    const iter = (e.iter != null && e.total != null) ? `<span class="dim mono">${e.iter}/${e.total}</span> ` : '';
    const sid = e.sched_id ? `<span class="dim mono"> · ${esc(String(e.sched_id).slice(0, 6))}</span>` : '';
    return `${iter}${_schedPhaseLabel(e.name, e.data)}${sid}`;
  }
  if (e.kind === 'scheduled_retry') {
    const iter = (e.iter != null && e.total != null) ? `<span class="dim mono">${e.iter}/${e.total}</span> ` : '';
    const detail = e.reason || e.code;
    return `${iter}<span style="color:var(--warn,#e0a800)">reintentando</span>${detail ? `<span class="dim mono" title="${esc(e.reason || '')}"> · ${esc(String(detail).slice(0, 48))}</span>` : ''}`;
  }
  if (e.kind === 'scheduled_aborted') {
    const iter = (e.iter != null && e.total != null) ? `<span class="dim mono">${e.iter}/${e.total}</span> ` : '';
    // reason explícito (truncado) si lo hay; cae al code.
    const detail = e.reason || e.code;
    return `${iter}<span style="color:var(--danger)">abortado</span>${detail ? `<span class="dim mono" title="${esc(e.reason || '')}"> · ${esc(String(detail).slice(0, 48))}</span>` : ''}`;
  }
  if (e.kind === 'scheduled_cancelled') return `<span class="dim">cancelado</span>`;
  return '';
}
function _actEventKey(e) {
  // Identifica un evento de manera estable para tracking de "nuevos"
  return `${e.kind}|${e.ts}|${e.who}|${e.target}|${e.amount ?? ''}`;
}
function _actTimeCutoffMs() {
  const t = activityFilter.time;
  if (t === '24h') return 24 * 60 * 60 * 1000;
  if (t === '1h')  return 60 * 60 * 1000;
  if (t === '30m') return 30 * 60 * 1000;
  return null;
}
function getFilteredActivity() {
  const cutoff = _actTimeCutoffMs();
  const now = Date.now();
  const q = (activityFilter.q || '').trim().toLowerCase();
  return activityRows.filter(e => {
    if (activityFilter.kind) {
      if (activityFilter.kind === 'prewarm') return (e.kind || '').startsWith('prewarm_');
      if (e.kind !== activityFilter.kind) return false;
    }
    if (activityFilter.who != null && e.who != activityFilter.who) return false;
    if (cutoff != null) {
      const ts = Date.parse(e.ts || '');
      if (isNaN(ts) || (now - ts) > cutoff) return false;
    }
    if (q) {
      const hay = `${e.who ?? ''} ${e.target ?? ''} ${e.amount ?? ''} ${e.status ?? ''} ${e.text ?? ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}
function _renderActPagination(total) {
  const pages = Math.max(1, Math.ceil(total / activityPageSize));
  if (activityPage > pages) activityPage = pages;
  const wrap = $('#actPbPages');
  if (!wrap) return;
  if (pages <= 1) { wrap.innerHTML = ''; return; }
  // Compact pagination: prev · 1 … (cur-1) cur (cur+1) … last · next
  const btn = (label, page, opts = {}) => {
    const cls = ['pb-btn'];
    if (opts.active) cls.push('on');
    if (opts.disabled) cls.push('disabled');
    return `<button class="${cls.join(' ')}" data-page="${page}" ${opts.disabled ? 'disabled' : ''}>${label}</button>`;
  };
  let html = btn('‹', activityPage - 1, { disabled: activityPage <= 1 });
  const seen = new Set();
  const add = (p) => {
    if (p < 1 || p > pages || seen.has(p)) return '';
    seen.add(p);
    return btn(String(p), p, { active: p === activityPage });
  };
  html += add(1);
  if (activityPage > 3) html += `<span class="pb-gap">…</span>`;
  for (let p = activityPage - 1; p <= activityPage + 1; p++) html += add(p);
  if (activityPage < pages - 2) html += `<span class="pb-gap">…</span>`;
  html += add(pages);
  html += btn('›', activityPage + 1, { disabled: activityPage >= pages });
  wrap.innerHTML = html;
}
function _renderActOpsChips() {
  const wrap = $('#actOpsChips');
  if (!wrap) return;
  // Solo SA ve el filtro por operador; un operador solo ve sus propios eventos
  const isSA = state.user?.role === 'superadmin';
  if (!isSA) { wrap.innerHTML = ''; wrap.style.display = 'none'; return; }
  wrap.style.display = '';
  // Operadores únicos del feed actual con su color (best-effort)
  const seen = new Map();   // who → color
  for (const e of activityRows) {
    if (e.who && !seen.has(e.who)) seen.set(e.who, e.who_color || null);
  }
  const all = `<button class="act-op-chip${activityFilter.who == null ? ' on' : ''}" data-who="" title="Todos los operadores">Todos</button>`;
  const chips = Array.from(seen.entries()).map(([who, color]) => {
    const active = activityFilter.who != null && String(activityFilter.who) === String(who);
    const dot = color ? `<span class="act-op-chip-dot ${esc(color)}"></span>` : '';
    return `<button class="act-op-chip${active ? ' on' : ''}" data-who="${esc(who)}" title="Solo eventos de ${esc(who)}">${dot}${esc(who)}</button>`;
  }).join('');
  wrap.innerHTML = all + chips;
}
// Mapa global email→password para resolver combos fuera de state.rows
let _emailPassMap = {};
async function _loadPassMap() {
  try {
    const r = await fetch('/api/accounts/pass-map');
    if (r.ok) _emailPassMap = await r.json();
  } catch (_) {}
}

// Helper: resuelve email -> "email:password".
// Busca en state.rows (más fresco) y cae en _emailPassMap como fallback.
function _resolveComboFromEmail(email) {
  if (!email) return '';
  const row = (state.rows || []).find(r => r.email === email);
  if (row?.password) return `${row.email}:${row.password}`;
  const pwd = _emailPassMap[email];
  return pwd ? `${email}:${pwd}` : email;
}

// Hora exacta HH:MM a partir de un timestamp (para el feed agrupado)
function _exactHora(ts) {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
}
// Etiqueta de día para cabeceras de grupo: "Hoy", "Ayer", "28 jun"
function _dayLabel(ts) {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return '?';
  const today = new Date(); today.setHours(0,0,0,0);
  const yday  = new Date(today); yday.setDate(today.getDate() - 1);
  const check = new Date(d); check.setHours(0,0,0,0);
  if (check.getTime() === today.getTime()) return 'Hoy';
  if (check.getTime() === yday.getTime())  return 'Ayer';
  return d.toLocaleDateString('es-MX', { day: 'numeric', month: 'short' }).replace('.', '');
}
// Clave de día (YYYY-MM-DD) para agrupar
function _dayKey(ts) {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return 'unknown';
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function renderActivity() {
  const t = $('#actTable');
  // Resetear thead — solo necesitamos espacio para una columna (feed de líneas)
  t.querySelector('thead').innerHTML = '';

  const isSA = state.user?.role === 'superadmin';
  const filtered = getFilteredActivity();
  const total = filtered.length;
  const pages = Math.max(1, Math.ceil(total / activityPageSize));
  if (activityPage > pages) activityPage = pages;
  const start = (activityPage - 1) * activityPageSize;
  const slice = filtered.slice(start, start + activityPageSize);

  $('#actCountLabel').textContent = `${total} evento${total === 1 ? '' : 's'}`;

  if (slice.length === 0) {
    t.querySelector('tbody').innerHTML = '<tr><td colspan="1" class="loading">Sin actividad que coincida con los filtros</td></tr>';
  } else {
    // Agrupar por día (manteniendo orden: newest first)
    const groups = []; // [{label, dayKey, rows:[]}]
    const dayMap  = new Map();
    for (const ev of slice) {
      const dk = _dayKey(ev.ts);
      if (!dayMap.has(dk)) {
        const g = { label: _dayLabel(ev.ts), dayKey: dk, rows: [] };
        groups.push(g);
        dayMap.set(dk, g);
      }
      dayMap.get(dk).rows.push(ev);
    }

    let html = '';
    for (const g of groups) {
      html += `<tr class="act-day-head-row"><td class="act-day-head">${esc(g.label)}</td></tr>`;
      for (const ev of g.rows) {
        const key    = _actEventKey(ev);
        const newCls = _actNewIds.has(key) ? ' act-row-new' : '';
        const c      = ActivityLogic.formatActivityCopy(ev, isSA);
        const email  = String(ev.target || ev.email || '').split(':')[0];
        // Nota: renderizamos c.text con esc() para seguridad
        const noteExtra = (ev.kind === 'note' && !email && isSA && ev.who)
          ? `📝 ${esc(ev.who)} anotó`
          : '';
        const displayText = noteExtra || esc(c.text);
        html += `<tr class="act-line-row act-${esc(ev.kind)}${newCls}" data-evkey="${esc(key)}"><td><div class="act-line act-${esc(c.cls)}" data-open-email="${esc(email)}"><span class="act-ic">${c.icon}</span><span class="act-txt">${displayText}</span><span class="act-time mono dim">${_exactHora(ev.ts)}</span></div></td></tr>`;
        _actNewIds.delete(key);
      }
    }
    t.querySelector('tbody').innerHTML = html;
  }

  // Visible count + pagination
  const from = total === 0 ? 0 : start + 1;
  const to   = Math.min(start + activityPageSize, total);
  const vc   = $('#actVisibleCount');
  if (vc) vc.textContent = total === 0 ? 'sin eventos' : `${from}–${to} de ${total}`;
  _renderActPagination(total);
  _renderActOpsChips();

  // Filtro info (chip)
  const parts = [];
  if (activityFilter.kind) parts.push(activityFilter.kind);
  if (activityFilter.who != null) parts.push(`op:${activityFilter.who}`);
  if (activityFilter.time !== 'all') parts.push(activityFilter.time);
  if (activityFilter.q) parts.push(`"${activityFilter.q.slice(0, 20)}"`);
  $('#actFilterInfo').textContent = parts.length ? parts.join(' · ') : '';
  $('#actClearFilter').style.display = parts.length ? '' : 'none';
}
async function reloadActivity() {
  try {
    activityRows = await fetchActivity();
    renderActivity();
  } catch (e) {
    $('#actTable').querySelector('tbody').innerHTML =
      `<tr><td colspan="1" class="loading" style="color:var(--danger)">Error: ${esc(e.message)}</td></tr>`;
  }
}
function pushActivityEvent(ev) {
  // Insert at top, dedupe-ish, cap 500
  const row = {
    kind: ev.kind, ts: ev.ts, who: ev.who, who_color: ev.who_color,
    target: ev.target, amount: ev.amount, status: ev.status,
    reason: ev.reason, duration_ms: ev.duration_ms, id: ev.id, text: ev.text,
    // Campos para scheduled / scheduled_phase / scheduled_aborted / scheduled_cancelled
    sched_id: ev.sched_id, iter: ev.iter, total: ev.total,
    code: ev.code, success: ev.success,
    name: ev.name, data: ev.data, email: ev.email,
  };
  // Si el evento trae 'email' (scheduled*) pero no 'target', usar email como target
  // para que la columna "Cuenta" del feed muestre el combo y filtros por target funcionen.
  if (!row.target && row.email) row.target = row.email;
  activityRows.unshift(row);
  if (activityRows.length > 500) activityRows.length = 500;
  // Marca como "nuevo" para animación highlight si la fila aparece en pantalla
  _actNewIds.add(_actEventKey(row));
  if (state.section === 'activity') renderActivity();
  renderActivityMarquee();
}

// ─── Marquesina Actividad Live ───
const _MARQUEE_KINDS = new Set([
  'deposit','lock','unlock','unlock_auto','account_cooling','mark','pool_move','critical_error',
]);

async function loadActivityMarquee() {
  try {
    const r = await fetch('/api/activity');
    const data = await r.json();
    activityRows = data.feed || [];
    renderActivityMarquee();
  } catch {}
}

function renderActivityMarquee() {
  const host = document.getElementById('lpActivity');
  if (!host) return;
  const isSA = state.user?.role === 'superadmin';
  const deduped = ActivityLogic.dedupeActivity(activityRows)
    .filter(ev => _MARQUEE_KINDS.has(ev.kind))
    .slice(0, 30);

  const counter = document.getElementById('lpFeedCount');
  if (counter) counter.textContent = deduped.length ? `${deduped.length} eventos` : '—';

  if (deduped.length === 0) {
    host.innerHTML = '<div class="lp-empty dim mono">esperando actividad…</div>';
    return;
  }

  const makeRow = ev => {
    const c = ActivityLogic.formatActivityCopy(ev, isSA);
    const email = String(ev.target || ev.email || '').split(':')[0];
    return `<div class="lp-feed-row lp-feed-${esc(c.cls)} lp-feed-clickable" data-open-email="${esc(email)}" title="Abrir cuenta"><span class="lp-feed-ic">${c.icon}</span><span class="lp-feed-txt">${esc(c.text)}</span><span class="lp-feed-time mono dim">${fmtAgo(ev.ts)}</span></div>`;
  };
  const rowsHtml = deduped.map(makeRow).join('');
  // Duplicar para el loop sin costura (-50% keyframe)
  host.innerHTML = `<div class="lp-ticker-track">${rowsHtml}${rowsHtml}</div>`;
}

async function openAccountByEmail(email) {
  try {
    const r = await fetch('/api/accounts?q=' + encodeURIComponent(email));
    const rows = await r.json();
    const hit = (rows || []).find(x => (x.email || '').toLowerCase() === email.toLowerCase()) || (rows || [])[0];
    if (hit && hit.id != null) { openDetailModal(hit.id); return; }
  } catch {}
  // Fallback: poner el email en el buscador
  const s = document.getElementById('searchInput');
  if (s) { s.value = email; searchQuery = email; reload(); }
}

function _humanizeCritical(ev) {
  if (ev.kind === 'capmonster_low' || (ev.type === 'alert' && (ev.msg || '').toLowerCase().includes('capmonster')))
    return 'Servicio de verificación sin saldo';
  if (ev.kind === 'proxy_down' || (ev.type === 'alert' && (ev.msg || '').toLowerCase().includes('proxy')))
    return 'Problema de conexión con la pasarela';
  if (ev.type === 'health_warning')
    return 'Servicio degradado, reintentando';
  return ev.msg || 'Problema de conexión';
}

// ─── notifications ───
function pushNotif(n) {
  // Filter por destinatario: si la notif tiene target_user, solo el operador
  // dueño la ve. SA siempre ve todas (visibilidad operativa total).
  if (n.target_user != null) {
    const myTg = state.user?.telegram_id;
    const isSA = state.user?.role === 'superadmin';
    const isOwner = String(myTg) === String(n.target_user);
    if (!isSA && !isOwner) return; // no es para mí
  }
  notifications.unshift({ ...n, ts: Date.now(), id: Date.now() + Math.random(), unread: true });
  if (notifications.length > 50) notifications.length = 50;
  renderNotifBadge();
  if (state.section === 'notifications') renderNotifs();
}
function renderNotifBadge() {
  const unread = notifications.filter(n => n.unread).length;
  const badge = $('#bellBadge');
  const navBadge = $('#navNotifBadge');
  if (unread > 0) {
    if (badge) { badge.textContent = unread; badge.classList.remove('hidden'); }
    if (navBadge) navBadge.classList.remove('hidden');
  } else {
    if (badge) badge.classList.add('hidden');
    if (navBadge) navBadge.classList.add('hidden');
  }
}
function renderNotifs() {
  const list = $('#notifList');
  $('#notifCountLabel').textContent = `${notifications.length} eventos`;
  if (notifications.length === 0) {
    list.innerHTML = '<div class="loading">Sin notificaciones.</div>';
    return;
  }
  list.innerHTML = notifications.map(n => {
    const actions = (n.actions || []).map(a => {
      if (a === 'deposit') {
        return `<button class="ni-act ni-act-deposit" data-act="deposit" data-acc-id="${n.account_id ?? ''}" title="Abrir modal de depósito">💳 Depositar</button>`;
      }
      if (a === 'release') {
        return `<button class="ni-act ni-act-release" data-act="release" data-acc-id="${n.account_id ?? ''}" title="Liberar la cuenta para otros operadores">🔓 Liberar</button>`;
      }
      return '';
    }).join('');
    return `
    <div class="notif-item ${n.unread ? 'new' : ''}" data-notif-id="${n.id}">
      <span class="ni-icon">${n.icon || '🔔'}</span>
      <span class="ni-msg">${esc(n.msg)}</span>
      ${actions ? `<span class="ni-actions">${actions}</span>` : ''}
      <span class="ni-time">${fmtAgo(new Date(n.ts).toISOString())}</span>
    </div>`;
  }).join('');
  // marcar como leídas
  notifications.forEach(n => n.unread = false);
  renderNotifBadge();
}

// Navegación rápida: click en cualquier elemento con [data-nav="<section>"]
// lleva a esa sección. Compatible con feed live, header live, alertas, etc.
document.body.addEventListener('click', e => {
  const nav = e.target.closest('[data-nav]');
  if (!nav) return;
  // Si el click cayó en un sub-elemento con data-copy/data-combo, no navegar
  // (el handler global de copia ya hizo stopPropagation, pero por defensa extra).
  if (e.target.closest('[data-copy], [data-combo], button, input, a')) return;
  const target = nav.dataset.nav;
  if (target && typeof showSection === 'function') {
    showSection(target);
  }
});

// Marquesina: click en fila → abrir detalle de cuenta (resuelve email→id)
document.getElementById('lpActivity')?.addEventListener('click', e => {
  const row = e.target.closest('.lp-feed-clickable[data-open-email]');
  if (!row) return;
  e.stopPropagation(); // no burbujear al data-nav del header
  const email = row.dataset.openEmail;
  if (email) openAccountByEmail(email);
});

// Handler de acciones en notifs (botones Depositar / Liberar)
document.body.addEventListener('click', async e => {
  const btn = e.target.closest('.ni-act');
  if (!btn) return;
  e.stopPropagation();
  const act = btn.dataset.act;
  const accId = parseInt(btn.dataset.accId);
  if (!accId) return;
  if (act === 'deposit') {
    if (typeof openDepositModal === 'function') openDepositModal(accId);
    return;
  }
  if (act === 'release') {
    try {
      const r = await fetch(`/api/accounts/${accId}/unlock`, { method: 'POST' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      toast('🔓 Cuenta liberada', 'success');
      // Remover esa notif del feed (sus acciones quedaron sin sentido)
      const item = btn.closest('.notif-item');
      const nid = item?.dataset.notifId;
      if (nid) {
        const idx = notifications.findIndex(n => String(n.id) === String(nid));
        if (idx >= 0) notifications.splice(idx, 1);
      }
      if (state.section === 'notifications') renderNotifs();
      renderNotifBadge();
    } catch (err) {
      toast(`Error: ${err.message}`, 'error');
    }
    return;
  }
});

// ─── navigation ───
let _lastNonNotifSection = 'accounts';
function showSection(name) {
  if (state.section !== 'notifications' && name !== state.section) {
    _lastNonNotifSection = state.section;
  }
  state.section = name;
  $('#accountsMain').style.display = name === 'accounts' ? 'flex' : 'none';
  const poolM = $('#poolMain'); if (poolM) poolM.style.display = name === 'pool' ? 'flex' : 'none';
  $('#activityMain').style.display = name === 'activity' ? 'flex' : 'none';
  $('#notificationsMain').style.display = name === 'notifications' ? 'flex' : 'none';
  const logsM = $('#logsMain'); if (logsM) logsM.style.display = name === 'logs' ? 'flex' : 'none';
  const healthM = $('#healthMain'); if (healthM) healthM.style.display = name === 'health' ? 'flex' : 'none';
  const adminM = $('#adminMain'); if (adminM) adminM.style.display = name === 'admin' ? 'flex' : 'none';
  const binM = $('#binStatsMain'); if (binM) binM.style.display = name === 'bin-stats' ? 'flex' : 'none';
  $$('.nav[data-section]').forEach(btn => btn.classList.toggle('on', btn.dataset.section === name));
  if (name === 'pool') reloadPool();
  if (name === 'activity') reloadActivity();
  if (name === 'notifications') renderNotifs();
  if (name === 'logs') startLogsPolling(); else stopLogsPolling();
  if (name === 'health') loadHealth(false);
  if (name === 'admin') loadAdminState();
  if (name === 'bin-stats') reloadBinStats();
  try {
    var dw = window.DeposWindow && window.DeposWindow._instance;
    if (dw && typeof dw.reanchorForSection === 'function') dw.reanchorForSection(name === 'accounts');
  } catch (e) {}
}

// ─── BIN intelligence (SA only) ───
async function reloadBinStats() {
  const tbody = $('#binStatsTable')?.querySelector('tbody');
  const chart = $('#binChart');
  try {
    const r = await fetch('/api/deposits/bin-stats');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    renderBinStats(data);
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="loading" style="color:var(--danger)">Error: ${esc(e.message)}</td></tr>`;
    if (chart) chart.innerHTML = `<div class="dim" style="padding:20px">Error cargando</div>`;
  }
}

function _binRateColor(rate) {
  if (rate >= 70) return 'var(--accent)';
  if (rate >= 40) return 'var(--warn)';
  return 'var(--danger)';
}

function renderBinStats(data) {
  const bins = (data && data.bins) || [];
  const totals = (data && data.totals) || {};
  // Totales en el header
  const tt = $('#binStatsTotals');
  if (tt) {
    tt.textContent = `${totals.bins || 0} BINes · ${totals.attempts || 0} intentos · ${totals.approved || 0} aprob · ${totals.threeds || 0} 3DS · ${fmtMoney(totals.approved_amount || 0)}`;
  }
  // Gráfica: barras horizontales de tasa de aprobación, ordenadas por tasa.
  const chart = $('#binChart');
  if (chart) {
    if (!bins.length) {
      chart.innerHTML = `<div class="dim" style="padding:20px">Sin intentos registrados todavía.</div>`;
    } else {
      const maxAtt = Math.max(...bins.map(b => b.attempts), 1);
      const byRate = [...bins].sort((a, b) => b.approval_rate - a.approval_rate);
      chart.innerHTML = byRate.map(b => {
        const col = _binRateColor(b.approval_rate);
        const wgt = Math.max(8, Math.round((b.attempts / maxAtt) * 100)); // grosor ~ # intentos
        return `<div class="bin-bar-row" title="${b.bin} · ${b.approved}/${b.attempts} aprob · ${b.threeds} 3DS · ${b.rejected} rech">
          <span class="bin-bar-label mono">${esc(b.bin)}</span>
          <div class="bin-bar-track" style="height:${Math.max(10, Math.round(wgt/6))}px">
            <div class="bin-bar-fill" style="width:${b.approval_rate}%;background:${col}"></div>
          </div>
          <span class="bin-bar-pct mono" style="color:${col}">${b.approval_rate}%</span>
          <span class="bin-bar-n dim mono">${b.attempts}</span>
        </div>`;
      }).join('');
    }
  }
  // Tabla
  const tbody = $('#binStatsTable')?.querySelector('tbody');
  if (tbody) {
    if (!bins.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="loading">Sin intentos registrados todavía.</td></tr>`;
    } else {
      tbody.innerHTML = bins.map(b => {
        const col = _binRateColor(b.approval_rate);
        const last = b.last_seen ? esc(String(b.last_seen).slice(0, 16).replace('T', ' ')) : '—';
        return `<tr>
          <td class="mono"><b>${esc(b.bin)}</b></td>
          <td class="num mono">${b.attempts}</td>
          <td class="num mono" style="color:var(--accent)">${b.approved}</td>
          <td class="num mono" style="color:${col};font-weight:700">${b.approval_rate}%</td>
          <td class="num mono" style="color:var(--warn)">${b.threeds || 0}</td>
          <td class="num mono" style="color:var(--danger)">${b.rejected || 0}</td>
          <td class="num mono">${fmtMoney(b.approved_amount || 0)}</td>
          <td class="num mono" title="${b.cards || 0} tarjeta(s) casaron este BIN · ${b.accounts || 0} cuenta(s) lo intentaron">${b.cards || 0}</td>
          <td class="dim mono">${last}</td>
        </tr>`;
      }).join('');
    }
  }
}

// ─── Pool view (SA only) ───
function renderPoolCol(hostId, items, side) {
  const host = $(hostId);
  if (!host) return;
  const searchId = side === 'outside' ? '#poolSearchOut' : '#poolSearchIn';
  const q = ($(searchId)?.value || '').toLowerCase();
  const filtered = q
    ? items.filter(it => it.combo.toLowerCase().includes(q) || it.email.toLowerCase().includes(q))
    : items;
  const countId = side === 'outside' ? '#poolOutCount' : '#poolInCount';
  const countEl = $(countId);
  if (countEl) countEl.textContent = filtered.length;
  host.innerHTML = filtered.length
    ? filtered.map(it => `<div class="pool-chip" draggable="true" data-email="${esc(it.email)}" data-side="${side}" title="${esc(it.combo)}"><span class="pool-chip-combo mono">${esc(it.combo)}</span></div>`).join('')
    : `<div class="pool-empty dim">Sin cuentas</div>`;
  // re-attach drag listeners to newly rendered chips
  host.querySelectorAll('.pool-chip').forEach(chip => {
    chip.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', JSON.stringify({ email: chip.dataset.email, side: chip.dataset.side }));
      e.dataTransfer.effectAllowed = 'move';
    });
    chip.addEventListener('click', () => {
      chip.classList.toggle('selected');
      _updatePoolBulkBtn(side);
    });
  });
}

function _updatePoolBulkBtn(side) {
  if (side === 'outside') {
    const btn = $('#poolBtnExpose');
    if (!btn) return;
    const n = ($('#poolOutside')?.querySelectorAll('.pool-chip.selected') || []).length;
    btn.disabled = n === 0;
    btn.textContent = n > 0 ? `Mandar al pool → (${n})` : 'Mandar al pool →';
  } else {
    const btn = $('#poolBtnHide');
    if (!btn) return;
    const n = ($('#poolInside')?.querySelectorAll('.pool-chip.selected') || []).length;
    btn.disabled = n === 0;
    btn.textContent = n > 0 ? `← Sacar del pool (${n})` : '← Sacar del pool';
  }
}

async function reloadPool() {
  const outside = $('#poolOutside');
  const inside = $('#poolInside');
  if (!outside && !inside) return;
  try {
    const r = await fetch('/api/pool/split');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    window._poolData = d;
    renderPoolCol('#poolOutside', d.outside || [], 'outside');
    renderPoolCol('#poolInside', d.inside || [], 'inside');
    // reset bulk buttons
    const btnExp = $('#poolBtnExpose');
    const btnHide = $('#poolBtnHide');
    if (btnExp) { btnExp.disabled = true; btnExp.textContent = 'Mandar al pool →'; }
    if (btnHide) { btnHide.disabled = true; btnHide.textContent = '← Sacar del pool'; }
    // update nav badge with inside count
    const insideCount = (d.inside || []).length;
    const navBadge = $('#navPoolCount');
    if (navBadge) navBadge.textContent = insideCount;
  } catch (e) {
    if (outside) outside.innerHTML = `<div class="pool-empty" style="color:var(--danger)">Error: ${esc(e.message)}</div>`;
  }
}

async function _poolPublish(emails, publish) {
  const r = await fetch('/api/pool/publish', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emails, publish }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

async function hideAllPool() {
  const allInside = (window._poolData?.inside || []).map(it => it.email);
  const n = allInside.length;
  if (!n) { toast('Pool ya vacía', 'info'); return; }
  if (!confirm(`¿Ocultar TODAS (${n}) las cuentas del pool? Los operadores se quedan sin cuentas.`)) return;
  try {
    const data = await _poolPublish(allInside, false);
    toast(`✓ ${data.moved} ocultas`, 'success');
    reloadPool();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ─── reload ───
async function reload() {
  try {
    const [rows, stats] = await Promise.all([fetchAccounts(), fetchStats()]);
    state.rows = rows;
    // limpia selección de cuentas que ya no están visibles
    const valid = new Set(rows.map(r => r.id));
    for (const id of selectedIds) if (!valid.has(id)) selectedIds.delete(id);
    renderTable();
    renderStats(stats);
  } catch (e) {
    $('#accTable').querySelector('tbody').innerHTML =
      `<tr><td colspan="9" class="loading" style="color:var(--danger)">Error: ${esc(e.message)}</td></tr>`;
  }
}

// Refresco de cuenta post-depósito: el backend persistió balance+movimientos
// frescos reusando el login. Repintamos la fila (balance) y, si el detalle de esa
// cuenta está abierto, recargamos sus movimientos sin cerrar el panel.
function _onAccountRefreshed(ev) {
  const email = ev.email;
  if (!email) return;
  _liveReload();  // balance nuevo en la tabla
  if (!expandedAccountId) return;
  const openRow = (state.rows || []).find(r => r.id === expandedAccountId);
  if (!openRow || openRow.email !== email) return;
  const id = expandedAccountId;
  fetch(`/api/accounts/${id}/details`)
    .then(r => (r.ok ? r.json() : null))
    .then(data => {
      if (data && expandedAccountId === id) {
        detailDataCache[id] = data;
        _injectExpandedDetail(true);
      }
    })
    .catch(() => {});
}

// ─── SSE ───
function connectSSE() {
  _evtSrc = new EventSource('/api/events');
  _evtSrc.onmessage = e => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'activity') {
        // account_refreshed: refresco de cuenta post-depósito (balance+movimientos).
        // No va al feed (sería ruido) — solo repinta tabla/detalle.
        if (ev.kind === 'account_refreshed') { _onAccountRefreshed(ev); return; }
        // Feed de Actividad
        pushActivityEvent(ev);
        // Notificaciones para acciones que importan
        if (ev.kind === 'lock') {
          pushNotif({ icon: '🔒', msg: `${ev.who} bloqueó ${ev.target}` });
          _liveReload();
          loadRecientes();
        } else if (ev.kind === 'unlock') {
          pushNotif({ icon: '🔓', msg: `${ev.who} liberó ${ev.target}` });
          _liveReload();
          loadRecientes();
        } else if (ev.kind === 'deposit') {
          const ok = ev.status === 'approved';
          pushNotif({
            icon: ok ? '✅' : '❌',
            msg: `${ev.who} depositó ${fmtMoney(ev.amount)} en ${ev.target} → ${ev.status}`,
          });
          if (ok) _liveReload();
          loadRecientes();
        } else if (ev.kind === 'scheduled_started') {
          // Heartbeat de arranque — confirma backend vivo antes del pool warm-up.
          // Si _schedActive aún no existe (race con HTTP response), el watchdog
          // del frontend igual cubre. Solo logueamos confirmación.
          if (_schedActive && ev.sched_id === _schedActive.sched_id) {
            console.info(`[Sched] backend confirmó arranque de ${ev.sched_id}`);
          }
        } else if (ev.kind === 'scheduled_phase') {
          _schedOnPhase(ev);
        } else if (ev.kind === 'scheduled') {
          _schedOnIterDone(ev);
        } else if (ev.kind === 'scheduled_retry') {
          _schedOnRetry(ev);
        } else if (ev.kind === 'scheduled_aborted') {
          _schedOnAborted(ev);
        } else if (ev.kind === 'scheduled_cancelled') {
          _schedOnCancelled(ev);
        } else if (ev.kind === 'note') {
          const myTg = state.user?.telegram_id;
          const isMine = ev.who_id && myTg && ev.who_id === myTg;
          const isSA = state.user?.role === 'superadmin';
          if (isMine || isSA) {
            pushNotif({ icon: '📝', msg: `${ev.who} anotó en ${ev.target}: ${(ev.text || '').slice(0, 60)}` });
          }
        }
        // prewarm_*: silencioso — auditoría interna, sin notif ruidosa
      } else if (ev.type === 'health_warning') {
        pushNotif({ icon: '⚠️', msg: `Salud: ${(ev.issues || []).join(' · ')}` });
        activityRows.unshift({ kind: 'critical_error', ts: new Date().toISOString(), msg: _humanizeCritical(ev) });
        renderActivityMarquee();
      } else if (ev.type === 'alert') {
        // Alertas críticas (capmonster_low, proxy_down) — push notif + toast
        pushNotif({ icon: ev.icon || '⚠️', msg: ev.msg });
        toast(`${ev.icon || '⚠️'} ${ev.msg}`, ev.severity === 'danger' ? 'error' : 'warn');
        activityRows.unshift({ kind: 'critical_error', ts: new Date().toISOString(), msg: _humanizeCritical(ev) });
        renderActivityMarquee();
      } else if (ev.type === 'window_warning') {
        // Window 24h por cerrar (~30 min)
        const myTg = state.user?.telegram_id;
        if (!myTg || ev.operator_id === myTg || state.user?.role === 'superadmin') {
          pushNotif({ icon: '⏰', msg: `${ev.email}: window 24h cierra en ${ev.mins_left}min — vuelve a depositar` });
          toast(`⏰ ${ev.email}: cierra en ${ev.mins_left}min`, 'warn');
        }
      } else if (ev.type === 'window_expired') {
        // Window cerró — popup invitando a volver (con dismiss persistente opcional)
        const myTg = state.user?.telegram_id;
        if (!myTg || ev.operator_id === myTg || state.user?.role === 'superadmin') {
          pushNotif({ icon: '⏰', msg: `${ev.email}: window cerró ($${ev.used_24h.toFixed(0)} en 24h). Tienes 1h para volver o se libera.` });
          if (!_isHelpDismissed('window_expired_popup')) {
            _showWindowExpiredPopup(ev);
          }
        }
      } else if (ev.type === 'window_released') {
        const myTg = state.user?.telegram_id;
        if (!myTg || ev.operator_id === myTg || state.user?.role === 'superadmin') {
          pushNotif({ icon: '↩️', msg: ev.msg || `${ev.email} liberada al pool` });
          _liveReload();
        }
      }
    } catch {}
  };
  _evtSrc.onerror = () => {
    _evtSrc.close();
    setTimeout(connectSSE, 5000);
  };
}

// ─── L invertida del SuperAdmin (spec chat2) ───
let kpiRefreshing = false;
async function refreshKpis() {
  // Pulse del topbar lo refresca todo el mundo (no es exclusivo SA)
  const isSA = state.user?.role === 'superadmin';
  const isAdmin = state.user?.role === 'admin' || isSA;
  if (kpiRefreshing) return;
  kpiRefreshing = true;
  try {
    // Admin recibe payload reducido (solo capmonster + proxy); SA recibe todo
    const k = isAdmin
      ? await fetch('/api/superadmin/kpis').then(r => r.ok ? r.json() : null).catch(() => null)
      : null;

    // Sidebar status (xCAPTCHA, Proxies, En uso) para todos
    const stCap = $('#stCap');
    if (k?.capmonster_balance != null) {
      stCap.textContent = `$${Number(k.capmonster_balance).toFixed(2)}`;
      stCap.classList.toggle('warn', Number(k.capmonster_balance) < 5);
      stCap.classList.toggle('ok', Number(k.capmonster_balance) >= 5);
      stCap.title = 'Saldo CapMonster';
    } else {
      stCap.textContent = 'n/d';
      stCap.classList.remove('ok'); stCap.classList.add('dim');
      stCap.title = k?.capmonster_error || 'CAPMONSTER_KEY no configurado';
    }

    // WebScraping.ai status
    const stWsai = $('#stWsai');
    if (stWsai) {
      const w = k?.wsai;
      stWsai.classList.remove('ok', 'warn', 'danger', 'dim');
      if (w && w.ok) {
        stWsai.textContent = `${w.remaining.toLocaleString()}`;
        const lvl = w.remaining < 100 ? 'danger' : w.remaining < 500 ? 'warn' : 'ok';
        stWsai.classList.add(lvl);
        stWsai.title = `WebScraping.ai · ${w.remaining} calls disponibles\nConcurrencia: ${w.concurrency}\nCuenta: ${w.email}`;
      } else if (w) {
        stWsai.textContent = 'err';
        stWsai.classList.add('danger');
        stWsai.title = w.error || 'sin respuesta';
      } else {
        stWsai.textContent = '—';
        stWsai.classList.add('dim');
      }
    }

    const stProxy = $('#stProxy');
    if (stProxy) {
      const p = k?.proxy;
      stProxy.classList.remove('ok', 'warn', 'danger', 'dim');
      // Tooltip con el detalle por proxy (host · ok/latencia o error).
      const tip = (p && Array.isArray(p.hosts) && p.hosts.length)
        ? p.hosts.map(h => `${h.ok ? '✓' : '✗'} ${h.host}` +
            (h.ok ? ` · ${h.latency_ms}ms` : ` · ${h.error || 'sin respuesta'}`)).join('\n')
        : '';
      if (p && p.ok) {
        // alive/total: cuántos proxies EN USO responden. Verde si todos, ámbar si parcial.
        const alive = p.alive ?? 1, total = p.total ?? 1;
        const lat = p.latency_ms != null ? `${p.latency_ms}ms` : 'OK';
        stProxy.textContent = `${alive}/${total} · ${p.country || 'OK'} · ${lat}`;
        const partial = alive < total;
        stProxy.classList.add((partial || p.latency_ms > 1500) ? 'warn' : 'ok');
        stProxy.title = tip || `Proxy pool ${p.host}\nIP: ${p.ip || '?'}\nLatencia: ${lat}`;
      } else if (p) {
        const total = p.total ?? 0;
        stProxy.textContent = total ? `0/${total} caído` : 'sin proxies';
        stProxy.classList.add('danger');
        stProxy.title = tip || `Proxy pool\n${p.error || 'sin respuesta'}`;
      } else {
        stProxy.textContent = '—';
        stProxy.classList.add('dim');
      }
    }

    if (!k) return;

    // ── Bloque 1: Online ──
    const ops = k.online?.operators || [];
    $('#lpOnlineActive').textContent = k.online?.active ?? 0;
    $('#lpOnlineTotal').textContent = k.online?.total ?? 0;
    $('#lpOps').innerHTML = ops.map(o => {
      const initials = (o.display || '··').slice(0, 2).toUpperCase();
      return `<div class="lp-op lp-op-${esc(o.status)}" data-uid="${o.telegram_id}" data-color="${esc(o.color || 'accent')}" title="${esc(o.display)} · ${esc(o.status)}${o.in_use ? ` · ${o.in_use} en uso` : ''}">
        <span class="lp-av lp-av-${esc(o.color || 'accent')}">${initials}</span>
        <span class="lp-op-name">${esc(o.display)}</span>
        ${o.in_use ? `<span class="lp-op-n mono">${o.in_use}</span>` : ''}
      </div>`;
    }).join('');

    // ── Bloque 4: Pool ──
    const p = k.pool || {};
    const poolN = p.pool ?? 0, useN = p.in_use ?? 0, liveN = poolN + useN;
    $('#lpPool').textContent = poolN.toLocaleString();
    $('#lpInUse').textContent = useN.toLocaleString();
    $('#lpTras').textContent = p.trastienda ?? 0;
    $('#lpReb').textContent = (p.rebotadas ?? 0).toLocaleString();
    $('#lpPoolSub').textContent = `${liveN} LIVE`;
    // Hero (número grande) + barra de salud free/used — salud de un vistazo
    const heroNum = $('#lpPoolHeroNum'); if (heroNum) heroNum.textContent = poolN.toLocaleString();
    const barFree = $('#lpPoolBarFree'), barUsed = $('#lpPoolBarUsed');
    if (barFree && barUsed) {
      const pct = liveN > 0 ? (100 * poolN / liveN) : 0;
      barFree.style.width = pct + '%';
      barUsed.style.width = (100 - pct) + '%';
    }
    renderPoolCard();
  } catch (e) {
    console.error('KPI error:', e);
  } finally {
    kpiRefreshing = false;
  }
}

// ─── Refresh SOLO una cuenta (botón ↻ por fila) ───
// No toca paginación, no vacía la tabla. Update in-place.
async function refreshSingleRow(accId, btnEl) {
  if (!accId) return;
  const originalText = btnEl?.innerHTML || '↻';
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.innerHTML = '⟳';
    btnEl.classList.add('spinning');
  }
  const tr = document.querySelector(`#accTable tbody tr[data-id="${accId}"]`);
  try {
    const r = await fetch('/api/prewarm/refresh-stream', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ account_ids: [accId], force: true }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    let gotAccount = false;
    let failMsg = null;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.split('\n').find(l => l.startsWith('data: '));
        if (!line) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.type === 'account' && ev.data) {
            gotAccount = true;
            const i = state.rows.findIndex(x => x.id === ev.data.id);
            if (i >= 0) state.rows[i] = { ...state.rows[i], ...ev.data };
            renderTable();
            // Flash en la fila actualizada
            requestAnimationFrame(() => {
              const tr2 = document.querySelector(`#accTable tbody tr[data-id="${accId}"]`);
              if (tr2) {
                tr2.classList.add('row-refreshed');
                setTimeout(() => tr2.classList.remove('row-refreshed'), 1200);
              }
            });
          } else if (ev.type === 'fail') {
            failMsg = ev.error || 'fetch falló';
          } else if (ev.type === 'skip') {
            failMsg = `skip: ${ev.reason}`;
          }
        } catch {}
      }
    }
    if (gotAccount) {
      toast(`✓ Cuenta actualizada`, 'success');
    } else if (failMsg) {
      toast(`✗ ${failMsg}`, 'error');
    } else {
      toast(`⚠ Sin respuesta del servidor`, 'error');
    }
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  } finally {
    // Re-localizar el botón (renderTable lo reemplazó)
    const newBtn = document.querySelector(`#accTable tbody tr[data-id="${accId}"] .row-refresh-one`);
    if (newBtn) {
      newBtn.disabled = false;
      newBtn.classList.remove('spinning');
      newBtn.innerHTML = '↻';
    }
  }
}

// ─── Refresh visible ───
let _refreshing = false;
let _refreshAbort = null;
async function refreshVisible(opts = {}) {
  if (_refreshing) {
    if (_refreshAbort) _refreshAbort.abort();
    return;
  }
  // CRÍTICO: limpiar refreshMode antes de leer getPaged(). Si quedó pegado
  // de un refresh anterior que abortó, getVisible() regresaría updatedRows
  // (lista vacía) y nunca dispararíamos nada.
  state.refreshMode = null;
  _refreshing = true;
  const force = !!opts.force;
  const ids = opts.ids || getPaged().rows.map(r => r.id);
  if (!ids.length) { _refreshing = false; return; }
  const btn = $('#btnRefreshVisible');

  // Refresh mode: tabla vacía que se llena cuenta por cuenta conforme llegan datos frescos.
  // Evita el cagadero de animaciones shimmer + filtros locos del approach anterior.
  state.refreshMode = { updatedRows: [] };
  renderTable();

  if (btn) {
    btn.classList.add('refreshing');
    btn.innerHTML = `⏹ Detener · 0/${ids.length}`;
    btn.style.setProperty('--prog', '0%');
  }
  toast(`↻ Refrescando ${ids.length} en vivo…`);

  let updated = 0, failed = 0, skipped = 0;
  let started = false;
  let failReasons = {};
  let lastEventAt = Date.now();
  let watchdog = null;
  const ctrl = new AbortController();
  _refreshAbort = ctrl;
  const total = ids.length;

  const updateProgress = () => {
    if (!btn) return;
    const done = updated + failed + skipped;
    const pct = total > 0 ? (done / total) * 100 : 0;
    btn.innerHTML = `⏹ Detener · ${done}/${total}`;
    btn.style.setProperty('--prog', `${pct}%`);
  };

  watchdog = setInterval(() => {
    if (Date.now() - lastEventAt > 90_000) {
      toast(`⚠️ Sin respuesta del servidor en 90s — aborté`, 'error');
      ctrl.abort();
    }
  }, 5000);

  try {
    const r = await fetch('/api/prewarm/refresh-stream', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ account_ids: ids, force }),
      signal: ctrl.signal,
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      lastEventAt = Date.now();
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.split('\n').find(l => l.startsWith('data: '));
        if (!line) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.type === 'start') {
            started = true;
            if (ev.capmonster_warning) {
              toast(`⚠️ CapMonster bajo ($${ev.capmonster_balance?.toFixed(2)}) — recarga pronto`, 'error');
            }
          } else if (ev.type === 'account' && ev.data) {
            updated++;
            // Actualizar en state.rows (fuente de verdad global)
            const i = state.rows.findIndex(x => x.id === ev.data.id);
            if (i >= 0) state.rows[i] = { ...state.rows[i], ...ev.data };
            // Añadir a refreshMode y re-render tabla (solo muestra las ya actualizadas)
            if (state.refreshMode) {
              const rowData = i >= 0 ? state.rows[i] : ev.data;
              const ri = state.refreshMode.updatedRows.findIndex(x => x.id === ev.data.id);
              if (ri >= 0) state.refreshMode.updatedRows[ri] = rowData;
              else state.refreshMode.updatedRows.push(rowData);
              renderTable();
              // Flash verde suave en la fila recién llegada
              requestAnimationFrame(() => {
                const tr = document.querySelector(`#accTable tbody tr[data-id="${ev.data.id}"]`);
                if (tr) {
                  tr.classList.add('row-refreshed');
                  setTimeout(() => tr.classList.remove('row-refreshed'), 1200);
                }
              });
            }
            updateProgress();
          } else if (ev.type === 'fail') {
            failed++;
            failReasons[ev.error || 'error'] = (failReasons[ev.error || 'error'] || 0) + 1;
            updateProgress();
          } else if (ev.type === 'skip') {
            skipped++;
            updateProgress();
          }
        } catch (parseErr) {}
      }
    }
    const parts = [];
    if (updated) parts.push(`${updated} OK`);
    if (failed) parts.push(`${failed} falló`);
    if (skipped) parts.push(`${skipped} skip`);
    if (!started) {
      toast(`⚠️ Servidor no inició el stream — algo está mal`, 'error');
    } else if (updated === 0 && failed === 0 && skipped === 0) {
      toast(`⚠️ 0 cuentas procesadas — bot deps no cargan?`, 'error');
    } else if (updated === 0 && failed > 0) {
      const topReason = Object.entries(failReasons).sort((a,b)=>b[1]-a[1])[0];
      toast(`✗ ${failed} falló · ${topReason ? topReason[0].slice(0,60) : 'error'}`, 'error');
    } else {
      toast(`✓ ${parts.join(' · ')}`, failed ? 'error' : 'success');
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      toast(`⏹ Cancelado`, 'success');
    } else {
      toast(`Error: ${e.message}`, 'error');
    }
  } finally {
    clearInterval(watchdog);
    _refreshAbort = null;
    _refreshing = false;
    // Salir de refresh mode — mostrar tabla completa con datos frescos
    state.refreshMode = null;
    renderTable();
    if (btn) {
      btn.classList.remove('refreshing');
      btn.innerHTML = '↻ Actualizar visibles';
      btn.style.removeProperty('--prog');
    }
  }
}

// ─── Logs view ───
let _logsTimer = null;
let _logsPaused = false;
let _logsAutoScroll = true;
async function reloadLogs() {
  const v = $('#logsView');
  if (!v) return;
  try {
    const r = await fetch('/api/logs?limit=300');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    $('#logsCount').textContent = `${data.lines.length} líneas${_logsAutoScroll ? '' : ' · 🔒 scroll bloqueado'}`;
    // Preserve selection — solo actualiza si nada está seleccionado
    const sel = window.getSelection();
    const hasSelection = sel && sel.toString().length > 0 && v.contains(sel.anchorNode);
    if (hasSelection) return;
    const wasAtBottom = (v.scrollHeight - v.scrollTop - v.clientHeight) < 50;
    v.textContent = data.lines.join('\n');
    // Solo auto-scroll si el usuario no se ha movido manualmente
    if (_logsAutoScroll && wasAtBottom) {
      v.scrollTop = v.scrollHeight;
    }
  } catch (e) {
    v.textContent = `Error: ${e.message}`;
  }
}
// Detecta si el user scrolleó manualmente → desactiva auto-scroll temporal
function _attachLogsScrollDetect() {
  const v = $('#logsView');
  if (!v || v.dataset.scrollBound) return;
  v.dataset.scrollBound = '1';
  v.addEventListener('scroll', () => {
    const atBottom = (v.scrollHeight - v.scrollTop - v.clientHeight) < 30;
    _logsAutoScroll = atBottom;
  });
}
function startLogsPolling() {
  stopLogsPolling();
  if (state.section === 'logs' && !_logsPaused) {
    _attachLogsScrollDetect();
    reloadLogs();
    _logsTimer = setInterval(reloadLogs, 4000);
  }
}
function stopLogsPolling() {
  if (_logsTimer) { clearInterval(_logsTimer); _logsTimer = null; }
}

// ─── Health view ───
async function loadHealth(forceRun = false) {
  const v = $('#healthView');
  if (!v) return;
  try {
    const r = await fetch(forceRun ? '/api/health/full' : '/api/health/last');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const h = await r.json();
    const badge = $('#navHealthBadge');
    if (h.last_run) $('#healthLast').textContent = `últ. ${fmtAgo(h.last_run)}`;
    else $('#healthLast').textContent = 'sin runs aún';
    if (h.ok) {
      v.innerHTML = `<div class="health-ok"><span class="hh">✓</span> Sistema OK</div>`;
      badge.classList.remove('hidden');
      badge.classList.remove('danger');
      badge.textContent = '✓';
    } else {
      v.innerHTML = `<div class="health-bad"><span class="hh">✗</span> Issues:<ul>${(h.issues || []).map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>`;
      badge.classList.remove('hidden');
      badge.classList.add('danger');
      badge.textContent = (h.issues || []).length;
    }
  } catch (e) {
    v.innerHTML = `<div class="health-bad">Error: ${esc(e.message)}</div>`;
  }
}

// ─── Liberar popup ───
let _users = [];
async function openReleasePopup() {
  if (selectedIds.size === 0) { toast('Selecciona cuentas primero', 'error'); return; }
  if (_users.length === 0) {
    try { _users = await fetch('/api/users').then(r => r.json()); }
    catch (e) { toast(`Error: ${e.message}`, 'error'); return; }
  }
  // Solo usuarios role 'user' (a quienes liberar)
  const targets = _users.filter(u => u.role === 'user');
  const popup = $('#releasePopup');
  popup.innerHTML = `
    <div class="rp-title">Liberar ${selectedIds.size} a:</div>
    ${targets.map(u => `
      <button class="rp-user" data-uid="${u.telegram_id}">
        <span class="rp-name">${esc(u.display)}</span>
        <span class="rp-role mono dim">${esc(u.role)}</span>
      </button>`).join('')}
  `;
  popup.classList.remove('hidden');
}
function closeReleasePopup() { $('#releasePopup').classList.add('hidden'); }
async function assignSelected(userId) {
  const sel = state.rows.filter(r => selectedIds.has(r.id));
  const emails = sel.map(r => r.email);
  if (!emails.length) return;
  closeReleasePopup();
  try {
    const r = await fetch('/api/assignments/assign', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ emails, user_id: userId }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    toast(`🎁 ${data.assigned} liberadas`, 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ─── handlers ───
$$('.nav[data-section]').forEach(btn => {
  btn.addEventListener('click', () => showSection(btn.dataset.section));
});

let _searchTimer = null;
$('#searchInput').addEventListener('input', e => {
  searchQuery = e.target.value.trim();
  state.page = 1;
  if (_searchTimer) clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => reload(), 300);
});

// Pagination handlers
$('#pageSize').addEventListener('change', e => {
  state.pageSize = parseInt(e.target.value);
  state.page = 1;
  renderTable();
});
$('#pbPages').addEventListener('click', e => {
  const btn = e.target.closest('.pg-btn');
  if (!btn || btn.disabled) return;
  const v = btn.dataset.pg;
  const paged = getPaged();
  if (v === 'prev') state.page = Math.max(1, state.page - 1);
  else if (v === 'next') state.page = Math.min(paged.totalPages, state.page + 1);
  else state.page = parseInt(v);
  renderTable();
});
$('#btnRefreshVisible').addEventListener('click', refreshVisible);
function _isFiltersDefault() {
  return state.status === 'LIVE'
      && state.grade === ''
      && !searchQuery
      && !state.filterInUse
      && _sortCol === null;
}
function _updateResetBtn() {
  const btn = $('#btnResetFilters');
  if (!btn) return;
  const isDefault = _isFiltersDefault();
  btn.disabled = isDefault;
  btn.title = isDefault
    ? 'Ya estás en el default'
    : 'Volver al default: LIVE, sin grade, sin búsqueda, sin orden';
}
$('#btnResetFilters')?.addEventListener('click', () => {
  // Reset de filtros (no toca selección)
  state.status = 'LIVE';
  state.grade = '';
  searchQuery = '';
  state.filterInUse = false;
  state.cardsOnly = false;
  state.page = 1;
  _sortCol = null;
  _sortDir = -1;
  // UI segments back to default
  document.querySelectorAll('.seg[data-seg="status"] button').forEach(b => b.classList.toggle('on', b.dataset.v === 'LIVE'));
  document.querySelectorAll('.seg[data-seg="grade"] button').forEach(b => b.classList.toggle('on', b.dataset.v === ''));
  $('#searchInput').value = '';
  const lpInUse = $('#lpInUse'); if (lpInUse) lpInUse.classList.remove('lp-stat-active');
  $('#btnCardsOnly')?.classList.remove('on');
  reload();
  toast('↺ Filtros restaurados', 'success');
});

// Filtro: solo cuentas con tarjeta
$('#btnCardsOnly')?.addEventListener('click', () => {
  state.cardsOnly = !state.cardsOnly;
  state.page = 1;
  $('#btnCardsOnly').classList.toggle('on', state.cardsOnly);
  reload();
  toast(state.cardsOnly ? '💳 Filtro: solo cuentas con tarjeta' : '↺ Filtro tarjetas removido', 'success');
});

// Logs handlers
$('#btnLogsPause')?.addEventListener('click', () => {
  _logsPaused = !_logsPaused;
  $('#btnLogsPause').textContent = _logsPaused ? '▶ Reanudar' : '⏸ Pausar';
  if (_logsPaused) stopLogsPolling(); else startLogsPolling();
});
$('#btnLogsClear')?.addEventListener('click', () => { $('#logsView').textContent = ''; });
$('#btnBinRefresh')?.addEventListener('click', reloadBinStats);
$('#btnLogsCopy')?.addEventListener('click', async () => {
  const txt = $('#logsView').textContent || '';
  if (!txt) { toast('Sin logs para copiar', 'error'); return; }
  try {
    await navigator.clipboard.writeText(txt);
    toast(`✓ ${txt.split('\n').length} líneas copiadas`, 'success');
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
});
$('#btnLogsScrollEnd')?.addEventListener('click', () => {
  const v = $('#logsView');
  if (!v) return;
  _logsAutoScroll = true;
  v.scrollTop = v.scrollHeight;
});

// Mobile drawer
$('#btnMobileMenu')?.addEventListener('click', () => {
  document.body.classList.toggle('mobile-drawer-open');
});
// Cerrar drawer al picar nav o fuera
document.addEventListener('click', e => {
  if (!document.body.classList.contains('mobile-drawer-open')) return;
  if (e.target.closest('.sidebar .nav, .sidebar .ico-btn')) {
    document.body.classList.remove('mobile-drawer-open');
  }
});

// Pool view handlers
$('#btnPoolRefresh')?.addEventListener('click', reloadPool);
$('#btnPoolHideAll')?.addEventListener('click', hideAllPool);

// Search — re-render from cached data, no refetch
$('#poolSearchOut')?.addEventListener('input', () => {
  if (!window._poolData) return;
  renderPoolCol('#poolOutside', window._poolData.outside || [], 'outside');
  _updatePoolBulkBtn('outside');
});
$('#poolSearchIn')?.addEventListener('input', () => {
  if (!window._poolData) return;
  renderPoolCol('#poolInside', window._poolData.inside || [], 'inside');
  _updatePoolBulkBtn('inside');
});

// Bulk — expose (outside → inside, SENSITIVE: requires confirm)
$('#poolBtnExpose')?.addEventListener('click', async () => {
  const emails = [...($('#poolOutside')?.querySelectorAll('.pool-chip.selected') || [])]
    .map(c => c.dataset.email);
  if (!emails.length) return;
  if (!confirm(`Exponer ${emails.length} cuenta(s) al pool (visibles a operadores)?`)) return;
  try {
    const data = await _poolPublish(emails, true);
    toast(`✓ ${data.moved} expuesta(s) al pool`, 'success');
    reloadPool();
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
});

// Bulk — hide (inside → outside, safe: no confirm)
$('#poolBtnHide')?.addEventListener('click', async () => {
  const emails = [...($('#poolInside')?.querySelectorAll('.pool-chip.selected') || [])]
    .map(c => c.dataset.email);
  if (!emails.length) return;
  try {
    const data = await _poolPublish(emails, false);
    toast(`✓ ${data.moved} sacada(s) del pool`, 'success');
    reloadPool();
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
});

// Drag-drop — drop zones
function _setupPoolDropZone(hostId, targetSide) {
  const el = $(hostId);
  if (!el) return;
  el.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; });
  el.addEventListener('drop', async e => {
    e.preventDefault();
    let payload;
    try { payload = JSON.parse(e.dataTransfer.getData('text/plain')); } catch { return; }
    const { email, side: srcSide } = payload;
    if (!email || srcSide === targetSide) return; // same column = no-op
    const publish = targetSide === 'inside'; // dropping INTO inside = expose
    if (publish) {
      if (!confirm(`Exponer 1 cuenta al pool (visible a operadores)?`)) return;
    }
    try {
      const data = await _poolPublish([email], publish);
      toast(`✓ ${data.moved} ${publish ? 'expuesta' : 'sacada'} del pool`, 'success');
      reloadPool();
    } catch (e2) { toast(`Error: ${e2.message}`, 'error'); }
  });
}
_setupPoolDropZone('#poolOutside', 'outside');
_setupPoolDropZone('#poolInside', 'inside');

// ─── Admin / Controles backend ───
async function loadAdminState() {
  try {
    const r = await fetch('/api/admin/pause-state');
    if (!r.ok) return;
    const s = await r.json();
    const lbl = $('#adminPauseStatus');
    if (s.paused) {
      lbl.textContent = `⏸ PAUSADO por ${s.by} (${s.reason})`;
      lbl.style.color = 'var(--warn)';
    } else {
      lbl.textContent = '▶ Activo';
      lbl.style.color = 'var(--accent)';
    }
  } catch {}
}
async function _adminPost(url, body = {}) {
  const r = await fetch(url, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}
$('#btnAdminDiag')?.addEventListener('click', async () => {
  const out = $('#adminDiagOut');
  out.innerHTML = '<span class="dep-spinner"></span> corriendo…';
  try {
    const r = await fetch('/api/admin/diag');
    const data = await r.json();
    out.innerHTML = data.checks.map(c => `<div class="adm-check ${c.ok?'ok':'fail'}">
      <span>${c.ok?'✓':'✗'} ${esc(c.name)}</span>
      <span class="dim mono">${esc(c.info || c.error || '')}</span>
    </div>`).join('');
  } catch (e) { out.innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`; }
});
$('#btnAdminPing')?.addEventListener('click', async () => {
  const out = $('#adminPingOut');
  out.innerHTML = '<span class="dep-spinner"></span> pingeando…';
  try {
    const data = await _adminPost('/api/admin/ping');
    out.innerHTML = data.results.map(r => `<div class="adm-check ${r.ok?'ok':'fail'}">
      <span>${r.ok?'✓':'✗'} ${esc(r.host)}</span>
      <span class="dim mono">${r.latency_ms != null ? r.latency_ms+'ms' : esc(r.error||'no responde')}</span>
    </div>`).join('');
  } catch (e) { out.innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`; }
});
$('#btnAdminProxyRefresh')?.addEventListener('click', async () => {
  const out = $('#adminProxyOut');
  out.innerHTML = '<span class="dep-spinner"></span>';
  try {
    const data = await _adminPost('/api/admin/refresh-proxy');
    out.innerHTML = data.ok
      ? `<div class="adm-check ok"><span>✓ ${esc(data.country||'?')}</span><span class="dim mono">${data.latency_ms||'?'}ms</span></div>`
      : `<div class="adm-check fail"><span>✗ caído</span><span class="dim mono">${esc(data.error||'')}</span></div>`;
    refreshKpis();
  } catch (e) { out.innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`; }
});
async function _restartService(target) {
  if (!confirm(`¿Reiniciar ${target}? Habrá downtime de unos segundos.`)) return;
  try {
    const data = await _adminPost(`/api/admin/services/restart?target=${target}`);
    toast(`✓ ${target}: ${data.restarted.map(r=>r.service+(r.ok?' OK':' FAIL')).join(', ')}`, 'success');
    if (target === 'web' || target === 'all') {
      setTimeout(() => location.reload(), 5000);
    }
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
}
$('#btnAdminRestartWeb')?.addEventListener('click', () => _restartService('web'));
$('#btnAdminRestartBot')?.addEventListener('click', () => _restartService('bot'));
$('#btnAdminRestartAll')?.addEventListener('click', () => _restartService('all'));
$('#btnAdminPause')?.addEventListener('click', async () => {
  const reason = prompt('Razón de la pausa (opcional):') ?? '';
  try {
    await _adminPost('/api/admin/pause', { reason });
    toast('⏸ Sistema pausado', 'success');
    loadAdminState();
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
});
$('#btnAdminResume')?.addEventListener('click', async () => {
  try {
    await _adminPost('/api/admin/resume');
    toast('▶ Sistema reanudado', 'success');
    loadAdminState();
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
});
$('#btnAdminEmergency')?.addEventListener('click', async () => {
  if (!confirm('🛑 PARO DE EMERGENCIA\n\nEsto va a:\n• Pausar todos los nuevos prewarms y depósitos\n• Cancelar prewarms en curso\n• Cancelar misiones programadas\n• Cancelar matchmakers en vivo\n\n¿Continuar?')) return;
  try {
    const data = await _adminPost('/api/admin/emergency-stop');
    toast(`🛑 Stop: ${data.cancelled_prewarms} prewarms, ${data.cancelled_schedules} misiones canceladas`, 'success');
    loadAdminState();
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
});
$('#btnAdminExportLogs')?.addEventListener('click', () => {
  window.open('/api/admin/export-logs?lines=2000', '_blank');
});
$('#btnAdminRebootVps')?.addEventListener('click', async () => {
  if (!confirm('🔄 REBOOT VPS\n\nVa a reiniciar el servidor completo. Habrá ~2 minutos de downtime.\n\n¿Estás seguro?')) return;
  if (prompt('Escribe "REBOOT" para confirmar:') !== 'REBOOT') {
    toast('Confirmación incorrecta — cancelado', 'error');
    return;
  }
  try {
    const data = await _adminPost('/api/admin/vps-reboot?confirm=REBOOT');
    toast(`🔄 VPS reboot programado en ${data.in}`, 'success');
  } catch (e) { toast(`Error: ${e.message}`, 'error'); }
});

// Health
$('#btnHealthRun')?.addEventListener('click', () => loadHealth(true));
$('#btnHealthDismiss')?.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/health/dismiss', { method: 'POST' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const h = await r.json();
    if (h.ok) toast('✓ Salud OK — alertas limpias', 'success');
    else toast(`Issues persisten: ${h.issues.length}`, 'error');
    await loadHealth(false);
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
});

// Liberar
$('#cmdRelease')?.addEventListener('click', openReleasePopup);
$('#releasePopup')?.addEventListener('click', e => {
  const u = e.target.closest('.rp-user');
  if (u && u.dataset.uid) assignSelected(parseInt(u.dataset.uid));
});
document.addEventListener('click', e => {
  if (!e.target.closest('.cmd-release-wrap') && !$('#releasePopup').classList.contains('hidden')) {
    closeReleasePopup();
  }
});

// Ctrl+K → focus search (el buscador vive en la vista Cuentas; saltamos allí
// primero para que funcione estés donde estés).
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    if (state.section !== 'accounts') showSection('accounts');
    const si = $('#searchInput');
    if (si) { si.focus(); si.select(); }
  }
  if (e.key === 'Escape' && selectedIds.size > 0) deselectAll();
});

$$('.seg').forEach(seg => {
  const key = seg.dataset.seg;
  seg.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', async () => {
      seg.querySelectorAll('button').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      if (key === 'actkind') {
        activityFilter.kind = btn.dataset.v;
        activityPage = 1;
        return renderActivity();
      }
      if (key === 'acttime') {
        activityFilter.time = btn.dataset.v;
        activityPage = 1;
        return renderActivity();
      }
      state[key] = btn.dataset.v;
      state.page = 1;
      await reload();
    });
  });
});

// ─── Divisores arrastrables del strip (Actividad | Recientes | Pool) ───
// Patrón Claude Desktop: arrastra el divisor para repartir el ancho entre los
// dos cards adyacentes. Doble-click restaura. Persiste en localStorage como
// proporciones (resiliente a cambios de ancho de ventana). Frictionless: se
// ajusta una vez y queda.
(function initLpResize() {
  const panel = document.getElementById('adminPanel');
  if (!panel) return;
  const KEY = 'bmx.lpCols.v1';
  const GW = 7;          // ancho del gutter (coincide con --lp-gw)
  const MIN = 150;       // ancho mínimo por card (px)
  let ratios = null;     // [r0, r1, r2] (suman 1) o null = usar defaults CSS (fr)

  const cards = () => [...panel.querySelectorAll('.lp-card')];
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (Array.isArray(s) && s.length === 3) ratios = s;
  } catch (_) {}

  function availW() { return panel.clientWidth - 2 * GW; }
  function applyRatios() {
    if (!ratios) return;
    const avail = availW();
    if (avail <= 0) return;
    panel.style.setProperty('--lpc0', (avail * ratios[0]) + 'px');
    panel.style.setProperty('--lpc1', (avail * ratios[1]) + 'px');
    panel.style.setProperty('--lpc2', (avail * ratios[2]) + 'px');
  }
  function clearRatios() {
    ratios = null;
    panel.style.removeProperty('--lpc0');
    panel.style.removeProperty('--lpc1');
    panel.style.removeProperty('--lpc2');
    try { localStorage.removeItem(KEY); } catch (_) {}
  }
  applyRatios();
  window.addEventListener('resize', applyRatios);

  panel.querySelectorAll('.lp-gutter').forEach(g => {
    g.addEventListener('pointerdown', e => {
      e.preventDefault();
      const gi = +g.dataset.g;          // 0 = Act|Rec · 1 = Rec|Pool
      const a = gi, b = gi + 1;          // cards adyacentes
      const cs = cards();
      const w = cs.map(c => c.getBoundingClientRect().width);
      const startX = e.clientX;
      g.classList.add('dragging');
      g.setPointerCapture?.(e.pointerId);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';

      const move = ev => {
        let dx = ev.clientX - startX;
        dx = Math.max(dx, MIN - w[a]);   // a no baja de MIN
        dx = Math.min(dx, w[b] - MIN);   // b no baja de MIN
        const cur = w.slice();
        cur[a] = w[a] + dx;
        cur[b] = w[b] - dx;
        panel.style.setProperty('--lpc0', cur[0] + 'px');
        panel.style.setProperty('--lpc1', cur[1] + 'px');
        panel.style.setProperty('--lpc2', cur[2] + 'px');
      };
      const up = () => {
        g.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        // Congela como proporciones para resistir cambios de ancho de ventana
        const fin = cards().map(c => c.getBoundingClientRect().width);
        const sum = fin.reduce((s, v) => s + v, 0) || 1;
        ratios = fin.map(v => v / sum);
        try { localStorage.setItem(KEY, JSON.stringify(ratios)); } catch (_) {}
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    });
    g.addEventListener('dblclick', () => {
      clearRatios();
      toast('↺ Anchos del strip restaurados', 'success');
    });
  });
})();

// ─── Divisor horizontal del strip (↕ altura) ───
// Arrastra ↕ para ajustar la altura del strip vs la tabla (reclamar el espacio
// de las cards para ver más cuentas). Doble-click restaura. Persiste en
// localStorage. Solo aplica a la vista Cuentas (#accountsMain).
(function initLpVResize() {
  const panel = document.getElementById('adminPanel');
  const gutter = document.getElementById('lpVGutter');
  const main = document.getElementById('accountsMain');
  if (!panel || !gutter || !main) return;
  const KEY = 'bmx.lpHeight.v1';
  const MIN = 96;
  const apply = h => { panel.style.height = h + 'px'; panel.style.minHeight = h + 'px'; };
  function maxH() { const m = main.clientHeight; return m > 300 ? m - 220 : 600; }
  try {
    const saved = parseInt(localStorage.getItem(KEY) || '', 10);
    if (saved > 0) apply(Math.min(Math.max(saved, MIN), 600));
  } catch (_) {}

  gutter.addEventListener('pointerdown', e => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = panel.getBoundingClientRect().height;
    const mx = maxH();
    gutter.classList.add('dragging');
    gutter.setPointerCapture?.(e.pointerId);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    const move = ev => {
      let h = startH + (ev.clientY - startY);
      h = Math.max(MIN, Math.min(h, mx));
      apply(h);
    };
    const up = () => {
      gutter.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      try { localStorage.setItem(KEY, String(Math.round(panel.getBoundingClientRect().height))); } catch (_) {}
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
  gutter.addEventListener('dblclick', () => {
    panel.style.removeProperty('height');
    panel.style.removeProperty('min-height');
    try { localStorage.removeItem(KEY); } catch (_) {}
    toast('↕ Altura del panel restaurada', 'success');
  });
})();

// Activity table — clicks interactivos
$('#actTable').addEventListener('click', e => {
  // Línea humanizada → abre detalle de cuenta
  const line = e.target.closest('.act-line[data-open-email]');
  if (line && line.dataset.openEmail) {
    e.stopPropagation();
    openAccountByEmail(line.dataset.openEmail);
    return;
  }
  const tgt = e.target.closest('.act-target');
  if (tgt && tgt.dataset.email) {
    // Lleva a Cuentas con esa cuenta filtrada en search
    searchQuery = tgt.dataset.email.toLowerCase();
    $('#searchInput').value = tgt.dataset.email;
    showSection('accounts');
    renderTable();
    return;
  }
  const who = e.target.closest('.act-who');
  if (who && who.dataset.who) {
    activityFilter.who = isNaN(+who.dataset.who) ? who.dataset.who : +who.dataset.who;
    activityPage = 1;
    renderActivity();
    return;
  }
});
$('#actClearFilter')?.addEventListener('click', () => {
  _restoreActivityFilters();
});

function _restoreActivityFilters() {
  activityFilter = { kind: '', who: null, time: 'all', q: '' };
  activityPage = 1;
  document.querySelectorAll('.seg[data-seg="actkind"] button').forEach((b, i) => b.classList.toggle('on', i === 0));
  document.querySelectorAll('.seg[data-seg="acttime"] button').forEach((b, i) => b.classList.toggle('on', i === 0));
  const s = $('#actSearch'); if (s) s.value = '';
  reloadActivity();
}

// Búsqueda local en el feed (debounced)
let _actSearchDeb = null;
$('#actSearch')?.addEventListener('input', e => {
  clearTimeout(_actSearchDeb);
  _actSearchDeb = setTimeout(() => {
    activityFilter.q = e.target.value;
    activityPage = 1;
    renderActivity();
  }, 180);
});

// Chips de operadores
$('#actOpsChips')?.addEventListener('click', e => {
  const chip = e.target.closest('.act-op-chip');
  if (!chip) return;
  const who = chip.dataset.who;
  activityFilter.who = (who === '' || who == null) ? null
                     : (isNaN(+who) ? who : +who);
  activityPage = 1;
  renderActivity();
});

// Page size
$('#actPageSize')?.addEventListener('change', e => {
  activityPageSize = parseInt(e.target.value, 10) || 50;
  activityPage = 1;
  renderActivity();
});

// Restaurar
$('#actBtnReset')?.addEventListener('click', _restoreActivityFilters);

// Refrescar (recarga del backend)
$('#actBtnRefresh')?.addEventListener('click', async () => {
  const btn = $('#actBtnRefresh');
  btn.classList.add('spinning');
  await reloadActivity();
  setTimeout(() => btn.classList.remove('spinning'), 700);
});

// Paginación
$('#actPbPages')?.addEventListener('click', e => {
  const b = e.target.closest('.pb-btn');
  if (!b || b.disabled) return;
  const p = parseInt(b.dataset.page, 10);
  if (!isNaN(p) && p !== activityPage) {
    activityPage = p;
    renderActivity();
  }
});

// ─── Marcador 📌 (toggle privado — NO recarga tabla) ───
async function toggleMark(email, btn) {
  try {
    const res = await (await fetch('/api/marks/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })).json();
    if (res.marked) markedSet.add(email); else markedSet.delete(email);
    if (btn) {
      btn.classList.toggle('on', !!res.marked);
      btn.title = res.marked ? 'Quitar marca' : 'Fijar para después';
    }
    loadRecientes();
  } catch {}
}

// ─── Tooltip hover para iconos 💳/📝 + click para nota rápida ───
let _rowTipEl = null;
let _rowTipTimer = null;
function _hideRowTip() {
  if (_rowTipEl) { _rowTipEl.remove(); _rowTipEl = null; }
  if (_rowTipTimer) { clearTimeout(_rowTipTimer); _rowTipTimer = null; }
}
async function _showRowTip(target, kind, accId) {
  _hideRowTip();
  const tip = document.createElement('div');
  tip.className = 'row-tip';
  tip.innerHTML = `<div class="row-tip-loading"><span class="dep-spinner"></span></div>`;
  document.body.appendChild(tip);
  _rowTipEl = tip;
  // Posicionar
  const r = target.getBoundingClientRect();
  tip.style.left = (r.right + 8) + 'px';
  tip.style.top = (r.top - 4) + 'px';
  try {
    if (kind === 'cards') {
      const data = await fetch(`/api/accounts/${accId}/cards-pipe`).then(r => r.json());
      tip.innerHTML = (data.cards || []).map(c =>
        `<div class="row-tip-row"><span class="mono">${esc(c.pipe)}</span><span class="dim mono"> · ${c.approved}/${c.deposits} ok</span></div>`
      ).join('') || '<div class="dim">Sin tarjetas</div>';
    } else if (kind === 'notes') {
      const data = await fetch(`/api/accounts/${accId}/notes-summary`).then(r => r.json());
      tip.innerHTML = (data.notes || []).map(n =>
        `<div class="row-tip-row"><b>${esc(n.created_by_name || '—')}</b> <span class="dim mono">${fmtAgo(n.created_at)}</span><div>${esc(n.note_text)}</div></div>`
      ).join('') || '<div class="dim">Sin notas</div>';
    }
    // Re-position si el contenido se movió
    const r2 = target.getBoundingClientRect();
    const tipRect = tip.getBoundingClientRect();
    if (r2.right + tipRect.width + 16 > window.innerWidth) {
      tip.style.left = (r2.left - tipRect.width - 8) + 'px';
    }
  } catch (e) {
    tip.innerHTML = `<div class="dim">Error: ${esc(e.message)}</div>`;
  }
}
function _attachRowIconTooltip() {
  const tbl = $('#accTable');
  tbl.addEventListener('mouseover', e => {
    const ic = e.target.closest('.row-ic.ic-cards, .row-ic.ic-notes');
    if (!ic) return;
    const accId = parseInt(ic.dataset.id);
    const kind = ic.classList.contains('ic-cards') ? 'cards' : 'notes';
    _rowTipTimer = setTimeout(() => _showRowTip(ic, kind, accId), 250);
  });
  tbl.addEventListener('mouseout', e => {
    if (e.target.closest('.row-ic')) _hideRowTip();
  });
}
_attachRowIconTooltip();

// Quick note: ➕ icon
async function _quickAddNote(accId, email) {
  const text = prompt(`Nota rápida para ${email}:`);
  if (!text || !text.trim()) return;
  try {
    const r = await fetch(`/api/accounts/${accId}/notes`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text: text.trim() }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    toast('✓ Nota guardada', 'success');
    reload();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ─── Tabla: click en checkbox, click en combo (copia), click en fila (detalle) ───
$('#accTable').addEventListener('click', e => {
  // Clicks DENTRO del panel inline de detalle los maneja su propio listener;
  // este handler de tabla los ignora (si no, toggle-aría la selección de la
  // cuenta al clickear cualquier parte del panel).
  if (e.target.closest('.acc-detail')) return;
  // Botón ↻ por fila — refresh SOLO esa cuenta, no toca paginación ni filtros
  const refOne = e.target.closest('.row-refresh-one');
  if (refOne?.dataset.id) {
    e.stopPropagation();
    refreshSingleRow(parseInt(refOne.dataset.id), refOne);
    return;
  }
  // Iconos de fila — interceptan ANTES de que se abra el modal
  const ic = e.target.closest('.row-ic');
  if (ic) {
    e.stopPropagation();
    if (ic.classList.contains('ic-mark')) {
      // 📌 — toggle marcador; NO abre detalle, NO recarga tabla
      toggleMark(ic.dataset.markEmail, ic);
      return;
    }
    const accId = parseInt(ic.dataset.id);
    const email = ic.dataset.email;
    if (ic.classList.contains('ic-add')) {
      _quickAddNote(accId, email);
    } else {
      // 💳 / 📝 → abre modal de detalle
      openDetailModal(accId);
    }
    return;
  }
  const th = e.target.closest('th.th-sort');
  if (th?.dataset.sort) { sortRows(th.dataset.sort); return; }
  const cb = e.target.closest('.rowsel');
  if (cb) {
    const id = parseInt(cb.dataset.id);
    if (cb.checked) selectedIds.add(id); else selectedIds.delete(id);
    const tr = cb.closest('tr');
    if (tr) tr.classList.toggle('row-sel', cb.checked);
    updateCmdBar();
    return;
  }
  // Click izquierdo sobre el combo (email:password) en la tabla principal → copiar
  // Va ANTES del row-toggle para no marcar la cuenta cuando solo querés copiar.
  const comboB = e.target.closest('td.combo b');
  if (comboB && comboB.dataset.combo) {
    e.stopPropagation();
    navigator.clipboard.writeText(comboB.dataset.combo)
      .then(() => toast(`✓ ${comboB.dataset.combo}`, 'success'))
      .catch(err => toast(`Error: ${err.message}`, 'error'));
    return;
  }
  if (e.target.id === 'selAll') {
    const visible = getVisible();
    if (e.target.checked) visible.forEach(r => selectedIds.add(r.id));
    else visible.forEach(r => selectedIds.delete(r.id));
    renderTable();
    return;
  }
  // Botón "Detalles" — único acceso al modal completo
  const detBtn = e.target.closest('.row-details');
  if (detBtn?.dataset.id) {
    e.stopPropagation();
    openDetailModal(parseInt(detBtn.dataset.id));
    return;
  }
  // Click derecho sobre el combo → copiar (preserva selección sobre click izq)
  // (el handler normal de copiar [data-combo] se atiende vía contextmenu abajo)

  // Click en cualquier parte de la fila (excepto los handlers ya atendidos arriba)
  // → toggle selección. NO abre modal.
  const tr = e.target.closest('tr');
  if (tr && tr.dataset.id) {
    const id = parseInt(tr.dataset.id);
    const wasSelected = selectedIds.has(id);
    if (wasSelected) selectedIds.delete(id);
    else selectedIds.add(id);
    tr.classList.toggle('row-sel', !wasSelected);
    const cb = tr.querySelector('.rowsel');
    if (cb) cb.checked = !wasSelected;
    updateCmdBar();
  }
});

// Click derecho sobre combo → copiar
$('#accTable').addEventListener('contextmenu', e => {
  const comboB = e.target.closest('td.combo b');
  if (comboB && comboB.dataset.combo) {
    e.preventDefault();
    navigator.clipboard.writeText(comboB.dataset.combo)
      .then(() => toast(`✓ ${comboB.dataset.combo}`, 'success'))
      .catch(err => toast(`Error: ${err.message}`, 'error'));
  }
});

// Modal de detalle: botón "Validar CURP en gob.mx"
$('#detModalBody').addEventListener('click', async e => {
  const vBtn = e.target.closest('.curp-validate-btn');
  if (vBtn?.dataset.accId) {
    e.preventDefault();
    e.stopPropagation();
    const accId = parseInt(vBtn.dataset.accId);
    await openCurpValidator(accId);
    return;
  }
});

async function openCurpValidator(accId) {
  // Re-fetch datos por si cambiaron
  let d;
  try {
    d = await fetch(`/api/accounts/${accId}/details`).then(r => r.json());
  } catch (e) { toast(`Error: ${e.message}`, 'error'); return; }
  const bdate = d.birthdate ? String(d.birthdate).split('T')[0].split(' ')[0] : null;
  if (!d.fullname || !bdate) { toast('Faltan nombre o fecha de nacimiento', 'error'); return; }
  const split = _splitFullname(d.fullname);
  if (!split) { toast('No se pudo separar nombre', 'error'); return; }
  const m = bdate.match(/^(\d{4})-(\d{2})-(\d{2})/);
  const [_, yyyy, mm, dd] = m || [];
  const sex = _inferSex(split.nombre);
  const state = _detectStateCode(d.address);
  // Texto pre-formateado para copiar al portapapeles
  const fields = [
    ['Nombre(s)', split.nombre],
    ['Primer apellido', split.ap1],
    ['Segundo apellido', split.ap2 || '—'],
    ['Día', dd], ['Mes', mm], ['Año', yyyy],
    ['Sexo', sex === 'M' ? 'Mujer' : 'Hombre'],
    ['Estado (código)', state],
  ];
  const blob = fields.map(([k, v]) => `${k}\t${v}`).join('\n');

  // Popup overlay con datos + botones
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal" style="width:480px">
      <header class="modal-head">
        <div class="modal-title"><span class="modal-icon">🔍</span><span>Validar CURP en gob.mx</span></div>
        <button class="modal-close" data-act="close" title="Cerrar">×</button>
      </header>
      <div class="modal-body" style="padding:16px;display:flex;flex-direction:column;gap:12px">
        <p style="font-size:12px;color:var(--text-dim);margin:0">
          gob.mx tiene Akamai anti-bot que bloquea automatización. Pero a mano es 10s:
        </p>
        <ol style="font-size:12px;line-height:1.6;padding-left:18px;color:var(--text-dim);margin:0">
          <li>Picar <b>📋 Copiar datos</b> abajo</li>
          <li>Picar <b>🔗 Abrir gob.mx</b> (nueva pestaña)</li>
          <li>Pegar valores en cada campo del form (Tab+Ctrl+V)</li>
          <li>Picar <b>Buscar</b>, copiar el CURP que sale</li>
          <li>Volver acá y pegarlo abajo + Guardar</li>
        </ol>
        <table class="curp-fields-table">
          ${fields.map(([k, v]) => `<tr><td class="dim mono">${esc(k)}</td><td><b class="mono">${esc(v)}</b></td></tr>`).join('')}
        </table>
        <div style="display:flex;gap:8px">
          <button class="seg-btn" data-act="copy" title="Copia los 8 valores tab-separados">📋 Copiar datos</button>
          <button class="seg-btn" data-act="open" title="Abre gob.mx en nueva pestaña" style="background:var(--accent-soft);color:var(--accent);border-color:var(--accent)">🔗 Abrir gob.mx</button>
        </div>
        <div style="border-top:1px solid var(--hairline);padding-top:12px;margin-top:4px">
          <label style="font-size:10.5px;color:var(--text-muted);font-family:var(--font-mono);text-transform:uppercase;letter-spacing:0.4px">CURP correcto</label>
          <input type="text" id="curpFinalInput" maxlength="18" placeholder="Pegalo aquí (18 chars)"
                 style="width:100%;margin-top:6px;background:rgba(0,0,0,0.30);border:1px solid var(--hairline);border-radius:6px;padding:8px 12px;color:var(--text);font:inherit;font-family:var(--font-mono);text-transform:uppercase">
          <div style="display:flex;justify-content:flex-end;margin-top:8px">
            <button class="seg-btn" data-act="save" style="background:var(--accent-soft);color:var(--accent);border-color:var(--accent)">💾 Guardar CURP</button>
          </div>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  overlay.addEventListener('click', async ev => {
    const act = ev.target.closest('[data-act]')?.dataset.act;
    if (!act && ev.target !== overlay) return;
    if (act === 'close' || ev.target === overlay) { overlay.remove(); return; }
    if (act === 'copy') {
      try {
        await navigator.clipboard.writeText(blob);
        toast('✓ Datos copiados', 'success');
      } catch (e) { toast(`Error: ${e.message}`, 'error'); }
      return;
    }
    if (act === 'open') {
      window.open('https://www.gob.mx/curp/#tab-02', '_blank');
      return;
    }
    if (act === 'save') {
      const v = $('#curpFinalInput').value.trim().toUpperCase();
      if (v.length !== 18) { toast('CURP debe tener 18 caracteres', 'error'); return; }
      try {
        const r = await fetch(`/api/accounts/${accId}/curp`, {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ curp: v }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        toast(`✓ CURP guardado: ${v}`, 'success');
        overlay.remove();
        openDetailModal(accId);  // re-render
      } catch (e) { toast(`Error: ${e.message}`, 'error'); }
    }
  });
}

// ════════════════════════════════════════════════════════════════════════
// Listeners del PANEL INLINE de detalle (acordeón en #accTable).
// Delegación sobre #accTable para sobrevivir re-renders de renderTable.
// El copiar [data-copy] ya lo maneja el listener global de document.body
// (capture). Aquí: Depositar, toggle "En uso", agregar/borrar nota,
// agregar tarjeta, ver más/menos movimientos.
// ════════════════════════════════════════════════════════════════════════
$('#accTable').addEventListener('click', async e => {
  // No interceptar si el click fue dentro de la tabla normal (no del panel).
  const panel = e.target.closest('.acc-detail');
  if (!panel) return;

  // --- Marcador 📌 en el panel de detalle ---
  const markBtnDetail = e.target.closest('.ic-mark[data-mark-email]');
  if (markBtnDetail) {
    e.preventDefault(); e.stopPropagation();
    toggleMark(markBtnDetail.dataset.markEmail, markBtnDetail);
    return;
  }

  // --- Depositar (toggle: mismo botón abre/cierra el panel de depósito) ---
  const depBtn = e.target.closest('.d-deposit-btn');
  if (depBtn?.dataset.accId) {
    e.preventDefault(); e.stopPropagation();
    const accId = parseInt(depBtn.dataset.accId);
    const sameSingle = _depDrawerOpen && _depMode === 'single'
      && _depAccountIds.length === 1 && _depAccountIds[0] === accId;
    if (sameSingle) {
      closeDepositModal();
    } else {
      openDepositModal(accId);
    }
    return;
  }

  // --- Toggle "En uso" (lock/unlock) ---
  const inuse = e.target.closest('[data-inuse]');
  if (inuse) {
    e.preventDefault(); e.stopPropagation();
    const accId = parseInt(inuse.dataset.inuse);
    const turningOn = !inuse.classList.contains('on');
    // Optimista (microanimación pop la da el .on en CSS)
    inuse.classList.toggle('on', turningOn);
    try {
      if (turningOn) {
        const op = state.user?.username || 'op';
        const r = await fetch(`/api/accounts/${accId}/lock`, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ operator: op, hours: 2 }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        if (detailDataCache[accId]) { detailDataCache[accId].locked_by = data.locked_by; detailDataCache[accId].locked_until = data.locked_until; }
        toast('🔖 En uso (lock 2h)', 'success');
      } else {
        const r = await fetch(`/api/accounts/${accId}/unlock`, { method: 'POST' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        if (detailDataCache[accId]) { detailDataCache[accId].locked_by = null; detailDataCache[accId].locked_until = null; }
        toast('🔓 Liberada', '');
      }
      // refresca fila en la tabla (lock chip) sin reconstruir el panel abierto
      _liveReload();
    } catch (err) {
      inuse.classList.toggle('on', !turningOn);  // revert
      toast(`Error: ${err.message}`, 'error');
    }
    return;
  }

  // --- Validar/corregir CURP en gob.mx (el handler viejo estaba en #detModalBody,
  //     que ya no se usa con el panel inline) ---
  const vBtn = e.target.closest('.curp-validate-btn');
  if (vBtn?.dataset.accId) {
    e.preventDefault(); e.stopPropagation();
    openCurpValidator(parseInt(vBtn.dataset.accId));
    return;
  }

  // --- expandir/cerrar una transacción nuestra (revela la tarjeta usada) ---
  const tog = e.target.closest('[data-mv-toggle]');
  if (tog) {
    e.preventDefault(); e.stopPropagation();
    const item = tog.closest('.mitem');
    const rev = item?.querySelector('.mrev');
    if (rev) { rev.hidden = !rev.hidden; item.classList.toggle('mitem-open', !rev.hidden); }
    return;
  }

  // --- paginador de movimientos (10/pág) ---
  const pg = e.target.closest('[data-mv-pg]');
  if (pg) {
    e.preventDefault(); e.stopPropagation();
    const np = parseInt(pg.dataset.mvPg);
    if (!isNaN(np) && np >= 0) { _mvPage[expandedAccountId] = np; _injectExpandedDetail(true); }
    return;
  }

  // --- Borrar nota (SA) ---
  const del = e.target.closest('.srow-del');
  if (del?.dataset.noteId) {
    e.preventDefault(); e.stopPropagation();
    const accId = expandedAccountId;
    const noteId = parseInt(del.dataset.noteId);
    if (!confirm('¿Borrar esta nota?')) return;
    try {
      await deleteNote(accId, noteId);
      if (detailDataCache[accId]) detailDataCache[accId].notes = (detailDataCache[accId].notes || []).filter(n => n.id !== noteId);
      toast('✓ Nota borrada', 'success');
      _injectExpandedDetail(true);
    } catch (err) { toast(`Error: ${err.message}`, 'error'); }
    return;
  }

  // --- Agregar nota: muestra textarea inline ---
  const addNote = e.target.closest('[data-add-note]');
  if (addNote) {
    e.preventDefault(); e.stopPropagation();
    _showInlineAddForm(parseInt(addNote.dataset.addNote), 'note');
    return;
  }

  // --- Agregar tarjeta: muestra input inline ---
  const addCard = e.target.closest('[data-add-card]');
  if (addCard) {
    e.preventDefault(); e.stopPropagation();
    _showInlineAddForm(parseInt(addCard.dataset.addCard), 'card');
    return;
  }

  // --- Guardar/cancelar del form inline ---
  const saveBtn = e.target.closest('.addform .save');
  if (saveBtn) {
    e.preventDefault(); e.stopPropagation();
    await _submitInlineAddForm(saveBtn.closest('.addform'));
    return;
  }
  const cancelBtn = e.target.closest('.addform .cancel');
  if (cancelBtn) {
    e.preventDefault(); e.stopPropagation();
    const host = cancelBtn.closest('.addform-host');
    if (host) host.innerHTML = '';
    return;
  }
});

// Render del form inline para agregar nota/tarjeta dentro del panel "Guardado".
function _showInlineAddForm(accId, kind) {
  const host = document.querySelector(`.acc-detail .addform-host[data-acc-id="${accId}"]`);
  if (!host) return;
  if (kind === 'note') {
    host.innerHTML = `<div class="addform" data-acc-id="${accId}" data-kind="note">
      <textarea class="addform-input" placeholder="Nueva nota…" maxlength="2000"></textarea>
      <div class="addform-row"><button class="cancel">Cancelar</button><button class="save">Guardar nota</button></div>
    </div>`;
  } else {
    // Las tarjetas se guardan al APROBARSE un depósito (auto-save en deposits.py).
    // No hay endpoint de alta manual y no tocamos la BD del bot. Por eso este
    // form abre el drawer de depósito con la tarjeta precargada: al aprobar,
    // la tarjeta queda guardada por el flujo existente.
    host.innerHTML = `<div class="addform" data-acc-id="${accId}" data-kind="card">
      <input class="addform-input" type="text" placeholder="5264246817962301|06|28|123" autocomplete="off" spellcheck="false">
      <div class="addform-row"><button class="cancel">Cancelar</button><button class="save">Probar y guardar (depositar)</button></div>
    </div>`;
  }
  const inp = host.querySelector('.addform-input');
  if (inp) inp.focus();
}

// Submit del form inline. Notas → POST /notes. Tarjetas → POST /cards (pipe).
async function _submitInlineAddForm(form) {
  if (!form) return;
  const accId = parseInt(form.dataset.accId);
  const kind = form.dataset.kind;
  const inp = form.querySelector('.addform-input');
  const val = (inp?.value || '').trim();
  if (!val) { inp?.focus(); return; }
  const saveBtn = form.querySelector('.save');
  if (saveBtn) saveBtn.disabled = true;
  try {
    if (kind === 'note') {
      const data = await submitNote(accId, val);
      // actualiza cache
      if (detailDataCache[accId]) {
        const me = state.user?.username || 'tú';
        const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
        detailDataCache[accId].notes = [
          { id: data.id, note_text: val, created_at: data.created_at || now, created_by_name: me, mine: true },
          ...(detailDataCache[accId].notes || []),
        ];
      }
      toast('✓ Nota guardada', 'success');
    } else {
      // Tarjeta: NO hay alta manual (las tarjetas se guardan al aprobarse un
      // depósito). Abrimos el drawer de depósito con la tarjeta precargada;
      // al aprobar, el flujo existente la guarda en account_cards.
      const host = form.closest('.addform-host');
      if (host) host.innerHTML = '';
      openDepositModal(accId);
      setTimeout(() => {
        const inp2 = $('#depCardPipe');
        if (inp2) { inp2.value = val; inp2.focus(); }
      }, 120);
      return;
    }
    _injectExpandedDetail(true);
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
    if (saveBtn) saveBtn.disabled = false;
  }
}

// Modal de detalle: botón "Depositar en esta cuenta"
$('#detModalBody').addEventListener('click', e => {
  const btn = e.target.closest('.d-deposit-btn');
  if (!btn) return;
  e.preventDefault();
  e.stopPropagation();
  const accId = parseInt(btn.dataset.accId);
  if (!accId) return;
  closeDetailModal();
  setTimeout(() => openDepositModal(accId), 80);
});

// Modal de detalle: botón "Seleccionar" — toggle multi-selección sin cerrar el panel
$('#detModalBody').addEventListener('click', e => {
  const btn = e.target.closest('.d-select-btn');
  if (!btn) return;
  e.preventDefault();
  e.stopPropagation();
  const accId = parseInt(btn.dataset.accId);
  if (!accId) return;
  const willSelect = !selectedIds.has(accId);
  if (willSelect) selectedIds.add(accId);
  else selectedIds.delete(accId);
  // Re-render del propio botón
  btn.classList.toggle('is-selected', willSelect);
  btn.textContent = willSelect ? '✓ Seleccionada · click para quitar' : '+ Seleccionar (multi)';
  // Refrescar fila visible en la tabla principal (checkbox + clase row-sel)
  const tr = document.querySelector(`#accTable tr[data-id="${accId}"]`);
  if (tr) {
    tr.classList.toggle('row-sel', willSelect);
    const cb = tr.querySelector('.rowsel');
    if (cb) cb.checked = willSelect;
  }
  // Refrescar la barra de comandos (cuenta seleccionada, botones Depositar/Copiar combos)
  if (typeof updateCmdBar === 'function') updateCmdBar();
  toast(willSelect ? '✓ Sumada a la selección' : '— Removida de selección', willSelect ? 'success' : '');
});

// Modal de detalle: form de notas (submit + delete)
$('#detModalBody').addEventListener('submit', async e => {
  const form = e.target.closest('.d-note-form');
  if (!form) return;
  e.preventDefault();
  const accId = parseInt(form.dataset.accId);
  const inp = form.querySelector('.d-note-input');
  const text = inp.value.trim();
  if (!text) { inp.focus(); return; }
  const btn = form.querySelector('.d-note-submit');
  btn.disabled = true;
  try {
    const data = await submitNote(accId, text);
    inp.value = '';
    toast('✓ Nota guardada', 'success');
    // Append optimista — sin re-render del modal
    const isSA = state.user?.role === 'superadmin';
    const list = $('#dNotesList');
    const empty = $('#dNotesEmpty');
    if (empty) empty.remove();
    const li = document.createElement('li');
    li.dataset.noteId = data.id;
    li.innerHTML = `<div class="d-note-head">
      <span class="d-note-by">${esc(state.user?.username || 'tú')}</span>
      <span class="d-note-when dim mono">ahora</span>
      ${isSA ? `<button class="d-note-del" data-note-id="${data.id}" title="Borrar (SA)">✕</button>` : ''}
    </div>
    <div class="d-note-body">${esc(text)}</div>`;
    list.insertBefore(li, list.firstChild);
    const cnt = $('#dNotesCount');
    if (cnt) cnt.textContent = list.children.length;
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
  }
});
$('#detModalBody').addEventListener('click', async e => {
  const del = e.target.closest('.d-note-del');
  if (!del) return;
  e.preventDefault();
  e.stopPropagation();
  const noteId = parseInt(del.dataset.noteId);
  const li = del.closest('li[data-note-id]');
  const form = $('#detModalBody').querySelector('.d-note-form');
  const accId = form ? parseInt(form.dataset.accId) : null;
  if (!accId || !noteId) return;
  if (!confirm('¿Borrar esta nota?')) return;
  try {
    await deleteNote(accId, noteId);
    if (li) li.remove();
    toast('✓ Nota borrada', 'success');
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  }
});

// Cerrar modal detalle: X, click fuera, Escape
$('#detModalClose').addEventListener('click', closeDetailModal);
$('#detModalOverlay').addEventListener('click', e => {
  if (e.target.id === 'detModalOverlay') closeDetailModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !$('#detModalOverlay').classList.contains('hidden')) {
    closeDetailModal();
  }
});

// ─── Drag-select sobre cualquier celda de la fila ───
// Pointer Events: cubre mouse + touch + pen sin long-press.
let _dragMode = null;  // null | 'select' | 'deselect'
let _dragPointerId = null;
let _dragLastId = null;  // anti-toggle: no re-tocar la misma fila durante un drag

function _toggleRowSelection(tr, wantChecked) {
  if (!tr) return;
  const cb = tr.querySelector('.rowsel');
  if (!cb) return;
  const id = parseInt(cb.dataset.id);
  if (selectedIds.has(id) === wantChecked) return;
  cb.checked = wantChecked;
  if (wantChecked) selectedIds.add(id); else selectedIds.delete(id);
  tr.classList.toggle('row-sel', wantChecked);
  updateCmdBar();
}

function _rowAtPoint(x, y) {
  const el = document.elementFromPoint(x, y);
  if (!el) return null;
  // Ignora interactivos (botones / inputs) para drag
  if (el.closest('button, a, input, .row-details, .row-ic, .help-dismiss')) return null;
  return el.closest('#accTable tbody tr[data-id]');
}

const _accTable = $('#accTable');
_accTable.addEventListener('pointerdown', e => {
  // Ignorar si arrancó en un botón/input
  if (e.target.closest('button, a, input, th, .row-details, .row-ic')) return;
  const tr = e.target.closest('#accTable tbody tr[data-id]');
  if (!tr) return;
  const id = parseInt(tr.dataset.id);
  const isSelected = selectedIds.has(id);
  // Si arrancas en una marcada, el drag deselecciona; si no, selecciona.
  _dragMode = isSelected ? 'deselect' : 'select';
  _dragPointerId = e.pointerId;
  _dragLastId = id;
  try { _accTable.setPointerCapture(e.pointerId); } catch {}
});
_accTable.addEventListener('pointermove', e => {
  if (!_dragMode) return;
  const tr = _rowAtPoint(e.clientX, e.clientY);
  if (!tr) return;
  const id = parseInt(tr.dataset.id);
  if (id === _dragLastId) return;  // misma fila, no re-toggle
  _dragLastId = id;
  e.preventDefault();
  _toggleRowSelection(tr, _dragMode === 'select');
});
function _endDrag(e) {
  if (_dragPointerId != null) {
    try { _accTable.releasePointerCapture(_dragPointerId); } catch {}
    _dragPointerId = null;
  }
  _dragMode = null;
  _dragLastId = null;
}
_accTable.addEventListener('pointerup', _endDrag);
_accTable.addEventListener('pointercancel', _endDrag);
document.addEventListener('pointerup', _endDrag);

// touch-action: none en sel-cell para no scrollear mientras arrastras (CSS lo aplica).

// ─── Admin coachmarks (hints contextuales no invasivos solo para rol admin) ───
const HINTS_KEY = 'admin_hints_v1';
const ADMIN_HINTS = [
  {
    id: 'deposit',
    selector: '.d-deposit-btn',
    side: 'top',                   // prefiere arriba; flecha apunta abajo
    icon: '💳',
    title: 'Depositar en esta cuenta',
    text: 'Click aquí para abrir el modal con 3 modos: ⚡ Una (single), 👥 Multi (matchmaker) o ⏰ Programado (goteo).',
    delay: 0,
  },
  {
    id: 'cards',
    selector: '.d-cards .d-card, .d-section .d-empty',
    selectorPick: 'cards-h4',      // si no hay tarjetas, usa el h4 de la sección
    side: 'left',
    icon: '🗂',
    title: 'Tarjetas guardadas',
    text: 'Click en cualquier tarjeta para copiar su pipe (numero|exp|cvv). Listo para pegar en el modal de depósito.',
    delay: 380,
  },
  {
    id: 'notes',
    selector: '.d-note-input',
    side: 'top',
    icon: '📝',
    title: 'Notas privadas',
    text: 'Apunta aquí cualquier observación de la cuenta. Solo el equipo las ve. Útil para tracking y handoff.',
    delay: 760,
  },
];

function _getHintsDismissed() {
  try { return JSON.parse(localStorage.getItem(HINTS_KEY) || '[]'); }
  catch { return []; }
}
function _isHintDismissed(id) { return _getHintsDismissed().includes(id); }
function _dismissHint(id) {
  const d = _getHintsDismissed();
  if (!d.includes(id)) {
    d.push(id);
    localStorage.setItem(HINTS_KEY, JSON.stringify(d));
  }
}
function _resolveHintTarget(hint) {
  // Caso especial: tarjetas — si no hay tarjetas guardadas, anclar al h4
  if (hint.id === 'cards') {
    const card = document.querySelector('.d-cards .d-card');
    if (card) return card;
    const headers = document.querySelectorAll('#detModalBody .d-section h4');
    for (const h of headers) {
      if (h.textContent.includes('Tarjetas')) return h;
    }
    return null;
  }
  return document.querySelector(hint.selector);
}
function _spawnCoachmark(hint) {
  const target = _resolveHintTarget(hint);
  if (!target) return;
  const rect = target.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return;

  target.classList.add('hint-target-glow');

  const cm = document.createElement('div');
  cm.className = 'coachmark';
  cm.dataset.hintId = hint.id;
  cm.innerHTML = `
    <div class="coachmark-tip">
      <span class="cm-icon">${hint.icon}</span>
      <span>${esc(hint.title)}</span>
      <span class="cm-pill">tip</span>
    </div>
    <div class="coachmark-text">${esc(hint.text)}</div>
    <div class="coachmark-actions">
      <label class="coachmark-dismiss" title="No mostrar este tip nunca más">
        <input type="checkbox"> No volver a mostrar
      </label>
      <button class="coachmark-ok" type="button">Entendido</button>
    </div>`;
  document.body.appendChild(cm);

  // Posicionar después de que el navegador calcule dimensiones reales
  requestAnimationFrame(() => {
    const cmRect = cm.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    const pad = 14;
    let left, top, arrow = hint.side;

    const place = (side) => {
      if (side === 'right') return { l: rect.right + pad, t: rect.top + (rect.height/2) - (cmRect.height/2) };
      if (side === 'left')  return { l: rect.left - cmRect.width - pad, t: rect.top + (rect.height/2) - (cmRect.height/2) };
      if (side === 'top')   return { l: rect.left + (rect.width/2) - (cmRect.width/2), t: rect.top - cmRect.height - pad };
      /* bottom */          return { l: rect.left + (rect.width/2) - (cmRect.width/2), t: rect.bottom + pad };
    };
    const fits = (side, p) => {
      if (side === 'right')  return p.l + cmRect.width <= vw - 8;
      if (side === 'left')   return p.l >= 8;
      if (side === 'top')    return p.t >= 8;
      return p.t + cmRect.height <= vh - 8;
    };

    // Intenta el lado preferido, si no entra prueba alternos
    const order = [hint.side, 'top', 'right', 'bottom', 'left'];
    let chosen = null;
    for (const s of order) {
      const p = place(s);
      if (fits(s, p)) { chosen = { side: s, p }; break; }
    }
    if (!chosen) chosen = { side: hint.side, p: place(hint.side) };

    left = Math.max(8, Math.min(chosen.p.l, vw - cmRect.width - 8));
    top  = Math.max(8, Math.min(chosen.p.t, vh - cmRect.height - 8));
    // Arrow apunta al elemento (lado opuesto al lado del coachmark)
    const arrowMap = { right: 'left', left: 'right', top: 'bottom', bottom: 'top' };
    arrow = arrowMap[chosen.side];

    cm.style.left = `${left}px`;
    cm.style.top = `${top}px`;
    cm.classList.add(`cm-arrow-${arrow}`);
  });

  const close = (forever) => {
    if (forever) _dismissHint(hint.id);
    cm.classList.add('coachmark-exiting');
    target.classList.remove('hint-target-glow');
    setTimeout(() => cm.remove(), 240);
  };
  cm.querySelector('.coachmark-ok').addEventListener('click', () => {
    const forever = cm.querySelector('input[type="checkbox"]').checked;
    close(forever);
  });
}
function showAdminHints() {
  if (state.user?.role !== 'admin') return;  // SA y user no ven hints
  // Espera a que el modal layout estabilice
  setTimeout(() => {
    for (const hint of ADMIN_HINTS) {
      if (_isHintDismissed(hint.id)) continue;
      setTimeout(() => _spawnCoachmark(hint), hint.delay);
    }
  }, 280);
}
function hideAdminHints() {
  document.querySelectorAll('.coachmark').forEach(cm => cm.remove());
  document.querySelectorAll('.hint-target-glow').forEach(el => el.classList.remove('hint-target-glow'));
}

// ─── Detalle de cuenta inline (acordeón debajo de la fila) ───
// openDetailModal conserva su nombre por compat con los callers existentes,
// pero ahora TOGGLEA el panel inline en vez de abrir el modal #detModalOverlay.
async function openDetailModal(id) {
  id = parseInt(id);
  if (!id) return;
  // Toggle: si ya está abierta, cerrar (con micro-animación).
  if (expandedAccountId === id) {
    _closePanelAnimated();
    return;
  }
  expandedAccountId = id;
  _expandedNode = null;  // cuenta distinta → forzar reconstrucción
  // Pinta de inmediato (loading o cache) y luego fetch fresco.
  _injectExpandedDetail(true);
  try {
    const r = await fetch(`/api/accounts/${id}/details`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    detailDataCache[id] = data;
    // Solo re-pinta si sigue abierta esta misma cuenta.
    if (expandedAccountId === id) _injectExpandedDetail(true);
  } catch (e) {
    if (expandedAccountId === id) {
      const cell = _expandedDetailCell();
      if (cell) cell.innerHTML = `<div class="acc-detail"><div class="acc-error">Error: ${esc(e.message)}</div></div>`;
    }
  }
}
function closeDetailModal() {
  _closePanelAnimated();
}
// Cierra el panel con micro-animación: añade .closing, espera la animación y
// recién entonces remueve el nodo y aplica los reload diferidos.
function _closePanelAnimated() {
  const row = document.querySelector('#accTable tbody tr.acc-detail-row');
  if (!row) { expandedAccountId = null; _expandedNode = null; _injectExpandedDetail(); _flushDeferredRender(); return; }
  const tid = expandedAccountId;
  row.classList.add('closing');
  setTimeout(() => {
    if (expandedAccountId === tid) {
      expandedAccountId = null; _expandedNode = null;
      _injectExpandedDetail();
      _flushDeferredRender();
    }
  }, 175);
}

// Devuelve el <td> del panel inline (si está montado), o null.
function _expandedDetailCell() {
  const row = document.querySelector('#accTable tbody tr.acc-detail-row');
  return row ? row.querySelector('td') : null;
}

// Cuenta el número real de <td> de una fila de cuenta (para el colspan del
// panel). La vista simple tiene 7 <td>; la detail, 9. Se cuenta del DOM para
// no depender de constantes desincronizadas (app.js declara colspan 6/8 pero
// genera 7/9 <td>).
function _detailColspan() {
  const anyRow = document.querySelector('#accTable tbody tr[data-id]');
  if (anyRow) return anyRow.querySelectorAll('td').length;
  return 9;   // vista única detallada
}

// Formatea un pipe de tarjeta a "num|MM|YY|cvv" (pipe entre mes y año, sin "/").
// _parse_pipe (backend) acepta este formato de 4 partes, así que sirve para copiar.
function _pipeDisplay(raw) {
  const parts = String(raw || '').replace(/\s/g, '').replace(/\//g, '|').split('|').filter(Boolean);
  if (parts.length === 3) {
    const [num, exp, cvv] = parts;
    if (/^\d{4}$/.test(exp)) return `${num}|${exp.slice(0, 2)}|${exp.slice(2)}|${cvv}`;
    return `${num}|${exp}|${cvv}`;
  }
  return parts.join('|');
}

// Inyecta / actualiza / quita el panel de detalle inline según expandedAccountId.
// rebuild=true → reconstruye el HTML (abrir cuenta, fetch, ver más, agregar nota…).
// rebuild=false (default, lo llama renderTable en cada SSE) → re-inserta el MISMO
// nodo preservando su estado DOM (no se cierran los <details> ni se pierde focus).
function _injectExpandedDetail(rebuild = false) {
  const tbody = document.querySelector('#accTable tbody');
  if (!tbody) return;
  tbody.querySelectorAll('tr.acc-detail-row').forEach(r => r.remove());
  if (!expandedAccountId) {
    document.querySelectorAll('#accTable tbody tr.row-expanded').forEach(r => r.classList.remove('row-expanded'));
    _expandedNode = null;
    return;
  }
  const targetRow = tbody.querySelector(`tr[data-id="${expandedAccountId}"]`);
  if (!targetRow) return;  // la cuenta no está en la página visible
  document.querySelectorAll('#accTable tbody tr.row-expanded').forEach(r => r.classList.remove('row-expanded'));
  targetRow.classList.add('row-expanded');

  if (rebuild || !_expandedNode || _expandedNode.dataset.id !== String(expandedAccountId)) {
    const data = detailDataCache[expandedAccountId];
    const tr = document.createElement('tr');
    tr.className = 'acc-detail-row';
    tr.dataset.id = String(expandedAccountId);
    const td = document.createElement('td');
    td.colSpan = _detailColspan();
    if (!data) {
      td.innerHTML = `<div class="acc-detail"><div class="acc-loading"><span class="dep-spinner"></span> Cargando…</div></div>`;
    } else {
      try {
        td.innerHTML = renderDetail(data);
      } catch (renderErr) {
        console.error('[Detail] renderDetail failed:', renderErr, 'data keys:', Object.keys(data));
        td.innerHTML = `<div class="acc-detail"><div class="acc-error">⚠️ Error renderizando: ${esc(renderErr.message)}</div></div>`;
      }
    }
    tr.appendChild(td);
    _expandedNode = tr;
  } else {
    // Reusa el nodo existente (preserva estado DOM); solo ajusta colspan si cambió la vista.
    const td = _expandedNode.querySelector('td');
    if (td) td.colSpan = _detailColspan();
  }
  targetRow.after(_expandedNode);
}

// ─── Helpers de formato para el panel v14 ───
// "28 may 2026 08:12" partido en día+mes (medio), año (tenue), hora (resaltada).
const _MV_MESES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
function _mvWhen(ts) {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return `<span class="when"><span class="d">—</span></span>`;
  const dd = d.getDate();
  const mes = _MV_MESES[d.getMonth()] || '';
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `<span class="when"><span class="d">${dd} ${mes}</span><span class="y">${yyyy}</span><span class="t">${hh}:${mi}</span></span>`;
}
// Edad en años a partir de birthdate (YYYY-MM-DD).
function _ageFrom(bdate) {
  if (!bdate) return null;
  const m = bdate.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const [, y, mo, da] = m.map(Number);
  const now = new Date();
  let age = now.getFullYear() - y;
  if (now.getMonth() + 1 < mo || (now.getMonth() + 1 === mo && now.getDate() < da)) age--;
  return age >= 0 && age < 120 ? age : null;
}
// DD/MM/YYYY desde YYYY-MM-DD.
function _dmy(bdate) {
  if (!bdate) return null;
  const m = bdate.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : null;
}
// Extrae ciudad + CP del address de forma best-effort (sin inventar).
function _cityCp(address) {
  if (!address) return null;
  const cp = (address.match(/\b(\d{5})\b/) || [])[1] || null;
  // Heurística simple: último segmento textual antes del CP / coma.
  let city = null;
  const parts = String(address).split(',').map(s => s.trim()).filter(Boolean);
  if (parts.length >= 2) city = parts[parts.length - 2] || parts[parts.length - 1];
  return { city, cp };
}

// Icono Phosphor de status por estado de movimiento.
function _mvStatusIcon(state) {
  return ({
    ok:   '<i class="ph-fill ph-check-circle"></i>',
    fail: '<i class="ph-fill ph-prohibit"></i>',
    threeds: '<i class="ph-fill ph-warning-circle"></i>',
    pending: '<i class="ph-fill ph-clock"></i>',
    wd:   '<i class="ph-fill ph-arrow-circle-up"></i>',
  })[state] || '<i class="ph-fill ph-circle"></i>';
}
// Clase de estado para la cápsula (colorea ícono+monto+contorno).
function _mvStateCls(state) {
  // Prefijo mv- para NO colisionar con clases globales (.dep ya existe en la
  // tabla con font mono → causaba que las aprobadas salieran en otra tipografía).
  return ({ ok: 'mv-dep', fail: 'mv-fail', threeds: 'mv-threeds', pending: 'mv-pend', wd: 'mv-wd' })[state] || 'mv-dep';
}
// Monto con signo/triángulo según kind+state.
function _mvAmount(m) {
  const money = fmtMoney(m.amount);
  if (m.kind === 'withdrawal') return `−${money} <span class="tri">▼</span>`;
  if (m.state === 'ok') return `+${money} <span class="tri">▲</span>`;
  if (m.state === 'pending') return `${money} <span class="tri">•</span>`;
  // fail: sin signo, pero con triángulo INVISIBLE para que el número alinee
  // a la derecha igual que las demás filas (mismo ancho de columna).
  return `${money} <span class="tri" style="visibility:hidden">▲</span>`;
}

// Una cápsula de movimiento. Las nuestras son expandibles vía <button> (los
// elementos no-button no reciben clicks fiables dentro de la tabla → bug de
// hit-testing del navegador; los <button> sí).
function _renderMovimiento(m) {
  const stCls = _mvStateCls(m.state);
  const isOurs = m.source === 'dashboard';
  const kindLabel = m.kind === 'withdrawal' ? 'Retiro' : 'Depósito';
  // En fallidas, "Depósito" va en rojo; en 3DS, ámbar (no se acreditó pero no es
  // rechazo del banco).
  const kindHtml = (m.state === 'fail')
    ? `<b style="color:var(--danger)">${kindLabel}</b>`
    : (m.state === 'threeds')
      ? `<b style="color:var(--warn)">${kindLabel} · 3DS</b>`
      : `<b>${kindLabel}</b>`;
  const method = m.method || (m.kind === 'withdrawal' ? '' : '—');
  const methodTxt = method ? ` · ${esc(method)}` : '';
  // "Quién" inline en chiquito junto al método (solo nuestras).
  const whoInline = (isOurs && m.who) ? ` · <span class="mwho">${esc(m.who)}</span>` : '';
  const srcIcon = isOurs
    ? '<i class="ph-fill ph-lightning us"></i>'
    : '<i class="ph-duotone ph-globe-hemisphere-west us"></i>';
  const head = `${_mvWhen(m.when)}<span class="sic">${_mvStatusIcon(m.state)}</span><span class="lbl">${srcIcon}${kindHtml}${methodTxt}${whoInline}</span><span class="amt">${_mvAmount(m)}</span>`;
  if (isOurs) {
    // Pipe con "|" entre mes y año (num|MM|YY|cvv) — parseable por _parse_pipe.
    const pipe = _pipeDisplay(m.card_pipe);
    const cardHtml = pipe
      ? `<i class="ph-duotone ph-credit-card" style="color:var(--acc)"></i> Tarjeta: <button type="button" class="pp d-copy" data-copy="${esc(pipe)}" title="Click para copiar">${esc(pipe)}</button>`
      : `<i class="ph-duotone ph-credit-card" style="color:var(--acc)"></i> <span class="dim">sin tarjeta registrada</span>`;
    // Estado de la transacción a la DERECHA: Approved (verde) / Rejected · 3DS
    // (rojo) / Pendiente (amarillo). Para fallidas usa la razón real si existe.
    let stWord, stWordCls;
    if (m.state === 'ok') { stWord = 'Approved'; stWordCls = 'mv-dep'; }
    else if (m.state === 'pending') { stWord = 'Pendiente'; stWordCls = 'mv-pend'; }
    else {
      const r = (m.reason || '').toUpperCase();
      stWord = r.includes('3DS') ? '3DS'
             : (r.includes('REJECT') || r.includes('DECLIN') || r.includes('BANK')) ? 'Rejected'
             : (m.reason ? m.reason.slice(0, 28) : 'Rejected');
      stWordCls = 'mv-fail';
    }
    return `<div class="mitem ours ${stCls}">
      <button type="button" class="mhead" data-mv-toggle>${head}<span class="exv"><i class="ph-bold ph-caret-down"></i></span></button>
      <div class="mrev" hidden>
        <span class="mrev-card">${cardHtml}</span>
        <span class="mrev-status ${stWordCls}">${esc(stWord)}</span>
      </div>
    </div>`;
  }
  // De la página: NO expandible.
  return `<div class="mitem page ${stCls}"><div class="mhead nohover">${head}<span class="exv noexp"><i class="ph-bold ph-minus"></i></span></div></div>`;
}

function renderDetail(d) {
  const isSA = state.user?.role === 'superadmin';

  // ── DATOS ──────────────────────────────────────────────────────────
  const bdate = d.birthdate ? String(d.birthdate).split('T')[0].split(' ')[0] : null;
  const age = _ageFrom(bdate);
  // Domicilio COMPLETO (sin truncar) — importa el estado + CP. Si no hay, omite.
  const addr = (d.address && d.address !== 'N/A') ? esc(d.address) : null;
  const nameMeta = [
    age != null ? `${age} años` : null,
    addr,
  ].filter(Boolean).join(' · ');
  const nombre = (d.fullname && d.fullname !== 'N/A') ? esc(d.fullname) : '<span class="dim">Sin nombre</span>';

  // CURP — real de BD o estimado (computeCurp). Copiable al click. Tag "est" si calculado.
  const curpStored = (d.curp && d.curp !== 'N/A') ? d.curp : null;
  const curpCalc = !curpStored ? computeCurp(d.fullname, bdate, d.address) : null;
  const curpShown = curpStored || curpCalc || '';
  const curpTag = curpStored ? '' : (curpCalc ? '<span class="est">est</span>' : '');
  const curpBody = curpShown
    ? `<button type="button" class="curp d-copy" data-copy="${esc(curpShown)}" title="Click para copiar">${esc(curpShown)} ${curpTag}</button>`
    : `<span class="curp"><span class="dim">—</span></span>`;
  // Botón validar/corregir en gob.mx (handler existente .curp-validate-btn:
  // abre modal con pasos gob.mx + permite guardar el CURP correcto).
  const curpHtml = `<span class="curp-line">${curpBody}<button type="button" class="curp-validate-btn" data-acc-id="${d.id}" title="Validar / corregir CURP en gob.mx"><i class="ph-bold ph-seal-check"></i></button></span>`;

  const nacimiento = _dmy(bdate) || '—';

  const datos = `
    <div class="datos">
      <div class="dseg dseg-name">
        <span class="nm">${nombre}</span>${age != null ? `<span class="nage">· ${age}</span>` : ''}
      </div>
      <div class="dseg grow">
        <span class="lab">Dirección</span>
        <span class="val addr">${addr || '<span class="dim">—</span>'}</span>
      </div>
      <div class="dseg">
        <span class="lab">Nacimiento</span>
        <span class="val">${nacimiento}</span>
      </div>
      <div class="dseg">
        <span class="lab">CURP</span>
        ${curpHtml}
      </div>
    </div>`;

  // ── MOVIMIENTOS ────────────────────────────────────────────────────
  const movs = Array.isArray(d.movimientos) ? d.movimientos : [];
  const totalPages = Math.max(1, Math.ceil(movs.length / _MV_PER_PAGE));
  let page = _mvPage[d.id] || 0;
  if (page >= totalPages) page = totalPages - 1;
  const start = page * _MV_PER_PAGE;
  const shown = movs.slice(start, start + _MV_PER_PAGE);
  const mvRows = shown.length
    ? shown.map(_renderMovimiento).join('')
    : `<div class="mv-empty">Sin movimientos registrados.</div>`;
  // Paginador interno (10/pág). Clase propia para no chocar con el paginador
  // de la tabla completa.
  const pager = movs.length > _MV_PER_PAGE
    ? `<div class="mv-pager">
        <button type="button" class="mv-pg" data-mv-pg="${page - 1}" ${page === 0 ? 'disabled' : ''} title="Anterior"><i class="ph-bold ph-caret-left"></i></button>
        <span class="mv-pg-info">${start + 1}–${Math.min(start + _MV_PER_PAGE, movs.length)} de ${movs.length}</span>
        <button type="button" class="mv-pg" data-mv-pg="${page + 1}" ${page >= totalPages - 1 ? 'disabled' : ''} title="Siguiente"><i class="ph-bold ph-caret-right"></i></button>
      </div>`
    : '';

  const movimientos = `
    <div class="sec-h">
      <span class="ttl"><i class="ph-duotone ph-arrows-down-up"></i> Movimientos <span class="cnt">${movs.length}</span></span>
      <span class="mv-leg">
        <span><i class="ph-fill ph-lightning" style="color:var(--gold)"></i> nosotros</span>
        <span><i class="ph-duotone ph-globe-hemisphere-west"></i> en la página</span>
      </span>
    </div>
    <div class="mlist">${mvRows}</div>
    ${pager}`;

  // ── GUARDADO (tarjetas + notas) — plegado por default ──────────────
  const cards = (d.cards || []);
  const notes = (d.notes || []);
  const cardRows = cards.map(c => {
    const num = c.card_number || '';
    const cvv = c.card_cvv || '';
    const pipe = _pipeDisplay(`${num}|${c.card_expiry || ''}|${cvv}`);  // num|MM|YY|cvv
    const approved = c.total_approved || 0;
    const total = c.total_deposits || 0;
    const pct = total > 0 ? Math.round((approved / total) * 100) : null;
    const stats = `${approved}/${total} aprobados${pct != null ? ` · <b>${pct}%</b>` : ''}`;
    const isAuto = (c.status || '').toLowerCase() === 'auto' || (c.status || '').toLowerCase().includes('auto');
    const autoTag = isAuto ? ' <span class="autotag">auto</span>' : '';
    const when = c.last_used_at || c.registered_at;
    return `<div class="srow">
      <span class="emo">💳</span>
      <div class="sbody">
        <button type="button" class="pp d-copy" data-copy="${esc(pipe)}" title="Click para copiar">${esc(pipe)}</button>
        <div class="cmeta">${stats}${autoTag}</div>
      </div>
      <span class="rmeta"><i class="ph-fill ph-clock"></i> ${esc(fmtAbsYear(when))}</span>
    </div>`;
  }).join('');
  const noteRows = notes.map(n => `<div class="srow" data-note-id="${n.id}">
      <span class="emo">📝</span>
      <div class="sbody"><div class="ntext">${esc(n.note_text)}</div></div>
      <span class="rmeta"><i class="ph-fill ph-user"></i> ${esc(n.created_by_name || '—')} · ${esc(fmtAbs(n.created_at))}${isSA ? `<button class="srow-del" data-note-id="${n.id}" title="Borrar (SA)">✕</button>` : ''}</span>
    </div>`).join('');
  const savedRows = (cardRows + noteRows) || `<div class="mv-empty">Nada guardado todavía.</div>`;
  const guardado = `
    <details class="coll" open>
      <summary>
        <span class="ttl"><i class="ph-duotone ph-archive"></i> Guardado</span>
        <span class="cnt">💳 ${cards.length} · 📝 ${notes.length}</span>
        <span class="cv2"><i class="ph-bold ph-caret-down"></i></span>
      </summary>
      <div class="srows">${savedRows}</div>
      <div class="addrow">
        <button class="addbtn" data-add-card="${d.id}"><i class="ph-bold ph-plus"></i> Agregar tarjeta</button>
        <button class="addbtn" data-add-note="${d.id}"><i class="ph-bold ph-plus"></i> Agregar nota</button>
      </div>
      <div class="addform-host" data-acc-id="${d.id}"></div>
    </details>`;

  // ── EN USO toggle (lock) + Depositar + 📌 marcador — arriba a la derecha ──
  const isLocked = !!d.locked_by;
  const inuse = `<button type="button" class="inuse${isLocked ? ' on' : ''}" data-inuse="${d.id}" title="${isLocked ? `En uso por ${esc(d.locked_by)}` : 'Marcar en uso (lock 2h)'}"><i class="ph-fill ph-bookmark-simple"></i> En uso</button>`;
  const depBtn = `<button class="b pri d-deposit-btn" data-acc-id="${d.id}"><i class="ph-duotone ph-credit-card"></i><span>Depositar</span></button>`;
  const detailMarked = markedSet.has(d.email);
  const markBtn = `<button type="button" class="row-ic ic-mark det-mark${detailMarked ? ' on' : ''}" data-mark-email="${esc(d.email)}" title="${detailMarked ? 'Quitar marca' : 'Fijar para después'}">📌</button>`;

  // datos ocupa el ancho de la columna izquierda (flex:5); el cluster derecho
  // (En uso + Depositar) ocupa el ancho de la columna derecha (flex:3). Así el
  // botón Depositar queda ARRIBA-derecha y todo cabe sin scroll.
  return `<div class="acc-detail">
    <div class="acc-top">
      ${datos}
      <div class="acc-top-right">${depBtn}${inuse}${markBtn}</div>
    </div>
    <div class="acc-cols">
      <div class="acc-col acc-col-mv">${movimientos}</div>
      <div class="acc-col acc-col-saved">${guardado}</div>
    </div>
  </div>`;
}

async function submitNote(accId, text) {
  const r = await fetch(`/api/accounts/${accId}/notes`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ text }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

async function deleteNote(accId, noteId) {
  const r = await fetch(`/api/accounts/${accId}/notes/${noteId}`, { method: 'DELETE' });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// Copia text al portapapeles. Estrategia: primero execCommand (sincrónico,
// funciona dentro del user gesture sin necesitar permisos especiales).
// Si falla, fallback a navigator.clipboard (async).
function _copyText(txt) {
  if (!txt) return false;
  const short = txt.length > 60 ? txt.slice(0, 60) + '…' : txt;
  // Método 1: execCommand sobre textarea oculto — SINCRÓNICO, más confiable
  let ok = false;
  try {
    const ta = document.createElement('textarea');
    ta.value = txt;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.left = '0';
    ta.style.opacity = '0';
    ta.style.pointerEvents = 'none';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, txt.length);
    ok = document.execCommand('copy');
    document.body.removeChild(ta);
  } catch (_) { ok = false; }
  if (ok) {
    toast(`✓ copiado: ${short}`, 'success');
    return true;
  }
  // Método 2: navigator.clipboard (async) — fallback
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt)
      .then(() => toast(`✓ copiado: ${short}`, 'success'))
      .catch(err => toast(`Error al copiar: ${err.message || err}`, 'error'));
    return true;
  }
  toast('Error al copiar (no hay API disponible)', 'error');
  return false;
}

// Click global: copia [data-copy] o [data-combo] desde cualquier lado del DOM.
// Capture phase (true) para correr ANTES que handlers locales (#accTable, etc).
// Resuelve combo via data-email al momento del click (no al render).
document.body.addEventListener('click', e => {
  const t = e.target.closest('[data-copy], [data-combo]');
  if (!t) return;
  // No interceptar inputs ni botones que NO son d-copy
  if (e.target.closest('input, button:not(.d-copy)') && !t.classList.contains('d-copy')) return;
  // Resolver texto
  let txt = t.dataset.copy || t.dataset.combo || '';
  if (t.dataset.email) {
    const resolved = _resolveComboFromEmail(t.dataset.email);
    if (resolved && resolved.includes(':')) txt = resolved;
    else if (!txt) txt = resolved;
  }
  if (!txt) return;
  // stopPropagation suprime el handler de fila/sort de #accTable
  e.stopPropagation();
  _copyText(txt);
}, true);

// ─── Deposit modal (3 modos: single | multi | schedule) ───
let _depMode = 'single';        // single | multi | schedule
let _depAccountIds = [];        // 1 ó N cuentas
let _depAmount = 50;
let _depReps = 5;
let _depBusy = false;
let _depMmRunId = null;         // run_id del matchmaker (para cancel)
let _depMmAbort = null;         // AbortController del SSE fetch

function setDepMode(mode) {
  _depMode = mode;
  $$('#depModeSeg .dep-drawer-tab').forEach(b => b.classList.toggle('on', b.dataset.mode === mode));

  const isSingle = mode === 'single';
  const isMulti  = mode === 'multi';
  const isSched  = mode === 'schedule';

  // visibilidades
  $('#depTargetBlock').classList.toggle('hidden', isMulti);
  $('#depMultiAccts').classList.toggle('hidden', !isMulti);
  $('#depCardSection').classList.toggle('hidden', isMulti);
  $('#depMultiCards').classList.toggle('hidden', !isMulti);
  $('#depScheduleBlock').classList.toggle('hidden', !isSched);
  // Phase stepper solo aplica a single — ocultar al cambiar de modo
  const _ps = $('#depStepper'); if (_ps) _ps.classList.add('hidden');
  // Vista live de schedule solo aplica a programado — ocultar y limpiar
  if (!isSched) { try { _schedReset(); } catch {} }

  // título
  $('#depDrawerTitle').textContent = isSingle ? 'Depositar' : isMulti ? 'Multicuenta' : 'Programado';
  $('#depAmountHint').textContent = isMulti ? '— por intento (max $50)' : isSched ? '— cada repetición' : '';

  // botón principal
  $('#depExec').textContent = isSingle ? '🚀 Ejecutar depósito'
                            : isMulti ? '🎯 Lanzar Matchmaker'
                            : '⏰ Programar misión';

  // Matchmaker: solo $10 / $50 (su único objetivo es buscar match con monto pequeño)
  const amts = $$('#depAmounts .dep-amt');
  amts.forEach(b => {
    const v = b.dataset.v;
    const allowedInMulti = (v === '10' || v === '50');
    if (isMulti) {
      b.style.display = allowedInMulti ? '' : 'none';
      if (!allowedInMulti && b.classList.contains('on')) {
        b.classList.remove('on');
        amts.forEach(x => { if (x.dataset.v === '50') x.classList.add('on'); });
        _depAmount = 50;
      }
    } else {
      b.style.display = '';
    }
  });

  // Banner de instrucciones según modo
  renderDepHelpBanner(mode);

  // tarjetas guardadas solo aplica en single (1 cuenta) y schedule
  refreshSavedCards();
  // multi: refrescar el panel de cuentas
  if (isMulti) renderMultiAccounts();
}

function renderDepHelpBanner(mode) {
  const banner = $('#depHelpBanner');
  if (!banner) return;
  const helps = {
    single: `<b>⚡ Una</b> · 1 tarjeta a 1 cuenta. Si la pasarela ya está caliente,
             pasa de un jalón. Sirve para reintentos rápidos o tarjetas casadas.`,
    multi:  `<b>👥 Matchmaker</b> · busca qué tarjeta pasa con qué cuenta usando
             montos chicos ($10/$50). Una vez que hay <b>match</b>, la tarjeta se
             casa con esa cuenta — no se vuelve a probar en otras (anti baneo).
             Después puedes <b>programar</b> los siguientes depósitos con esa
             tarjeta ya emparejada.`,
    schedule:`<b>⏰ Programado</b> · 1 tarjeta a 1 cuenta, N depósitos cada 1 min.
              Topes: <b>máx $499 por intento</b> y <b>$1499 acumulado por cuenta
              en 24h</b> desde el primer depósito aprobado. Si pasas, dispara 3DS.
              Te llegará una notif cuando se acerque el fin de las 24h para que
              vuelvas a depositar; si no, la cuenta se libera para los demás.`,
  };
  // Si el user dijo "no mostrar más" para este modo, ocultar
  const dismissed = _isHelpDismissed(`dep_help_${mode}`);
  if (dismissed || !helps[mode]) {
    banner.innerHTML = '';
    banner.classList.add('dim-help');
    // Mini icono ? para volver a mostrar
    if (helps[mode]) {
      banner.innerHTML = `<button class="help-restore" data-mode="${mode}" title="Mostrar instrucciones">ℹ️</button>`;
    }
    return;
  }
  banner.classList.remove('dim-help');
  banner.innerHTML = `
    <div class="help-text">${helps[mode]}</div>
    <button class="help-dismiss" data-key="dep_help_${mode}" title="No volver a mostrar">✕</button>
  `;
}

// Popup custom para window_expired con opción "no volver a mostrar"
function _showWindowExpiredPopup(ev) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal" style="width:440px">
      <header class="modal-head">
        <div class="modal-title"><span class="modal-icon">⏰</span><span>Window 24h cerró</span></div>
        <button class="modal-close" data-act="close" title="Cerrar">×</button>
      </header>
      <div class="modal-body" style="padding:18px">
        <p style="margin-bottom:12px">
          La cuenta <b class="mono">${esc(ev.email)}</b> acaba de cumplir 24h.<br>
          Depositaste <b>$${ev.used_24h.toFixed(2)}</b> en este periodo.
        </p>
        <p style="font-size:12px;color:var(--text-dim);margin-bottom:14px">
          Tienes <b>1 hora</b> para volver a depositar. Si no, la cuenta se libera
          al pool para los demás socios.
        </p>
        <label style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text-muted);margin-bottom:14px">
          <input type="checkbox" id="winDismiss" style="accent-color:var(--accent)">
          No volver a mostrar este popup
        </label>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="seg-btn" data-act="close" title="Solo cierra el popup">Después</button>
          <button class="seg-btn" data-act="open" title="Abrir modal de depósito ya" style="background:var(--accent-soft);color:var(--accent);border-color:var(--accent)">💳 Depositar ahora</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act && e.target !== overlay) return;
    if ($('#winDismiss')?.checked) _dismissHelp('window_expired_popup');
    if (act === 'open') {
      const acc = state.rows.find(r => r.email === ev.email);
      if (acc) openDepositModal(acc.id);
    }
    overlay.remove();
  });
}

// LocalStorage helpers para "no mostrar más"
function _isHelpDismissed(key) {
  try { return localStorage.getItem(`dismiss:${key}`) === '1'; }
  catch { return false; }
}
function _dismissHelp(key) {
  try { localStorage.setItem(`dismiss:${key}`, '1'); } catch {}
}
function _undismissHelp(key) {
  try { localStorage.removeItem(`dismiss:${key}`); } catch {}
}

// Handler global para ✕ y ℹ️ del banner
document.addEventListener('click', e => {
  const dismiss = e.target.closest('.help-dismiss');
  if (dismiss?.dataset.key) {
    _dismissHelp(dismiss.dataset.key);
    renderDepHelpBanner(_depMode);
    return;
  }
  const restore = e.target.closest('.help-restore');
  if (restore?.dataset.mode) {
    _undismissHelp(`dep_help_${restore.dataset.mode}`);
    renderDepHelpBanner(restore.dataset.mode);
    return;
  }
});

async function openDepositModal(accountId, opts = {}) {
  // Determina cuentas iniciales:
  // - openDepositModal(id) → single, esa cuenta
  // - openDepositModal(null, {ids: [...]}) → multi por default si >1
  let _ids;
  if (opts.ids && opts.ids.length > 0) {
    _ids = [...opts.ids].slice(0, 5);
  } else if (accountId) {
    _ids = [accountId];
  } else if (selectedIds.size > 0) {
    _ids = [...selectedIds].slice(0, 5);
  } else {
    toast('Sin cuenta seleccionada', 'error');
    return;
  }

  // ── C1: modal v8 por DEFAULT (2026-06-28) ──
  // Antes era opt-IN por flag (`localStorage.deposV8==='1'`). Como el flag es
  // POR NAVEGADOR, los demás operadores (y cualquier otro navegador) caían al
  // drawer viejo aunque el v8 ya estuviera deployado → "ven interfaz vieja".
  // Ahora v8 es el DEFAULT; opt-OUT explícito con `localStorage.deposV8='0'`
  // (escape hatch si algo truena). Fallback seguro al drawer viejo si por lo que
  // sea `openDepos` no cargó.
  // Pasamos las cuentas completas (email/password/grade/balance) desde state.rows → el v8
  // evita un fetch extra y pinta grado + balance reales.
  if (localStorage.getItem('deposV8') !== '0' && window.openDepos) {
    const accounts = _ids.map((id) => {
      const r = (state.rows || []).find((x) => x.id === id) || {};
      return {
        id,
        email: r.email || '',
        password: r.password || '',
        grade: (r.grade || '').toLowerCase(),
        balance: r.balance_total || 0,
      };
    });
    return window.openDepos({ accounts });
  }

  _depAccountIds = _ids;

  _depAmount = 50;
  _depReps = 5;
  _depMmRunId = null;
  $('#depCardPipe').value = '';
  $('#depMultiPool').value = '';
  $('#depPoolCount').textContent = '0 tarjetas';
  $('#depCardErr').classList.add('hidden');
  $('#depResult').classList.add('hidden');
  $('#depFeed').classList.add('hidden');
  $('#depFeed').innerHTML = '';
  $('#depCustomAmount').value = '';
  $('#depCustomAmount').classList.add('hidden');
  $$('#depAmounts .dep-amt').forEach(b => b.classList.toggle('on', b.dataset.v === '50'));
  $('#depRepsVal').textContent = '5';
  $('#depExec').disabled = false;
  $('#depCancel').classList.add('hidden');
  $('#depDrawer').classList.add('dep-drawer-open');
  // El body empuja contenido a la izquierda — el drawer NO se superpone al
  // dashboard, lo comprime. Coherente con el sidebar izq (también empuja).
  document.body.classList.add('dep-drawer-pushing');
  _depDrawerOpen = true;
  // Si había un pill flotante de misión previa, lo ocultamos al re-abrir.
  _depPillHide();

  // Tab Multi SIEMPRE visible — el operador puede entrar a Multi con 1 sola
  // cuenta seleccionada y desde ahí ir agregando más desde la tabla atrás
  // (drawer empuja, NO bloquea el dashboard).

  // Mode default: single si 1 cuenta, multi si más
  setDepMode(_depAccountIds.length > 1 ? 'multi' : 'single');

  // Display cuenta target (single/schedule) — combo clickeable para copiar
  if (_depAccountIds.length === 1) {
    const acc = state.rows.find(r => r.id === _depAccountIds[0]);
    const combo = acc ? `${acc.email}:${acc.password || ''}` : '—';
    const tgt = $('#depTargetEmail');
    tgt.textContent = combo;
    tgt.dataset.combo = combo;
    tgt.classList.add('d-copy');
    $('#depTargetBalance').textContent = acc ? fmtMoney(acc.balance_total) : '—';
    refreshCapStatus(_depAccountIds[0]);
  } else {
    $('#depCap').style.display = 'none';
  }

  setTimeout(() => {
    if (_depMode === 'multi') $('#depMultiPool').focus();
    else {
      const inp = $('#depCardPipe');
      inp.focus();
      if (inp.value) inp.select();
    }
  }, 60);
}

function renderMultiAccounts() {
  const list = $('#depMultiList');
  $('#depMultiAcctsCount').textContent = `${_depAccountIds.length}/5`;
  // Placeholder cuando hay <2 cuentas: el drawer empuja al dashboard, así que
  // el operador puede tickear cuentas en la tabla atrás sin cerrar el drawer.
  if (_depAccountIds.length < 2) {
    const have = _depAccountIds.length;
    list.innerHTML = `<div class="dep-multi-empty">
      <div class="dep-multi-empty-icon">👈</div>
      <div class="dep-multi-empty-msg">
        <b>${have === 0 ? 'Sin cuentas' : '1 cuenta'} seleccionada${have === 0 ? 's' : ''}.</b><br>
        Tickea ${have === 0 ? '2–5 cuentas' : '1–4 más'} en la tabla de la izquierda
        para armar el matchmaker. Las cuentas seleccionadas aparecen aquí.
      </div>
    </div>`;
    return;
  }
  list.innerHTML = _depAccountIds.map(id => {
    const acc = state.rows.find(r => r.id === id);
    if (!acc) return '';
    const combo = `${acc.email}:${acc.password || ''}`;
    return `<div class="dep-multi-row">
      <span class="dep-multi-email d-copy" data-combo="${esc(combo)}" title="Click para copiar">${esc(combo)}</span>
      <span class="dep-multi-balance mono dim">${fmtMoney(acc.balance_total)}</span>
      <button class="dep-multi-rm" data-id="${id}" title="Quitar">×</button>
    </div>`;
  }).join('');
}

async function refreshSavedCards() {
  const cont = $('#depSavedCards');
  const chips = $('#depCardChips');
  if (_depMode === 'multi' || _depAccountIds.length !== 1) {
    cont.classList.add('hidden');
    return;
  }
  const accId = _depAccountIds[0];
  const acc = state.rows.find(r => r.id === accId);
  if (!acc || !acc.cards_count) { cont.classList.add('hidden'); return; }

  try {
    const data = await fetch(`/api/accounts/${accId}/details`).then(r => r.ok ? r.json() : null);
    const cards = (data?.cards || []).filter(c => c.card_number && c.card_expiry && c.card_cvv);
    if (!cards.length) { cont.classList.add('hidden'); return; }

    chips.innerHTML = cards.slice(0, 8).map((c, i) => {
      const exp = String(c.card_expiry).replace('/', '');
      const pipe = `${c.card_number}|${exp}|${c.card_cvv}`;
      const tail = c.card_number.slice(-4);
      const ok = (c.total_approved || 0) > 0;
      return `<button class="dep-chip${i === 0 ? ' dep-chip-fresh' : ''}${ok ? ' dep-chip-ok' : ''}" data-pipe="${esc(pipe)}" title="${ok ? `${c.total_approved}/${c.total_deposits} aprobados` : 'sin depósitos exitosos'}">
        <span class="dep-chip-tail mono">···${tail}</span>
        ${ok ? '<span class="dep-chip-badge">✓</span>' : ''}
      </button>`;
    }).join('');
    cont.classList.remove('hidden');
  } catch {
    cont.classList.add('hidden');
  }
}

function closeDepositModal() {
  // Si hay misión activa (scheduled o matchmaker), cerramos el drawer pero
  // dejamos la mini-pill flotante para reabrir sin interrumpir el run.
  // Para single (_depBusy puro sin _schedActive ni _mmRunId): bloquear cierre
  // — un single dura segundos, no vale tener pill efímero.
  const hasActiveMission = !!(_schedActive || _depMmRunId);
  if (_depBusy && !hasActiveMission) {
    toast('Esperando intento en curso…', 'error');
    return;
  }
  $('#depDrawer').classList.remove('dep-drawer-open');
  document.body.classList.remove('dep-drawer-pushing');
  _depDrawerOpen = false;
  if (hasActiveMission) {
    _depPillShow();
    return;  // NO reset del state — la misión sigue
  }
  $('#depMatchView').classList.add('hidden');
  $('#depCap').style.display = 'none';
  // Limpiar la vista live del schedule (si quedó algún render previo)
  try { _schedReset(); } catch {}
  _depAccountIds = [];
}

// Cap status — pinta la barra y devuelve disponible
async function refreshCapStatus(accountId) {
  const cap = $('#depCap');
  if (!accountId) { cap.style.display = 'none'; return null; }
  try {
    const r = await fetch(`/api/deposits/cap-status/${accountId}`);
    if (!r.ok) { cap.style.display = 'none'; return null; }
    const s = await r.json();
    const used = Number(s.used || 0);
    const max = Number(s.max_24h || 1499);
    const pct = Math.min(100, (used / max) * 100);
    $('#depCapUsed').textContent = `$${used.toFixed(0)}`;
    const fill = $('#depCapFill');
    fill.style.width = `${pct}%`;
    fill.className = 'dep-cap-fill ' + (pct >= 100 ? 'cap-full' : pct >= 75 ? 'cap-warn' : 'cap-ok');
    if (s.in_window && s.expires_at) {
      const exp = new Date(s.expires_at);
      $('#depCapExpires').textContent = `· cierra ${exp.toLocaleTimeString('es-MX', {hour:'2-digit',minute:'2-digit'})}`;
    } else {
      $('#depCapExpires').textContent = '';
    }
    cap.style.display = '';
    return s;
  } catch {
    cap.style.display = 'none';
    return null;
  }
}

function validatePipe(s) {
  if (!s) return null;
  const parts = s.replace(/\s/g, '').split('|').filter(Boolean);
  if (parts.length === 3) {
    const [num, exp, cvv] = parts;
    if (!/^\d{13,19}$/.test(num)) return 'Número de tarjeta inválido';
    if (!/^(0[1-9]|1[0-2])\/?(\d{2}|\d{4})$/.test(exp)) return 'Vencimiento inválido (MMYY)';
    if (!/^\d{3,4}$/.test(cvv)) return 'CVV inválido';
    return null;
  }
  if (parts.length === 4) {
    const [num, mm, yy, cvv] = parts;
    if (!/^\d{13,19}$/.test(num)) return 'Número de tarjeta inválido';
    if (!/^(0?[1-9]|1[0-2])$/.test(mm)) return 'Mes inválido';
    if (!/^\d{2,4}$/.test(yy)) return 'Año inválido';
    if (!/^\d{3,4}$/.test(cvv)) return 'CVV inválido';
    return null;
  }
  return 'Formato: numero|MMYY|CVV';
}

function getAmount() {
  let a = _depAmount;
  if (a === 'custom') a = parseFloat($('#depCustomAmount').value) || 0;
  return a;
}

// ── SINGLE / SCHEDULE: 1 tarjeta, 1 cuenta ──
async function executeDeposit() {
  if (_depBusy) return;
  if (_depMode === 'multi') return executeMatchmaker();

  if (_depAccountIds.length !== 1) { toast('Selecciona 1 cuenta', 'error'); return; }
  const pipe = $('#depCardPipe').value.trim();
  const err = validatePipe(pipe);
  if (err) {
    $('#depCardErr').textContent = err;
    $('#depCardErr').classList.remove('hidden');
    $('#depCardPipe').focus();
    return;
  }
  const amount = getAmount();
  if (amount < 1 || amount > 5000) { toast('Monto fuera de rango (1-5000)', 'error'); return; }

  if (_depMode === 'schedule') return executeScheduled(pipe, amount);

  // SINGLE — SSE live stepper
  _depBusy = true;
  $('#depExec').disabled = true;
  $('#depExec').textContent = 'Procesando…';
  const res = $('#depResult');
  res.classList.add('hidden');
  res.className = 'dep-result hidden';
  res.innerHTML = '';
  _stepperReset();
  $('#depStepper').classList.remove('hidden');

  let _gotDone = false;
  let reader = null;
  try {
    const r = await fetch('/api/deposits/execute-stream', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ account_id: _depAccountIds[0], card_pipe: pipe, amount }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      const msg = (err.detail && err.detail.message) || err.detail || `HTTP ${r.status}`;
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        // SSE comments (heartbeat ":ping") start with ":" — skip
        const dataLine = chunk.split('\n').find(l => l.startsWith('data: '));
        if (!dataLine) continue;
        try {
          const ev = JSON.parse(dataLine.slice(6));
          if (ev && ev.type === 'done') _gotDone = true;
          _handleExecStreamEvent(ev, amount);
        } catch { /* ignore malformed */ }
      }
    }
    if (!_gotDone) {
      // Stream cerró sin done — marcar fatal
      _showStepperFatal('Conexión cerrada sin resultado');
    }
    $('#depExec').textContent = '🔁 Otro intento';
  } catch (e) {
    _showStepperFatal(e.message);
    $('#depExec').textContent = '🔁 Reintentar';
  } finally {
    // Cancel SSE reader if still open (network drop, modal closed, etc.)
    // cancel() may throw if stream already closed — we don't care.
    if (reader) {
      try { await reader.cancel(); } catch {}
    }
    _depBusy = false;
    $('#depExec').disabled = false;
  }
}

// ── Phase stepper helpers (single deposit SSE) ──
function _stepperReset() {
  document.querySelectorAll('#depStepper .dep-phase').forEach(el => {
    el.classList.remove('active', 'ok', 'fail', 'na');
    const t = el.querySelector('.dep-phase-time');
    if (t) t.textContent = '';
  });
}
function _setStepState(stepName, state, durationMs) {
  const el = document.querySelector(`#depStepper .dep-phase[data-step="${stepName}"]`);
  if (!el) return;
  el.classList.remove('active', 'ok', 'fail', 'na');
  if (state) el.classList.add(state);
  const t = el.querySelector('.dep-phase-time');
  if (t) {
    if (typeof durationMs === 'number' && isFinite(durationMs)) t.textContent = `${durationMs}ms`;
    else if (durationMs === '3DS') t.textContent = '3DS';
    else if (typeof durationMs === 'string') t.textContent = durationMs;
  }
}
function _showStepperFatal(msg) {
  // Cualquier paso "active" pasa a "fail"; los pending quedan tal cual
  document.querySelectorAll('#depStepper .dep-phase.active').forEach(el => {
    el.classList.remove('active');
    el.classList.add('fail');
  });
  const res = $('#depResult');
  res.className = 'dep-result error';
  res.classList.remove('hidden');
  res.innerHTML = `<b>✗ Error</b><br><span class="mono">${esc(msg || 'Sin detalle')}</span>`;
}
function _handleExecStreamEvent(ev, amount) {
  if (!ev || !ev.type) return;
  if (ev.type === 'start') {
    return;
  }
  if (ev.type === 'fatal') {
    _showStepperFatal(ev.error || 'Error fatal en stream');
    return;
  }
  if (ev.type === 'phase') {
    const d = ev.data || {};
    switch (ev.name) {
      case 'login_start':         _setStepState('login',  'active'); break;
      case 'login_done':          _setStepState('login',  d.ok ? 'ok' : 'fail', d.duration_ms); break;
      case 'gateway_begin':       _setStepState('begin',  'active'); break;
      case 'gateway_begin_done':  _setStepState('begin',  d.ok ? 'ok' : 'fail', d.duration_ms); break;
      case 'gateway_submit':      _setStepState('submit', 'active'); break;
      case 'gateway_submit_done': {
        const approved = d.result_code === 'BANK_APPROVED';
        _setStepState('submit', approved ? 'ok' : 'fail', d.duration_ms);
        if (d.is_3ds) _setStepState('check', 'na', '3DS');
        break;
      }
      case 'gateway_check':       _setStepState('check',  'active'); break;
      case 'gateway_check_done': {
        // OK unless the check itself raised an error.
        // txn_status es informativo; la aprobación real viene de result_code en submit_done.
        // El reconcile final en type='done' fuerza ok si el backend confirmó success.
        _setStepState('check', d.check_error ? 'fail' : 'ok', d.duration_ms);
        break;
      }
      case 'done':
        // El backend también emite phase=done justo antes del type=done final.
        // Lo dejamos pasar — el type=done hace el render del result panel.
        break;
    }
    return;
  }
  if (ev.type === 'done') {
    const res = $('#depResult');
    res.classList.remove('hidden');
    if (ev.success) {
      res.className = 'dep-result success';
      res.innerHTML = `<b>✓ Depósito aprobado</b> — $${(amount || 0).toFixed(2)} <span class="dim mono"> · ${ev.duration_ms || 0}ms</span>`;
      pushNotif({ icon: '💳', msg: `Depósito $${(amount || 0).toFixed(2)} aprobado` });
      // Reconcile: backend confirmó aprobado. Si el step 'check' quedó marcado fail por
      // un edge case (txn_status=0 mientras el banco ya aprobó), corregirlo a ok aquí.
      const checkEl = document.querySelector('.dep-phase[data-step="check"]');
      if (checkEl && !checkEl.classList.contains('na') && !checkEl.classList.contains('ok')) {
        _setStepState('check', 'ok');
      }
      reload();
    } else {
      res.className = 'dep-result error';
      const detail = ev.error || ev.result_code || 'Sin detalle';
      res.innerHTML = `<b>✗ Rechazado</b><br><span class="mono">${esc(detail)}</span>`;
      pushNotif({ icon: '⚠️', msg: `Depósito rechazado: ${detail}` });
    }
  }
}

// ── SCHEDULE: 1 tarjeta, 1 cuenta, N reps cada 1 min ──
// Vista live driven por SSE: barra de progreso, fase actual, timeline.
// No usa el feed de Actividad — todo el feedback vive en el modal.
const _PHASE_TEXTS = {
  login_start: '🔑 Iniciando sesión…',
  login_done: '✓ Sesión OK',
  gateway_begin: '📝 Generando orden…',
  gateway_begin_done: '✓ Orden creada',
  gateway_submit: '💳 Procesando tarjeta…',
  gateway_submit_done: '✓ Banco respondió',
  gateway_check: '🔎 Verificando con BetMexico…',
  gateway_check_done: '✓ Verificado',
  implicit_3ds_detected: '⚠️ 3DS detectado (no acreditado)',
  done: '✓ Intento completado',
};

// ─────────────────────────────────────────────────────────────────────────
// Drawer lateral + mini-pill flotante
// ─────────────────────────────────────────────────────────────────────────
let _depDrawerOpen = false;
let _depPillTickTimer = null;     // refresca el texto del pill cada 1s

function _depPillShow() {
  const pill = $('#depMissionPill');
  if (!pill) return;
  pill.classList.remove('hidden');
  _depPillTick();   // pinta texto inicial
  if (_depPillTickTimer) clearInterval(_depPillTickTimer);
  _depPillTickTimer = setInterval(_depPillTick, 1000);
}

function _depPillHide() {
  const pill = $('#depMissionPill');
  if (pill) pill.classList.add('hidden');
  if (_depPillTickTimer) { clearInterval(_depPillTickTimer); _depPillTickTimer = null; }
}

function _depPillTick() {
  const txtEl = $('#depPillText');
  const iconEl = $('#depPillIcon');
  if (!txtEl) return;
  // Prioridad: schedule activo > matchmaker activo
  if (_schedActive) {
    iconEl.textContent = '⏰';
    const done = _schedActive.currentIter;
    const tot = _schedActive.total;
    // Si hay countdown corriendo, muéstralo
    const cdEl = $('#depSchedCountdown');
    let cdText = '';
    if (cdEl && !cdEl.classList.contains('hidden')) {
      cdText = ' · ' + (cdEl.textContent || '').trim();
    }
    txtEl.textContent = `${done}/${tot}${cdText}`;
  } else if (_depMmRunId) {
    iconEl.textContent = '🎯';
    txtEl.textContent = `${_mm.matches} match · ${_mm.attempts} intentos`;
  } else {
    // Misión terminó mientras el pill estaba visible → ocultar.
    _depPillHide();
  }
}

function _depPillReopen() {
  // Reabre el drawer sin tocar el state — la misión sigue viva.
  $('#depDrawer').classList.add('dep-drawer-open');
  document.body.classList.add('dep-drawer-pushing');
  _depDrawerOpen = true;
  // Si el usuario lo había dejado colapsado, expandir al abrir explícitamente
  // (clic en Depositar/Nueva misión/Reabrir pill). Si quiere dejarlo rail otra
  // vez, hace clic en el ≪ del header.
  if (_depDrawerCollapsed) _toggleDepCollapsed(false);
  _depPillHide();
}

// Estado del schedule activo (un solo schedule a la vez por user)
let _schedActive = null;          // { sched_id, total, currentIter, lastIterStart, results: [] }
let _schedCountdownTimer = null;
// Buffer de eventos scheduled_* que pueden llegar ANTES de que _schedShow corra
// (race: el background task `loop()` arranca con asyncio.create_task y, si el
// captcha pool ya estaba warm, el primer phase_cb se dispara en <50ms — antes
// de que la respuesta HTTP del POST /scheduled/create haya retornado al
// frontend). Sin buffer, esos eventos quedan descartados en la guarda de
// _schedActive y el operador ve "Preparando…" eternamente.
let _schedPendingEvents = [];     // [{handler:'phase'|'iter'|'aborted'|'cancelled', ev}]
// Watchdog del 1er evento. Si en 25s no llegamos a NINGÚN phase, casi seguro
// el SSE bus está caído o el backend explotó silencioso. Anunciamos al user.
let _schedWatchdogTimer = null;
let _schedHintTimer = null;       // rotador de hints durante el pool warm-up

function _schedReset() {
  if (_schedCountdownTimer) { clearInterval(_schedCountdownTimer); _schedCountdownTimer = null; }
  if (_schedWatchdogTimer) { clearTimeout(_schedWatchdogTimer); _schedWatchdogTimer = null; }
  if (_schedHintTimer) { clearInterval(_schedHintTimer); _schedHintTimer = null; }
  _schedActive = null;
  _schedPendingEvents = [];
  const el = $('#depScheduledRun');
  if (!el) return;
  el.classList.add('hidden');
  el.classList.remove('done', 'aborted');
  const tl = $('#depSchedTimeline'); if (tl) tl.innerHTML = '';
  const bar = $('#depSchedBarFill'); if (bar) bar.style.width = '0%';
  const cd = $('#depSchedCountdown'); if (cd) cd.classList.add('hidden');
  const txt = $('#depSchedNowText'); if (txt) txt.textContent = 'Iniciando…';
  // Esconder cancel + reactivar Ejecutar (vuelve al flujo normal de nueva misión)
  $('#depSchedCancel')?.classList.add('hidden');
  $('#depExec')?.classList.remove('hidden');
}

function _schedShow(sched_id, total, opts = {}) {
  _schedActive = {
    sched_id, total,
    currentIter: opts.currentIter || 0,
    lastIterStart: 0,
    results: [],
  };
  const el = $('#depScheduledRun');
  if (!el) return;
  el.classList.remove('hidden', 'done', 'aborted');
  $('#depSchedId').textContent = `id: ${sched_id}`;
  $('#depSchedIterNow').textContent = String(_schedActive.currentIter);
  $('#depSchedIterTot').textContent = String(total);
  const pct = total > 0 ? (_schedActive.currentIter / total) * 100 : 0;
  $('#depSchedBarFill').style.width = `${pct}%`;
  $('#depSchedTimeline').innerHTML = '';
  $('#depSchedNowText').textContent = opts.resumed
    ? `↺ Re-anclado tras refresh — esperando próximo evento…`
    : `⚡ Calentando captcha pool…`;
  $('#depSchedCountdown').classList.add('hidden');
  // Mientras hay misión activa, el botón Ejecutar se reemplaza por Cancelar.
  // TDAH-friendly: el control de aborto es siempre visible y obvio.
  $('#depExec')?.classList.add('hidden');
  $('#depSchedCancel')?.classList.remove('hidden');

  // Rotador de hints — feedback continuo durante los ~5-15s antes del primer
  // phase event (login_start). Sin esto, "Preparando…" no cambia y parece
  // congelado. Se cancela al primer phase real (en _schedOnPhase).
  const hints = [
    `⚡ Calentando captcha pool…`,
    `🔑 Solicitando token CapMonster…`,
    `🚀 Levantando worker…`,
    `⏳ Esperando primer login…`,
  ];
  let hintIdx = 1;
  _schedHintTimer = setInterval(() => {
    if (!_schedActive) return;
    $('#depSchedNowText').textContent = hints[hintIdx % hints.length];
    hintIdx++;
  }, 3500);

  // Watchdog: si en 30s no llegó ningún scheduled_phase, casi seguro el bus
  // SSE está roto o el backend murió. Alertamos al operador en vez de dejarlo
  // viendo hints rotativos eternos.
  _schedWatchdogTimer = setTimeout(() => {
    if (!_schedActive) return;
    if (_schedActive.currentIter === 0 && !_schedActive.lastIterStart) {
      console.warn(`[Sched] watchdog: sin scheduled_phase en 30s para ${sched_id}`);
      if (_schedHintTimer) { clearInterval(_schedHintTimer); _schedHintTimer = null; }
      $('#depSchedNowText').textContent = `⚠️ Sin señal del backend (>30s). La misión sigue corriendo, pero el feed live no responde.`;
    }
  }, 30000);

  // Drena eventos que llegaron mientras _schedActive era null (race).
  if (_schedPendingEvents.length) {
    console.info(`[Sched] drenando ${_schedPendingEvents.length} eventos pendientes para ${sched_id}`);
    const buffered = _schedPendingEvents;
    _schedPendingEvents = [];
    for (const { handler, ev } of buffered) {
      if (ev.sched_id !== sched_id) continue;
      if (handler === 'phase') _schedOnPhase(ev);
      else if (handler === 'iter') _schedOnIterDone(ev);
      else if (handler === 'retry') _schedOnRetry(ev);
      else if (handler === 'aborted') _schedOnAborted(ev);
      else if (handler === 'cancelled') _schedOnCancelled(ev);
    }
  }
}

function _schedUpdateProgress() {
  if (!_schedActive) return;
  const pct = Math.max(0, Math.min(100, Math.round((_schedActive.currentIter / _schedActive.total) * 100)));
  $('#depSchedBarFill').style.width = pct + '%';
  $('#depSchedIterNow').textContent = String(_schedActive.currentIter);
}

function _schedOnPhase(ev) {
  if (!_schedActive) {
    // _schedShow aún no corrió (race con respuesta HTTP /scheduled/create).
    // Buffereamos para replay cuando _schedShow se ejecute.
    _schedPendingEvents.push({ handler: 'phase', ev });
    return;
  }
  if (ev.sched_id !== _schedActive.sched_id) return;
  const iter = ev.iter || 1;
  // Marca inicio de un nuevo intento (primer phase)
  if (iter > _schedActive.currentIter || (iter === 1 && !_schedActive.lastIterStart)) {
    _schedActive.lastIterStart = Date.now();
  }
  // Primer phase real → matamos el rotador de hints y el watchdog.
  if (_schedHintTimer) { clearInterval(_schedHintTimer); _schedHintTimer = null; }
  if (_schedWatchdogTimer) { clearTimeout(_schedWatchdogTimer); _schedWatchdogTimer = null; }
  const txt = _PHASE_TEXTS[ev.name] || `· ${ev.name}`;
  $('#depSchedNowText').textContent = `Intento ${iter}/${_schedActive.total} — ${txt}`;
  $('#depSchedCountdown').classList.add('hidden');
  if (_schedCountdownTimer) { clearInterval(_schedCountdownTimer); _schedCountdownTimer = null; }
}

function _schedOnIterDone(ev) {
  if (!_schedActive) {
    _schedPendingEvents.push({ handler: 'iter', ev });
    return;
  }
  if (ev.sched_id !== _schedActive.sched_id) return;
  const iter = ev.iter || 1;
  const ok = !!ev.success;
  const code = ev.code || (ok ? 'APPROVED' : 'REJECTED');
  const durMs = _schedActive.lastIterStart ? (Date.now() - _schedActive.lastIterStart) : 0;
  const dur = durMs > 0 ? (durMs / 1000).toFixed(1) + 's' : '';
  _schedActive.results.push({ iter, ok, code, dur });
  _schedActive.currentIter = iter;
  _schedUpdateProgress();

  // Append a timeline (más reciente arriba). 3DS = ámbar (no rojo): la tarjeta
  // sirve, solo el procesador pidió autenticación y la txn no se acreditó.
  const is3ds = /3ds/i.test(code) || /3ds/i.test(ev.reason || '');
  const tl = $('#depSchedTimeline');
  if (tl) {
    const item = document.createElement('div');
    const cls = ok ? 'ok' : (is3ds ? 'threeds' : 'fail');
    const icon = ok ? '✓' : (is3ds ? '⚠' : '✗');
    item.className = `dep-sched-tl-item ${cls}`;
    // title = mensaje explícito completo en hover (reason); el chip muestra el code corto.
    const reasonTitle = (!ok && ev.reason) ? esc(ev.reason) : '';
    item.innerHTML = `
      <span class="dep-sched-tl-iter">#${iter}</span>
      <span class="dep-sched-tl-icon">${icon}</span>
      <span class="dep-sched-tl-code"${reasonTitle ? ` title="${reasonTitle}"` : ''}>${esc(code)}</span>
      <span class="dep-sched-tl-dur">${esc(dur)}</span>
    `;
    tl.insertBefore(item, tl.firstChild);
  }

  // Check terminal
  if (iter >= _schedActive.total) {
    _schedFinish(ok);
    return;
  }
  if (!ok) {
    // El backend va a emitir scheduled_aborted, dejamos que ese handler termine
    return;
  }
  // Próximo intento — countdown
  _schedStartCountdown(60);
}

function _schedStartCountdown(seconds) {
  const el = $('#depSchedCountdown');
  const txtEl = $('#depSchedNowText');
  if (!el || !txtEl) return;
  el.classList.remove('hidden');
  let remaining = seconds;
  el.textContent = `⏱ ${remaining}s`;
  txtEl.textContent = `Esperando próximo intento…`;
  if (_schedCountdownTimer) clearInterval(_schedCountdownTimer);
  _schedCountdownTimer = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(_schedCountdownTimer);
      _schedCountdownTimer = null;
      el.classList.add('hidden');
    } else {
      el.textContent = `⏱ ${remaining}s`;
    }
  }, 1000);
}

function _schedFinish(allOk) {
  if (!_schedActive) return;
  if (_schedHintTimer) { clearInterval(_schedHintTimer); _schedHintTimer = null; }
  if (_schedWatchdogTimer) { clearTimeout(_schedWatchdogTimer); _schedWatchdogTimer = null; }
  if (_schedCountdownTimer) { clearInterval(_schedCountdownTimer); _schedCountdownTimer = null; }
  const el = $('#depScheduledRun');
  if (el) el.classList.add(allOk ? 'done' : 'aborted');
  const total = _schedActive.total;
  $('#depSchedNowText').textContent = allOk
    ? `🎯 Misión completa — ${total} intento${total === 1 ? '' : 's'} aprobado${total === 1 ? '' : 's'}`
    : `✗ Misión terminada con errores`;
  $('#depSchedCountdown').classList.add('hidden');
  $('#depExec').textContent = '⏰ Nueva misión';
  $('#depExec').classList.remove('hidden');
  $('#depSchedCancel').classList.add('hidden');
  _schedActive = null;
}

function _schedOnRetry(ev) {
  // Fallo TRANSITORIO (login 406/captcha/proxy, gateway 50x) — NO aborta, el
  // backend reintenta la misma rep. Mostramos el reintento para que el operador
  // sepa que sigue vivo (Robert 2026-05-29: que no se detenga por login).
  if (!_schedActive) {
    _schedPendingEvents.push({ handler: 'retry', ev });
    return;
  }
  if (ev.sched_id !== _schedActive.sched_id) return;
  if (_schedCountdownTimer) { clearInterval(_schedCountdownTimer); _schedCountdownTimer = null; }
  const a = ev.attempt || 1, mx = ev.max || 4;
  const why = ev.reason || ev.code || 'transitorio';
  const txt = $('#depSchedNowText');
  if (txt) txt.textContent = `🔁 Reintentando intento ${ev.iter || ''} (${a}/${mx}) — ${String(why).slice(0, 70)}`;
  // Append discreto al timeline para dejar rastro del reintento.
  const tl = $('#depSchedTimeline');
  if (tl) {
    const item = document.createElement('div');
    item.className = 'dep-sched-tl-item retry';
    item.innerHTML = `
      <span class="dep-sched-tl-iter">#${ev.iter || ''}</span>
      <span class="dep-sched-tl-icon">🔁</span>
      <span class="dep-sched-tl-code" title="${esc(String(why))}">retry ${a}/${mx} · ${esc(ev.code || '')}</span>
      <span class="dep-sched-tl-dur"></span>
    `;
    tl.insertBefore(item, tl.firstChild);
  }
}

function _schedOnAborted(ev) {
  if (!_schedActive) {
    _schedPendingEvents.push({ handler: 'aborted', ev });
    return;
  }
  if (ev.sched_id !== _schedActive.sched_id) return;
  if (_schedHintTimer) { clearInterval(_schedHintTimer); _schedHintTimer = null; }
  if (_schedWatchdogTimer) { clearTimeout(_schedWatchdogTimer); _schedWatchdogTimer = null; }
  if (_schedCountdownTimer) { clearInterval(_schedCountdownTimer); _schedCountdownTimer = null; }
  // 3DS no es un fallo "rojo": la tarjeta sirve, el procesador escaló a 3DS
  // (ej. threshold del BIN) y la txn no se acreditó. Ámbar + ⚠ (Robert 2026-05-29).
  const is3ds = /3ds/i.test(ev.code || '') || /3ds/i.test(ev.reason || '');
  const run = $('#depScheduledRun');
  run.classList.remove('aborted', 'threeds-stop');
  run.classList.add(is3ds ? 'threeds-stop' : 'aborted');
  const detail = esc(ev.reason || ev.code || 'fallo');
  $('#depSchedNowText').textContent = is3ds
    ? `⚠ Detenida por 3DS — ${detail}`
    : `✗ Misión abortada — ${detail}`;
  $('#depSchedCountdown').classList.add('hidden');
  $('#depExec').textContent = '⏰ Nueva misión';
  $('#depExec').classList.remove('hidden');
  $('#depSchedCancel').classList.add('hidden');
  _schedActive = null;
}

function _schedOnCancelled(ev) {
  if (!_schedActive) {
    _schedPendingEvents.push({ handler: 'cancelled', ev });
    return;
  }
  if (ev.sched_id !== _schedActive.sched_id) return;
  if (_schedHintTimer) { clearInterval(_schedHintTimer); _schedHintTimer = null; }
  if (_schedWatchdogTimer) { clearTimeout(_schedWatchdogTimer); _schedWatchdogTimer = null; }
  if (_schedCountdownTimer) { clearInterval(_schedCountdownTimer); _schedCountdownTimer = null; }
  $('#depScheduledRun').classList.add('aborted');
  $('#depSchedNowText').textContent = `⏹ Misión cancelada`;
  $('#depSchedCountdown').classList.add('hidden');
  $('#depExec').textContent = '⏰ Nueva misión';
  $('#depExec').classList.remove('hidden');
  $('#depSchedCancel').classList.add('hidden');
  _schedActive = null;
}

async function executeScheduled(pipe, amount) {
  _depBusy = true;
  $('#depExec').disabled = true;
  $('#depExec').textContent = 'Programando…';
  _schedReset();
  $('#depResult').classList.add('hidden');
  try {
    const r = await fetch('/api/deposits/scheduled/create', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        account_id: _depAccountIds[0], card_pipe: pipe,
        amount, repetitions: _depReps,
      }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    // Activar vista live — el resto viene por SSE
    _schedShow(data.sched_id, _depReps);
    pushNotif({ icon: '⏰', msg: `Misión ${data.sched_id}: ${_depReps} reps en ${data.email}` });
    $('#depExec').textContent = '⏳ Misión activa';
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
    $('#depExec').textContent = '⏰ Programar misión';
  } finally {
    _depBusy = false;
    $('#depExec').disabled = false;
  }
}

// ── MULTI: matchmaker SSE con vista 3-columnas reactiva ──
const _mm = {
  cards: new Map(),    // tail → {pipe, fails, status: idle|busy|retired|matched, matchedEmail, lastCode}
  accounts: new Map(), // email → {id, fails, status: idle|busy|done|dead|cooldown, matchedTail, deadCode, lastCode}
  matches: 0,
  attempts: 0,
  amount: 0,
};

function _mmReset(accountIds, cardPipes, amount) {
  _mm.cards.clear();
  _mm.accounts.clear();
  _mm.matches = 0;
  _mm.attempts = 0;
  _mm.amount = amount;
  for (const pipe of cardPipes) {
    const num = pipe.replace(/\s/g, '').split('|')[0];
    const tail = num.slice(-4);
    _mm.cards.set(tail, { pipe, num, fails: 0, status: 'idle' });
  }
  for (const id of accountIds) {
    const acc = state.rows.find(r => r.id === id);
    if (acc) _mm.accounts.set(acc.email, { id, fails: 0, status: 'idle' });
  }
}

const _MM_CODE_LABEL = {
  LOGIN_FAILED:    'Login falló',
  AUTOEXCLUSION:   'Autoexcluida',
  KYC_PENDING:     'KYC revocado',
  '3DS_UNDETECTED':'3DS no detectado',
  'SHADOW_BAN?':   'Shadow ban',
  '3DS_REQUIRED':  '3DS bloqueó',
  BANK_REJECTED:   'Banco rechazó',
  ERROR:           'Error',
  UNKNOWN:         'Desconocido',
};
const _mmLabel = code => _MM_CODE_LABEL[code] || code || '';

function _mmRender() {
  // Tarjetas — incluye data-pair-key cuando hay pair activo (email del busy)
  // para que el handler de 'phase' pueda inyectar el sub-indicador.
  const cardsHtml = [..._mm.cards.entries()].map(([tail, c]) => {
    const cls = `mm-card mm-${c.status}`;
    const fails = c.fails ? `<span class="mm-fails">${c.fails}/2</span>` : '';
    const ic = c.status === 'matched' ? '🎯'
             : c.status === 'busy'    ? '<span class="dep-spinner"></span>'
             : c.status === 'retired' ? '💀'
             : '';
    const reason = (c.status === 'retired' && c.lastCode)
      ? `<span class="mm-reason">${esc(_mmLabel(c.lastCode))}</span>` : '';
    const pairKey = (c.status === 'busy' && c.busyEmail)
      ? ` data-pair-key="${esc(c.busyEmail)}|···${tail}"` : '';
    // currentPhase se persiste en el modelo para sobrevivir re-renders
    // disparados por otros pares (ver _mmSetPairPhase).
    const phaseTxt = (c.status === 'busy' && c.currentPhase) ? esc(c.currentPhase) : '';
    return `<div class="${cls}"${pairKey}>
      <span class="mm-tail mono">···${tail}</span>
      ${fails}
      ${reason}
      <span class="mm-pair-phase">${phaseTxt}</span>
      <span class="mm-ic">${ic}</span>
    </div>`;
  }).join('');
  $('#mmCards').innerHTML = cardsHtml;

  // Cuentas — mismo patrón: data-pair-key cuando está busy
  const accsHtml = [..._mm.accounts.entries()].map(([email, a]) => {
    const cls = `mm-acct mm-${a.status}`;
    const fails = a.fails ? `<span class="mm-fails">${a.fails}/2</span>` : '';
    const ic = a.status === 'done'     ? '✓'
             : a.status === 'busy'     ? '<span class="dep-spinner"></span>'
             : a.status === 'dead'     ? '💀'
             : a.status === 'cooldown' ? '⏳'
             : '';
    const matched = a.matchedTail ? `<span class="mm-matched mono">···${a.matchedTail}</span>` : '';
    const reason = (a.status === 'dead' && a.deadCode)
      ? `<span class="mm-reason mm-reason-dead" title="${esc(a.deadCode)}">${esc(_mmLabel(a.deadCode))}</span>`
      : '';
    const pairKey = (a.status === 'busy' && a.busyTail)
      ? ` data-pair-key="${esc(email)}|···${a.busyTail}"` : '';
    const phaseTxt = (a.status === 'busy' && a.currentPhase) ? esc(a.currentPhase) : '';
    return `<div class="${cls}"${pairKey}>
      <span class="mm-email">${esc(email)}</span>
      ${matched}
      ${fails}
      ${reason}
      <span class="mm-pair-phase">${phaseTxt}</span>
      <span class="mm-ic">${ic}</span>
    </div>`;
  }).join('');
  $('#mmAccounts').innerHTML = accsHtml;

  // Stats
  $('#mmStMatches').textContent = _mm.matches;
  $('#mmStAttempts').textContent = _mm.attempts;
  $('#mmStAmount').textContent = _mm.amount;
}

// Actualiza el sub-indicador de fase dentro del row del par (email, tail).
// Llama el handler de 'phase' en cada evento; si no hay row (el par ya terminó
// y el render lo movió a otro estado), es un no-op silencioso.
// IMPORTANTE: persiste el texto en el modelo (_mm.cards / _mm.accounts) para
// sobrevivir un _mmRender disparado por otro par. Sin esto, el indicador se
// borra cada vez que otro evento causa re-render.
function _mmSetPairPhase(key, name, data) {
  data = data || {};
  const labels = {
    login_start:          '🔑 Login…',
    login_done:           data.ok ? '🔑 ✓' : '🔑 ✗',
    gateway_begin:        '📝 Orden…',
    gateway_begin_done:   data.ok ? '📝 ✓' : '📝 ✗',
    gateway_submit:       '💳 Tarjeta…',
    gateway_submit_done:  data.is_3ds ? '💳 3DS' : (data.result_code === 'BANK_APPROVED' ? '💳 ✓' : '💳 ✗'),
    gateway_check:        '✓ Verificando…',
    gateway_check_done:   data.check_error ? '✓ ✗' : '✓ ✓',
    done:                 data.success ? '✓ Aprobado' : '✗ Rechazado',
  };
  const text = labels[name] || name;
  // El key viene como "email|···tail" — parseamos para persistir en modelo
  const sepIdx = key.indexOf('|');
  if (sepIdx > 0) {
    const email = key.slice(0, sepIdx);
    const tail = key.slice(sepIdx + 1).replace('···', '');
    const card = _mm.cards.get(tail);
    const acc = _mm.accounts.get(email);
    if (card) card.currentPhase = text;
    if (acc) acc.currentPhase = text;
  }
  // DOM update directo (sin forzar _mmRender) — más rápido y suave
  const rows = document.querySelectorAll(`[data-pair-key="${key}"]`);
  rows.forEach(row => {
    const phaseEl = row.querySelector('.mm-pair-phase');
    if (phaseEl) phaseEl.textContent = text;
  });
}

function _mmFeedAdd(cls, html) {
  const feed = $('#depFeed');
  const div = document.createElement('div');
  div.className = `mm-feed-row ${cls}`;
  div.innerHTML = html;
  feed.appendChild(div);
  // Cap a 80 rows en pantalla
  while (feed.children.length > 80) feed.removeChild(feed.firstChild);
  feed.scrollTop = feed.scrollHeight;
}

async function executeMatchmaker() {
  if (_depBusy) return;
  if (_depAccountIds.length < 2) { toast('Selecciona 2-5 cuentas desde la tabla para el matchmaker', 'error'); return; }
  if (_depAccountIds.length > 5) { toast('Máximo 5 cuentas', 'error'); return; }

  const raw = $('#depMultiPool').value.trim();
  const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
  const cards = [];
  for (const l of lines.slice(0, 10)) {
    if (!validatePipe(l)) cards.push(l);
  }
  if (!cards.length) { toast('Pega al menos 1 tarjeta válida', 'error'); return; }

  const amount = getAmount();
  if (amount < 1 || amount > 499) { toast('Monto debe ser entre $1 y $499', 'error'); return; }

  _depBusy = true;
  $('#depExec').disabled = true;
  $('#depCancel').classList.remove('hidden');
  // Oculta inputs, abre la vista matchmaker
  $('#depMultiCards').classList.add('hidden');
  $('#depMultiAccts').classList.add('hidden');
  $('#depResult').classList.add('hidden');
  $('#depMatchView').classList.remove('hidden');
  // (Drawer tiene ancho fijo — el matchmaker se renderiza vertical adentro.)

  _mmReset(_depAccountIds, cards, amount);
  _mmRender();
  $('#depFeed').innerHTML = '';

  // Fallback: si el stream cierra sin 'done' (excepción en generator, conexión cortada,
  // etc.) las pair rows quedan stuck en busy. _mmGotDone marca recepción explícita.
  let _mmGotDone = false;
  try {
    const ctrl = new AbortController();
    _depMmAbort = ctrl;
    const r = await fetch('/api/deposits/multi/stream', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ account_ids: _depAccountIds, cards, amount }),
      signal: ctrl.signal,
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.split('\n').find(l => l.startsWith('data: '));
        if (!line) continue;
        try {
          const parsed = JSON.parse(line.slice(6));
          if (parsed && (parsed.type === 'done' || parsed.type === 'fatal' || parsed.type === 'cancelled')) {
            _mmGotDone = true;
          }
          handleMmEvent(parsed);
        } catch {}
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      _mmFeedAdd('mm-err', `✗ ${esc(e.message)}`);
    }
  } finally {
    _depBusy = false;
    $('#depExec').disabled = false;
    $('#depExec').textContent = '🔁 Otra ronda';
    $('#depCancel').classList.add('hidden');
    _depMmAbort = null;
    _depMmRunId = null;
    // Stream cerró sin done explícito → reset preventivo del estado busy para que
    // las pair rows no queden con spinner hasta recargar la página.
    if (!_mmGotDone) {
      console.warn('[MM] stream closed without done — clearing busy state');
      for (const c of _mm.cards.values()) {
        if (c.status === 'busy') { c.status = 'idle'; c.busyEmail = null; c.currentPhase = ''; }
      }
      for (const a of _mm.accounts.values()) {
        if (a.status === 'busy') { a.status = 'idle'; a.busyTail = null; a.currentPhase = ''; }
      }
      _mmRender();
      toast('Conexión interrumpida — selección reseteada', 'error');
    }
    if (_mm.matches > 0) reload();
  }
}

function handleMmEvent(ev) {
  switch (ev.type) {
    case 'start':
      _depMmRunId = ev.run_id;
      _mmFeedAdd('mm-info', `🚀 Iniciado · ${ev.cards} cards × ${ev.accounts} cuentas`);
      break;

    case 'trying': {
      _mm.attempts = ev.attempt;
      const tail = ev.tail.replace('···', '');
      const card = _mm.cards.get(tail);
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.status = 'busy'; card.busyEmail = ev.email; }
      if (acc)  { acc.status = 'busy'; acc.busyTail = tail; }
      _mmRender();
      _mmFeedAdd('mm-trying',
        `<span class="dep-spinner"></span> <b class="mono">${esc(ev.tail)}</b> → <span>${esc(ev.email)}</span>`);
      break;
    }

    case 'phase': {
      // Sub-indicador en vivo dentro del par (email, tail) que está corriendo.
      // Llega ANTES que match/rejected/account_dead — cuando termina, esos
      // eventos cambian el status a matched/dead/idle y el data-pair-key se quita.
      const key = `${ev.email}|${ev.tail}`;
      _mmSetPairPhase(key, ev.name, ev.data || {});
      break;
    }

    case 'match': {
      _mm.matches++;
      const tail = ev.tail.replace('···', '');
      const card = _mm.cards.get(tail);
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.status = 'matched'; card.matchedEmail = ev.email; card.busyEmail = null; card.currentPhase = ''; }
      if (acc) { acc.status = 'done'; acc.matchedTail = tail; acc.matchedPipe = ev.pipe; acc.busyTail = null; acc.currentPhase = ''; }
      _mmRender();
      _mmFeedAdd('mm-match',
        `✓ <b class="mono">${esc(ev.tail)}</b> ↔ <b>${esc(ev.email)}</b> · $${ev.amount.toFixed(2)} <span class="dim mono">${ev.duration_ms}ms</span>`);
      pushNotif({ icon: '💳', msg: `Match: ${ev.tail} ↔ ${ev.email}` });
      break;
    }
    case 'done': {
      _mmFeedAdd('mm-done',
        `<b>Listo</b> · ${ev.matches} match${ev.matches !== 1 ? 'es' : ''} · ${ev.attempts} intentos${ev.pending ? ` · ${ev.pending} sin emparejar` : ''}`);
      // Limpia estados busy → idle al final + limpia currentPhase para no
      // mostrar texto stale si se re-usa el panel para otra ronda
      for (const c of _mm.cards.values()) {
        if (c.status === 'busy') c.status = 'idle';
        c.currentPhase = '';
      }
      for (const a of _mm.accounts.values()) {
        if (a.status === 'busy' || a.status === 'cooldown') a.status = a.fails >= 2 ? 'dead' : 'idle';
        a.currentPhase = '';
      }
      _mmRender();
      // Si hubo matches, ofrecer programar los siguientes depósitos
      if (_mm.matches > 0) _renderPostMatchOffer();
      break;
    }

    case 'rejected': {
      const tail = ev.tail.replace('···', '');
      const card = _mm.cards.get(tail);
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.fails = ev.card_fails ?? card.fails; card.status = 'idle'; card.lastCode = ev.code; card.busyEmail = null; card.currentPhase = ''; }
      if (acc)  {
        acc.fails = ev.acct_fails ?? acc.fails;
        acc.lastCode = ev.code;
        acc.busyTail = null;
        acc.currentPhase = '';
        if (ev.acct_fails >= 2) { acc.status = 'dead'; acc.deadCode = ev.code; }
        else { acc.status = 'cooldown'; }
      }
      _mmRender();
      _mmFeedAdd('mm-rej',
        `✗ <span class="mono">${esc(ev.tail)}</span> → ${esc(ev.email)} <span class="dim mono">${esc(ev.code)}</span>`);
      break;
    }

    case 'card_retired': {
      const tail = ev.tail.replace('···', '');
      const card = _mm.cards.get(tail);
      if (card) { card.status = 'retired'; card.fails = ev.fails; }
      _mmRender();
      const why = card?.lastCode ? ` · ${esc(_mmLabel(card.lastCode))}` : '';
      _mmFeedAdd('mm-info', `🔻 <span class="mono">${esc(ev.tail)}</span> retirada${why}`);
      break;
    }

    case 'account_dead': {
      const acc = _mm.accounts.get(ev.email);
      if (acc) { acc.status = 'dead'; acc.deadCode = ev.code; acc.lastCode = ev.code; acc.busyTail = null; acc.currentPhase = ''; }
      // Tarjeta queda 'idle' (la cuenta murió, no la tarjeta) — limpia su busyEmail
      if (ev.tail) {
        const tail = ev.tail.replace('···', '');
        const card = _mm.cards.get(tail);
        if (card && card.status === 'busy') { card.status = 'idle'; card.busyEmail = null; card.currentPhase = ''; }
      }
      _mmRender();
      const persisted = ev.persisted ? ' <span class="mm-persisted">guardada</span>' : '';
      _mmFeedAdd('mm-dead',
        `💀 <b>${esc(ev.email)}</b> · <b>${esc(_mmLabel(ev.code))}</b> <span class="dim mono">${esc(ev.code)}</span>${persisted}`);
      break;
    }

    case 'account_paused': {
      // La pasarela de la cuenta rechazó N tarjetas (BANK_REJECTED) → sale del
      // run para no martillarla con login+captcha por cada tarjeta. NO es DEAD.
      const acc = _mm.accounts.get(ev.email);
      if (acc) { acc.status = 'dead'; acc.lastCode = 'BANK_REJECTED'; acc.busyTail = null; acc.currentPhase = ''; acc.paused = true; }
      if (ev.tail) {
        const tail = ev.tail.replace('···', '');
        const card = _mm.cards.get(tail);
        if (card && card.status === 'busy') { card.status = 'idle'; card.busyEmail = null; card.currentPhase = ''; }
      }
      _mmRender();
      _mmFeedAdd('mm-rej',
        `⏸ <b>${esc(ev.email)}</b> · pasarela rechaza (${ev.rejects || 2} tarjetas) — fuera del run, NO muerta`);
      break;
    }

    case 'login_retry': {
      // 406 / captcha / proxy = NUESTRO lado, NO la cuenta. Con `retrying` el
      // backend va a reintentar el par; con `exhausted` agotó los reintentos.
      // Ni la cuenta ni la tarjeta se penalizan permanente.
      const tail = (ev.tail || '').replace('···', '');
      const card = _mm.cards.get(tail);
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.status = 'idle'; card.busyEmail = null; card.currentPhase = ''; }
      if (acc)  { acc.status = 'idle'; acc.busyTail = null; acc.currentPhase = ''; acc.lastCode = ev.code; }
      _mmRender();
      const detail = ev.retrying
        ? `reintentando login (${ev.tries || 1}/${ev.max || 3})`
        : 'login falló tras reintentos (NO muerta)';
      _mmFeedAdd('mm-cooldown',
        `🔄 <b>${esc(ev.email)}</b> · ${detail} <span class="dim mono">${esc(ev.code)}</span>`);
      break;
    }

    case 'velocity_skip': {
      // Backend marcó VELOCITY_SKIP — la tarjeta no se consumió pero el par
      // (email, tail) ya pasó por el 'trying' que dejó ambos en busy. Sin
      // este handler, ambos rows quedan con spinner permanente.
      const tail = (ev.tail || '').replace('···', '');
      const card = _mm.cards.get(tail);
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.status = 'idle'; card.busyEmail = null; card.currentPhase = ''; }
      if (acc)  { acc.status = 'idle'; acc.busyTail = null; acc.currentPhase = ''; }
      _mmRender();
      _mmFeedAdd('mm-cooldown',
        `⏳ <span class="mono">${esc(ev.tail || '')}</span> → ${esc(ev.email || '')} velocity skip · ${ev.wait_sec || 0}s`);
      break;
    }

    case 'account_cooling': {
      // RATE_LIMITED (429): la cuenta entró en enfriamiento persistente y sale del
      // run (spec anti-rate-limit Capa 3). Sin este handler, su row (y la tarjeta
      // del par) quedan con spinner permanente — mismo bug que velocity_skip.
      const tail = (ev.tail || '').replace('···', '');
      const card = tail ? _mm.cards.get(tail) : null;
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.status = 'idle'; card.busyEmail = null; card.currentPhase = ''; }
      if (acc)  { acc.status = 'idle'; acc.busyTail = null; acc.currentPhase = ''; acc.lastCode = 'RATE_LIMITED'; }
      _mmRender();
      const mins = ev.cooldown_min || 45;
      _mmFeedAdd('mm-cooldown',
        `🧊 <b>${esc(ev.email)}</b> · enfriando ${mins} min (rate-limit 429) — saltada`);
      break;
    }

    case 'cooldown':
      _mmFeedAdd('mm-cooldown', `⏳ Cooldown ${ev.wait}s…`);
      break;

    case 'error':
      _mmFeedAdd('mm-err', `✗ ${esc(ev.email || '')} ${esc(ev.message || '')}`);
      break;

    case 'cancelled':
      _mmFeedAdd('mm-info', `⏹ Cancelado`);
      break;
  }
}

// Tras matchmaker exitoso, ofrece programar los siguientes depósitos
function _renderPostMatchOffer() {
  const matched = [..._mm.accounts.entries()]
    .filter(([_, a]) => a.status === 'done' && a.matchedTail);
  if (!matched.length) return;
  const view = $('#depMatchView');
  if (!view) return;
  const existing = $('#depPostMatch');
  if (existing) existing.remove();
  const div = document.createElement('div');
  div.id = 'depPostMatch';
  div.className = 'dep-post-match';
  div.innerHTML = `
    <span class="dep-post-match-text">
      🎯 Tienes <b>${matched.length} match${matched.length>1?'es':''}</b>.
      ¿Programar más depósitos con la(s) tarjeta(s) ya casada(s)?
    </span>
    <button class="dep-post-match-btn" id="btnPostMatchSchedule">⏰ Programar</button>
  `;
  view.appendChild(div);
  $('#btnPostMatchSchedule').addEventListener('click', () => {
    // Cambia a modo schedule con la primera cuenta+tarjeta
    const [email, info] = matched[0];
    const accId = info.id;
    _depAccountIds = [accId];
    setDepMode('schedule');
    $('#depCardPipe').value = info.matchedPipe || '';
    refreshCapStatus(accId);
    div.remove();
    toast(`⏰ Listo: ${matched.length>1?'usando primer match':'tarjeta cargada'}`, 'success');
  });
}

async function cancelMatchmaker() {
  if (!_depMmRunId) {
    if (_depMmAbort) _depMmAbort.abort();
    return;
  }
  try {
    await fetch(`/api/deposits/multi/${_depMmRunId}/cancel`, { method: 'POST' });
    toast('⏹ Cancelando…', 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// Cancel del scheduled actualmente activo. El backend hace task.cancel() → el
// loop sale por CancelledError y broadcastea scheduled_cancelled, que dispara
// la limpieza de UI vía _schedReset() en el handler SSE.
async function cancelScheduled() {
  const sid = _schedActive?.sched_id;
  if (!sid) return;
  if (!confirm('¿Cancelar la misión programada? Los intentos ya enviados quedan guardados.')) return;
  const btn = $('#depSchedCancel');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Cancelando…'; }
  try {
    const r = await fetch(`/api/deposits/scheduled/${sid}/cancel`, { method: 'POST' });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    toast('⏹ Misión cancelada', 'success');
  } catch (e) {
    toast(`Error cancelando: ${e.message}`, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '⏹ Cancelar misión'; }
  }
}

// ── Wire-up ──
$('#depDrawerClose').addEventListener('click', closeDepositModal);

// ── Collapse / expand del drawer (rail mode) ──
// Persistente en localStorage. Cuando colapsado, el drawer queda a 36px y
// el body empuja solo ese ancho. Click en el botón vuelve a 420px.
const _DEP_COLLAPSE_KEY = 'depDrawerCollapsed';
let _depDrawerCollapsed = localStorage.getItem(_DEP_COLLAPSE_KEY) === '1';
function _applyDepCollapsed() {
  const d = $('#depDrawer');
  const btn = $('#depDrawerCollapseBtn');
  d.classList.toggle('dep-drawer-collapsed', _depDrawerCollapsed);
  document.body.classList.toggle('dep-drawer-collapsed', _depDrawerCollapsed);
  if (btn) {
    btn.textContent = _depDrawerCollapsed ? '«' : '»';
    btn.title = _depDrawerCollapsed
      ? 'Expandir panel (vuelve a 420px)'
      : 'Colapsar panel (queda como rail de 36px)';
  }
}
function _toggleDepCollapsed(force) {
  _depDrawerCollapsed = (typeof force === 'boolean') ? force : !_depDrawerCollapsed;
  localStorage.setItem(_DEP_COLLAPSE_KEY, _depDrawerCollapsed ? '1' : '0');
  _applyDepCollapsed();
}
$('#depDrawerCollapseBtn')?.addEventListener('click', () => _toggleDepCollapsed());
_applyDepCollapsed();  // restore al cargar

// Mini-pill reabre el drawer sin tocar el state (la misión sigue activa).
$('#depMissionPill').addEventListener('click', e => {
  // Ignorar clicks que ya manejó el botón interno (evita doble open).
  if (e.target.id === 'depPillReopen') return;
  _depPillReopen();
});
$('#depPillReopen').addEventListener('click', _depPillReopen);
$('#depModeSeg').addEventListener('click', e => {
  const btn = e.target.closest('.dep-drawer-tab');
  if (!btn) return;
  if (_depBusy) { toast('Espera a que termine', 'error'); return; }
  setDepMode(btn.dataset.mode);
});
$('#depAmounts').addEventListener('click', e => {
  const btn = e.target.closest('.dep-amt');
  if (!btn) return;
  $$('#depAmounts .dep-amt').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _depAmount = btn.dataset.v === 'custom' ? 'custom' : parseFloat(btn.dataset.v);
  const cust = $('#depCustomAmount');
  if (btn.dataset.v === 'custom') { cust.classList.remove('hidden'); setTimeout(() => cust.focus(), 30); }
  else cust.classList.add('hidden');
});
$('#depExec').addEventListener('click', executeDeposit);
$('#depCancel').addEventListener('click', cancelMatchmaker);
$('#depSchedCancel')?.addEventListener('click', cancelScheduled);
$('#depCardPipe').addEventListener('input', () => {
  $('#depCardErr').classList.add('hidden');
});
$('#depCardChips').addEventListener('click', e => {
  const chip = e.target.closest('.dep-chip');
  if (!chip) return;
  $('#depCardPipe').value = chip.dataset.pipe;
  $('#depCardPipe').focus();
});
$('#depMultiPool').addEventListener('input', () => {
  const lines = $('#depMultiPool').value.split('\n').map(l => l.trim()).filter(Boolean);
  $('#depPoolCount').textContent = `${lines.length} tarjeta${lines.length !== 1 ? 's' : ''}`;
});
$('#depMultiList').addEventListener('click', e => {
  const rm = e.target.closest('.dep-multi-rm');
  if (!rm) return;
  const id = parseInt(rm.dataset.id);
  _depAccountIds = _depAccountIds.filter(x => x !== id);
  if (_depAccountIds.length < 2) {
    setDepMode('single');
  } else {
    renderMultiAccounts();
  }
});
document.querySelector('#depScheduleBlock')?.addEventListener('click', e => {
  const btn = e.target.closest('.dep-step-btn');
  if (!btn) return;
  const d = parseInt(btn.dataset.d);
  _depReps = Math.max(1, Math.min(20, _depReps + d));
  $('#depRepsVal').textContent = String(_depReps);
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && _depDrawerOpen) closeDepositModal();
  if (e.key === 'Enter' && _depDrawerOpen && document.activeElement?.id === 'depCardPipe') {
    executeDeposit();
  }
});

// Botón cmdBar — abre el modal con TODAS las seleccionadas
$('#cmdDeposit').addEventListener('click', () => {
  if (selectedIds.size === 0) { toast('Selecciona al menos 1 cuenta', 'error'); return; }
  if (selectedIds.size > 5) { toast('Máximo 5 cuentas para multi', 'error'); return; }
  openDepositModal(null, { ids: [...selectedIds] });
});

$('#cmdCopy')?.addEventListener('click', copySelectedCombos);
$('#cmdTrastienda')?.addEventListener('click', bulkTrastienda);
$('#cmdLock').addEventListener('click', bulkLock);
$('#cmdUnlock')?.addEventListener('click', bulkUnlock);
$('#cmdDeselect').addEventListener('click', deselectAll);

// Click en el chip "2h" del botón Lock abre el selector
$('#cmdLockHours')?.addEventListener('click', e => {
  e.preventDefault();
  e.stopPropagation();
  $('#lockHoursPopup').classList.toggle('hidden');
});
$('#lockHoursPopup')?.addEventListener('click', e => {
  const btn = e.target.closest('.lh-btn');
  if (!btn) return;
  state.lockHours = parseInt(btn.dataset.h);
  $('#cmdLockHours').textContent = `${state.lockHours}h`;
  $$('#lockHoursPopup .lh-btn').forEach(b => b.classList.toggle('on', b === btn));
  $('#lockHoursPopup').classList.add('hidden');
});
document.addEventListener('click', e => {
  if (!e.target.closest('.cmd-lock-wrap')) $('#lockHoursPopup')?.classList.add('hidden');
});

$('#bellBtn')?.addEventListener('click', () => {
  if (state.section === 'notifications') {
    showSection(_lastNonNotifSection || 'accounts');
  } else {
    showSection('notifications');
  }
});

// Click en "En uso" del Pool → filtra accounts por las que tienen lock activo
$('#lpInUse')?.addEventListener('click', () => {
  state.filterInUse = !state.filterInUse;
  state.page = 1;
  $('#lpInUse').classList.toggle('lp-stat-active', state.filterInUse);
  showSection('accounts');
  renderTable();
  toast(state.filterInUse ? '🎣 Filtro: solo en uso' : '↺ Filtro removido', 'success');
});
// Click en "Pool" → quita filtros, muestra todas
$('#lpPool')?.addEventListener('click', () => {
  if (state.filterInUse) {
    state.filterInUse = false;
    $('#lpInUse').classList.remove('lp-stat-active');
    state.page = 1;
    showSection('accounts');
    renderTable();
  }
});

// Click en avatar de la L invertida → filtra activity por ese operador
$('#lpOps')?.addEventListener('click', e => {
  const op = e.target.closest('.lp-op');
  if (!op) return;
  const uid = parseInt(op.dataset.uid);
  if (!uid) return;
  activityFilter.who = uid;
  showSection('activity');
});
$('#btnClearNotif').addEventListener('click', () => { notifications = []; renderNotifs(); renderNotifBadge(); });

$$('.sb-user .ico-btn, .ico-btn[title="Salir"], .power').forEach(btn => {
  btn.addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  });
});

// ─── Rehidratación tras refresh ───
// TDAH-friendly: si Robert recarga la página estando una misión scheduled
// en curso, NO puede perderla de vista. El backend mantiene la misión viva
// en _active_schedules y la expone vía /scheduled/list. Aquí la reanclamos
// al drawer y dejamos el SSE seguir pintando eventos como si no hubiera
// pasado nada — el operador retoma el contexto sin esfuerzo.
async function rehydrateActiveScheduled() {
  try {
    const r = await fetch('/api/deposits/scheduled/list');
    if (!r.ok) return;
    const list = await r.json();
    if (!Array.isArray(list) || list.length === 0) return;

    // Si hay varias (caso SA viendo todas), elegir la del user actual o la primera
    const meId = state.user?.telegram_id;
    const sched = list.find(s => s.operator_id === meId) || list[0];

    // Abrir el drawer (sin pasar por openDepositModal — no requiere cuenta seleccionada)
    $('#depDrawer').classList.add('dep-drawer-open');
    document.body.classList.add('dep-drawer-pushing');
    _depDrawerOpen = true;
    if (_depDrawerCollapsed) _toggleDepCollapsed(false);

    // Forzar tab Prog. visible (los handlers de tab manejan el resto del layout)
    setDepMode('schedule');

    // Si encontramos la cuenta en state.rows, llenar target block para contexto
    const acct = (state.rows || []).find(x => x.email === sched.email);
    if (acct) {
      _depAccountIds = [acct.id];
      const tEl = $('#depTargetEmail');
      if (tEl) {
        tEl.textContent = acct.password ? `${acct.email}:${acct.password}` : acct.email;
      }
      const bEl = $('#depTargetBalance');
      if (bEl) bEl.textContent = fmtMoney(acct.balance_total);
    }
    // Repins de la tarjeta usada (visible en el input para contexto)
    if (sched.card_pipe) {
      const cardEl = $('#depCardPipe');
      if (cardEl) cardEl.value = sched.card_pipe;
    }
    $('#depRepsVal').textContent = String(sched.repetitions);

    // Mostrar la vista live con el iter actual ya anclado (no esperar al primer SSE)
    _schedShow(sched.sched_id, sched.repetitions, {
      currentIter: sched.current_iter || 0,
      resumed: true,
    });
    toast(
      `↺ Misión activa reanclada · iter ${sched.current_iter || 0}/${sched.repetitions} · ${sched.email}`,
      'success'
    );
  } catch (e) {
    console.warn('[rehydrate] scheduled error:', e);
  }
}

// ─── Pool card — role-aware render ───
function renderPoolCard() {
  const isSA = state.user?.role === 'superadmin';
  const card = document.querySelector('.lp-card.lp-pool');
  if (!card) return;

  if (isSA) {
    // SA: hero + barra de salud visibles; grid 4-stat (la llena refreshKpis)
    const hero = document.getElementById('lpPoolHero'); if (hero) hero.style.display = '';
    const bar = document.getElementById('lpPoolBar'); if (bar) bar.style.display = '';
    // solo añadir Gestionar una vez
    if (!card.querySelector('.lp-pool-manage')) {
      const btn = document.createElement('button');
      btn.className = 'lp-pool-manage';
      btn.type = 'button';
      btn.textContent = 'Gestionar pool';
      btn.addEventListener('click', () => showSection('pool'));
      card.appendChild(btn);
    }
    return;
  }

  // Operador: "Mis stats del día" — hero/barra del pool NO aplican (se ocultan)
  const hero = document.getElementById('lpPoolHero'); if (hero) hero.style.display = 'none';
  const bar = document.getElementById('lpPoolBar'); if (bar) bar.style.display = 'none';
  const s = window._recentStats || { attempts: 0, approved: 0, amount: 0, rate: 0 };
  const body = document.getElementById('lpPoolCard');
  if (!body) return;
  // Cambiar sub-header de "Pool" → "hoy"
  const sub = document.getElementById('lpPoolSub');
  if (sub) sub.textContent = 'hoy';
  body.innerHTML = `
    <div class="lp-stat"><span class="lp-stat-label">Intentos</span><b class="lp-stat-val">${s.attempts}</b></div>
    <div class="lp-stat"><span class="lp-stat-label">Aprobados</span><b class="lp-stat-val">${s.approved}</b></div>
    <div class="lp-stat"><span class="lp-stat-label">Monto</span><b class="lp-stat-val">$${(s.amount || 0).toLocaleString()}</b></div>
    <div class="lp-stat"><span class="lp-stat-label">Tasa</span><b class="lp-stat-val">${s.rate}%</b></div>`;
}

// ─── Recientes (card lateral) ───
async function loadRecientes() {
  try {
    const d = await (await fetch('/api/recent')).json();
    renderRecientes(d.recent || []);
    window._recentStats = d.stats || null;
    renderPoolCard();
  } catch {}
}
function renderRecientes(items) {
  const host = $('#lpRecientes');
  if (!host) return;
  const cnt = $('#lpRecientesCount');
  if (cnt) cnt.textContent = items.length;
  // Estado a color (escaneable): en uso=verde · depósito=oro · fijada=púrpura
  const meta = r => r === 'deposit' ? { cls: 'rec-dep',  lbl: 'depósito' }
                  : r === 'lock'    ? { cls: 'rec-use',  lbl: 'en uso'   }
                  : r === 'mark'    ? { cls: 'rec-mark', lbl: 'fijada'   }
                  : { cls: '', lbl: r };
  host.innerHTML = items.length === 0
    ? '<div class="lp-empty dim mono">sin recientes</div>'
    : items.map(it => {
        const m = meta(it.reason);
        return `<div class="lp-recent-row ${m.cls} d-copy" data-email="${esc(it.email)}" data-copy="${esc(it.combo)}" title="Click para copiar combo">
        <span class="lp-recent-combo mono">${esc(it.combo)}</span>
        <span class="lp-recent-st">${m.lbl}</span>
        <span class="lp-recent-time">${fmtAgo(it.last_ts)}</span>
      </div>`;
      }).join('');
}

// ─── init ───
(async () => {
  await loadMe();
  // Cargar marcas privadas antes del primer render (para que 📌 aparezca activo)
  try {
    const m = await (await fetch('/api/marks')).json();
    markedSet = new Set(m.marks || []);
  } catch {}
  tickGreeting();
  setInterval(tickGreeting, 30_000);
  tickFrase();
  setInterval(tickFrase, 9_000);
  await reload();
  _loadPassMap();
  renderPoolCard();
  refreshKpis();
  setInterval(refreshKpis, 30_000);
  loadActivityMarquee();
  loadRecientes();
  loadHealth(false);
  connectSSE();
  // Reanclar misiones programadas activas DESPUÉS de reload() (necesitamos
  // state.rows para resolver el target block) y de connectSSE (para que los
  // próximos phase events lleguen al handler ya cargado).
  rehydrateActiveScheduled();
})();

window.addEventListener('beforeunload', () => {
  if (_evtSrc) _evtSrc.close();
});
