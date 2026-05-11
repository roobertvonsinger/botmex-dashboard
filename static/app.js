// Botmexico v2 — vanilla, sin frameworks.

const FRASES = [
  "¿Ya desayunaste o puro café y ansiedad?",
  "Échale ganas, mi rey — la chamba no se hace sola.",
  "Hoy es buen día pa' tirar pa'rriba 🇲🇽",
  "Si no puedes con el enemigo, hackéalo.",
  "El que madruga, encuentra cuentas LIVE.",
  "Calladito te ves más bonito… y vendes más.",
  "No es magia, es disciplina. Bueno, y un poquito de magia.",
  "Trabaja en silencio, deja que tu saldo haga el ruido.",
  "Hoy se chambea con todo, mañana descansamos (mentira).",
  "El éxito sabe a tacos al pastor.",
];

const esc = s => s == null ? '' : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

const state = {
  section: 'accounts',
  status: 'LIVE',
  grade: '',
  view: 'simple',
  rows: [],
  user: null,
  page: 1,
  pageSize: 50,
  lockHours: 2,
  filterInUse: false,
  cardsOnly: false,  // filter: solo cuentas con al menos 1 tarjeta
};


const selectedIds = new Set();
let searchQuery = '';
let activityRows = [];
let activityFilter = { kind: '', who: null, time: 'all', q: '' };
let activityPage = 1;
let activityPageSize = 50;
const _actNewIds = new Set();   // ids/keys de eventos llegados via SSE — para animar como nuevos
let notifications = [];
let _evtSrc = null;
let _sortCol = null, _sortDir = -1;

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
const gradeClass = g => ({ A: 'A', B: 'B', C: 'C', D: 'D' })[g] || 'U';

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
  'CAMP': 'CC', 'COL': 'CM',
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
// Glow tiers para el saldo:
//   ≥ $10  → glow (verde brillante)
//   $5-$10 → tenue/grisecito
//   ≤ $5   → default (verde normal)
//   $0     → zero (gris)
const balanceCls = v => {
  if (!v || v <= 0) return 'zero';
  if (v >= 10) return 'glow';
  if (v > 5) return 'dim-amount';
  return '';
};
const getVisible = () => state.filterInUse
  ? state.rows.filter(r => r.locked_by)
  : state.rows;

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

  // L invertida (control multiusuario) SOLO superadmin — admin no debe ver indicios de SA
  if (!isSuper) {
    $('#adminPanel').style.display = 'none';
    document.body.classList.add('no-kpis');
  }
  // Vista Detallada solo superadmin (admin/user usan Simple)
  if (!isSuper) {
    const viewSeg = document.querySelector('.seg[data-seg="view"]');
    if (viewSeg) viewSeg.style.display = 'none';
    state.view = 'simple';
  }
  // Logs y Health solo superadmin
  if (!isSuper) {
    $('#navLogs').style.display = 'none';
    $('#navHealth').style.display = 'none';
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
  // +15ch de margen a la derecha — más cómodo visualmente
  t.style.setProperty('--combo-width', `${Math.min(maxComboLen + 15, 75)}ch`);
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

  const colspan = state.view === 'simple' ? 6 : 8;
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
    // Iconos de fila: 💳 (tarjetas), 📝 (notas), siempre + (quick add) + botón Detalles
    const hasCards = (r.cards_count || 0) > 0;
    const hasNotes = (r.notes_count || 0) > 0;
    let iconsHtml = '';
    if (hasCards) {
      iconsHtml += `<button class="row-ic ic-cards" data-id="${r.id}" data-email="${esc(r.email)}" title="${r.cards_count} tarjeta${r.cards_count>1?'s':''}">💳<sup>${r.cards_count}</sup></button>`;
    }
    if (hasNotes) {
      iconsHtml += `<button class="row-ic ic-notes" data-id="${r.id}" data-email="${esc(r.email)}" title="${r.notes_count} nota${r.notes_count>1?'s':''}">📝<sup>${r.notes_count}</sup></button>`;
    }
    iconsHtml += `<button class="row-ic ic-add" data-id="${r.id}" data-email="${esc(r.email)}" title="Añadir nota rápida">+ Nota</button>`;

    // Botón "Detalles" premium — único acceso al modal
    const detailsBtn = `<button class="row-details" data-id="${r.id}" title="Ver detalles completos de la cuenta">
      <span class="row-details-text">detalles</span>
      <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.938a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z" clip-rule="evenodd"/>
      </svg>
    </button>`;

    if (state.view === 'simple') {
      return `<tr class="${trClasses}" data-id="${r.id}" title="${trTitle || ''}">
        <td class="grade-bar-cell" title="Grade ${esc(r.grade) || '?'}"></td>
        <td class="sel-cell" title="Click selecciona la fila"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
        <td class="num" title="Saldo total disponible"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span></td>
        <td class="combo"><b data-id="${r.id}" data-combo="${esc(combo)}" title="Click para copiar combo">${esc(combo)}</b>${lockChip}</td>
        <td class="row-details-cell">${detailsBtn}</td>
        <td class="dep" title="Último depósito hecho">${dep}</td>
        <td class="row-icons">${iconsHtml}</td>
      </tr>`;
    }
    return `<tr class="${trClasses}" data-id="${r.id}" title="${trTitle || ''}">
      <td class="grade-bar-cell" title="Grade ${esc(r.grade) || '?'}"></td>
      <td class="sel-cell" title="Click selecciona la fila"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
      <td class="num" title="Saldo total disponible"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span></td>
      <td class="combo"><b data-id="${r.id}" data-combo="${esc(combo)}" title="Click para copiar combo">${esc(combo)}</b></td>
      <td class="row-details-cell">${detailsBtn}</td>
      <td class="dep" title="Último depósito hecho">${dep}</td>
      <td class="dep dim" title="Cuándo se actualizó por última vez">${fmtAgo(r.last_checked_at)}</td>
      <td class="num" title="Total de veces actualizada">${r.check_count || 0}</td>
      <td class="row-icons">${iconsHtml}</td>
    </tr>`;
  }).join('');

  t.querySelector('tbody').innerHTML = rowsHtml || `<tr><td colspan="${colspan}" class="loading">Sin cuentas</td></tr>`;

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
  return r.json();
}

function actionLabel(kind) {
  if (kind === 'deposit') return '💳 Depósito';
  if (kind === 'lock') return '🔒 Lock';
  if (kind === 'unlock') return '🔓 Unlock';
  if (kind === 'note') return '📝 Nota';
  if (kind?.startsWith('prewarm_')) return '· login bg';  // auditoría interna, sin ruido
  return kind;
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
// Helper: resuelve email -> "email:password" combo desde state.rows (cache).
// Si la cuenta no está en cache (filtrada/no cargada), devuelve solo el email.
function _resolveComboFromEmail(email) {
  if (!email) return '';
  const row = (state.rows || []).find(r => r.email === email);
  return row ? `${row.email}:${row.password || ''}` : email;
}

function renderActivity() {
  const t = $('#actTable');
  t.querySelector('thead').innerHTML = `
    <tr>
      <th>Cuándo</th><th>Quién</th><th>Acción</th><th>Cuenta</th>
      <th>Tarjeta</th>
      <th class="num">Monto</th><th>Estado</th>
    </tr>`;
  const filtered = getFilteredActivity();
  const total = filtered.length;
  const pages = Math.max(1, Math.ceil(total / activityPageSize));
  if (activityPage > pages) activityPage = pages;
  const start = (activityPage - 1) * activityPageSize;
  const slice = filtered.slice(start, start + activityPageSize);

  $('#actCountLabel').textContent = `${total} evento${total === 1 ? '' : 's'}`;

  t.querySelector('tbody').innerHTML = slice.map(e => {
    const key = _actEventKey(e);
    const newCls = _actNewIds.has(key) ? ' act-row-new' : '';
    return `<tr class="act-${esc(e.kind)}${newCls}" data-evkey="${esc(key)}">
      <td class="dim mono act-when" title="${esc(e.ts || '')}">
        <span class="act-abs">${fmtAbs(e.ts)}</span>
        <span class="act-rel dim">${fmtAgo(e.ts)}</span>
      </td>
      <td><span class="act-who" data-who="${esc(e.who ?? '')}">${esc(e.who ?? '—')}</span></td>
      <td>${actionLabel(e.kind)}</td>
      <td class="combo"><b class="act-target d-copy" data-email="${esc(e.target || '')}" data-copy="${esc(_resolveComboFromEmail(e.target))}" title="Click para copiar combo">${esc(e.target || '—')}</b></td>
      <td class="combo">${e.card_pipe ? `<b class="d-copy mono" data-copy="${esc(e.card_pipe)}" title="Click para copiar tarjeta">${esc(e.card_pipe)}</b>` : '<span class="dim">—</span>'}</td>
      <td class="num">${e.amount != null ? fmtMoney(e.amount) : ''}</td>
      <td>${statusPill(e)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="loading">Sin actividad que coincida con los filtros</td></tr>';

  // Limpieza: las claves que ya pintamos como "nuevas" se consumen
  for (const ev of slice) _actNewIds.delete(_actEventKey(ev));

  // Visible count + pagination
  const from = total === 0 ? 0 : start + 1;
  const to = Math.min(start + activityPageSize, total);
  const vc = $('#actVisibleCount');
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
      `<tr><td colspan="7" class="loading" style="color:var(--danger)">Error: ${esc(e.message)}</td></tr>`;
  }
}
function pushActivityEvent(ev) {
  // Insert at top, dedupe-ish, cap 500
  const row = {
    kind: ev.kind, ts: ev.ts, who: ev.who, who_color: ev.who_color,
    target: ev.target, amount: ev.amount, status: ev.status,
    reason: ev.reason, duration_ms: ev.duration_ms, id: ev.id, text: ev.text,
  };
  activityRows.unshift(row);
  if (activityRows.length > 500) activityRows.length = 500;
  // Marca como "nuevo" para animación highlight si la fila aparece en pantalla
  _actNewIds.add(_actEventKey(row));
  if (state.section === 'activity') renderActivity();
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
    badge.textContent = unread;
    badge.classList.remove('hidden');
    navBadge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
    navBadge.classList.add('hidden');
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
  $$('.nav[data-section]').forEach(btn => btn.classList.toggle('on', btn.dataset.section === name));
  if (name === 'pool') reloadPool();
  if (name === 'activity') reloadActivity();
  if (name === 'notifications') renderNotifs();
  if (name === 'logs') startLogsPolling(); else stopLogsPolling();
  if (name === 'health') loadHealth(false);
  if (name === 'admin') loadAdminState();
}

// ─── Pool view (SA only) ───
async function reloadPool() {
  const t = $('#poolTable');
  if (!t) return;
  try {
    const r = await fetch('/api/pool/accounts');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const rows = await r.json();
    $('#poolCountLabel').textContent = `${rows.length} cuenta${rows.length !== 1 ? 's' : ''} visibles a operadores`;
    $('#navPoolCount').textContent = rows.length;
    t.querySelector('thead').innerHTML = `<tr>
      <th class="grade-bar-th"></th>
      <th class="num">Saldo</th>
      <th>Cuenta</th>
      <th>Asignada a</th>
      <th>Lock</th>
      <th class="num"></th>
    </tr>`;
    t.querySelector('tbody').innerHTML = rows.map(r => {
      const g = gradeClass(r.grade);
      const until = r.locked_by ? fmtUntil(r.locked_until) : null;
      const lockChip = r.locked_by
        ? `<span class="lock-chip op-accent">🔒 ${esc(r.locked_by)}${until && !until.expired ? ` <span class="dim mono">${until.text}</span>` : ''}</span>`
        : '<span class="dim">libre</span>';
      const assigned = r.assigned_to > 0 ? `<span class="dim mono">${r.assigned_to} usuario(s)</span>` : '<span class="dim">—</span>';
      const combo = `${r.email}:${r.password || ''}`;
      return `<tr class="r-grade-${g}" data-id="${r.id}">
        <td class="grade-bar-cell"></td>
        <td class="num"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span></td>
        <td class="combo"><b data-combo="${esc(combo)}">${esc(combo)}</b></td>
        <td>${assigned}</td>
        <td>${lockChip}</td>
        <td class="num"><button class="seg-btn pool-hide-btn" data-id="${r.id}" title="Quitar de la vista de operadores">×</button></td>
      </tr>`;
    }).join('') || '<tr><td colspan="6" class="loading">Pool vacía — pica "Liberar" desde Cuentas para empezar a publicar</td></tr>';
  } catch (e) {
    t.querySelector('tbody').innerHTML = `<tr><td colspan="6" class="loading" style="color:var(--danger)">Error: ${esc(e.message)}</td></tr>`;
  }
}

async function hideAllPool() {
  if (!confirm('¿Quitar TODAS las cuentas de la vista de los operadores?\n\nLos operadores dejarán de verlas hasta que las publiques de nuevo desde Cuentas → Liberar.')) return;
  try {
    const r = await fetch('/api/accounts/hide-all', { method: 'POST' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    toast(`📤 ${data.hidden} ocultas`, 'success');
    reloadPool();
    reload();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function removeFromPool(id) {
  try {
    const r = await fetch('/api/accounts/publish', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ids: [id], publish: false }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    toast('✓ Quitada de pool', 'success');
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

// ─── SSE ───
function connectSSE() {
  _evtSrc = new EventSource('/api/events');
  _evtSrc.onmessage = e => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'activity') {
        // Feed de Actividad
        pushActivityEvent(ev);
        // Notificaciones para acciones que importan
        if (ev.kind === 'lock') {
          pushNotif({ icon: '🔒', msg: `${ev.who} bloqueó ${ev.target}` });
          reload();
        } else if (ev.kind === 'unlock') {
          pushNotif({ icon: '🔓', msg: `${ev.who} liberó ${ev.target}` });
          reload();
        } else if (ev.kind === 'deposit') {
          const ok = ev.status === 'approved';
          pushNotif({
            icon: ok ? '✅' : '❌',
            msg: `${ev.who} depositó ${fmtMoney(ev.amount)} en ${ev.target} → ${ev.status}`,
          });
          if (ok) reload();
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
      } else if (ev.type === 'alert') {
        // Alertas críticas (capmonster_low, proxy_down) — push notif + toast
        pushNotif({ icon: ev.icon || '⚠️', msg: ev.msg });
        toast(`${ev.icon || '⚠️'} ${ev.msg}`, ev.severity === 'danger' ? 'error' : 'warn');
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
          reload();
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
      if (p && p.ok) {
        const lat = p.latency_ms != null ? `${p.latency_ms}ms` : 'OK';
        stProxy.textContent = `${p.country || 'OK'} · ${lat}`;
        stProxy.classList.add(p.latency_ms > 1500 ? 'warn' : 'ok');
        stProxy.title = `LitPort ${p.host}\nIP: ${p.ip || '?'}\nLatencia: ${lat}`;
      } else if (p) {
        stProxy.textContent = 'caído';
        stProxy.classList.add('danger');
        stProxy.title = `LitPort ${p.host || ''}\n${p.error || 'sin respuesta'}`;
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

    // ── Bloque 2: Feed live ──
    const feed = k.feed || [];
    $('#lpFeedCount').textContent = feed.length ? `${feed.length} eventos` : '—';
    $('#lpFeed').innerHTML = feed.length === 0
      ? '<div class="lp-empty dim mono">esperando actividad…</div>'
      : feed.map(e => {
          const isDepOk   = e.kind === 'deposit' && e.status === 'approved';
          const isDepFail = e.kind === 'deposit' && e.status !== 'approved';
          const ic = e.kind === 'deposit' ? (isDepOk ? '💰' : '✗')
                   : e.kind === 'lock' ? '🔒' : '·';
          const col = e.who_color || 'accent';
          const rowCls = isDepOk ? 'lp-feed-ok' : isDepFail ? 'lp-feed-fail' : 'lp-feed-neutral';
          const combo = _resolveComboFromEmail(e.target || '');
          // Toda la fila navega al panel de Actividad. El combo (target) tiene data-copy
          // para 1-click izquierdo copiar (el handler global stopPropagation evita
          // que dispare también la navegación).
          return `<div class="lp-feed-row ${rowCls} lp-feed-clickable" data-nav="activity" title="Click para ir al panel de Actividad">
            <span class="lp-feed-ic">${ic}</span>
            <span class="lp-feed-who lp-color-${esc(col)}">${esc(e.who || '—')}</span>
            <span class="lp-feed-target dim mono d-copy" data-copy="${esc(combo)}" title="Click para copiar combo">${esc(e.target || '')}</span>
            ${e.amount != null ? `<span class="lp-feed-amt mono">${fmtMoney(e.amount)}</span>` : ''}
            <span class="lp-feed-time mono dim">${fmtAgo(e.ts)}</span>
          </div>`;
        }).join('');

    // ── Bloque 3: Alertas ──
    const alerts = k.alerts || [];
    $('#lpAlertCount').textContent = alerts.length;
    $('#lpAlertCount').classList.toggle('warn', alerts.length > 0);
    $('#lpAlerts').innerHTML = alerts.length === 0
      ? '<div class="lp-empty dim mono">sin alertas</div>'
      : alerts.map(a => `<div class="lp-alert-row sev-${esc(a.severity)}">
          <span class="lp-alert-msg">${esc(a.msg)}</span>
          <span class="lp-alert-time mono dim">${fmtAgo(a.ts)}</span>
        </div>`).join('');

    // ── Bloque 4: Pool ──
    const p = k.pool || {};
    $('#lpPool').textContent = (p.pool ?? 0).toLocaleString();
    $('#lpInUse').textContent = (p.in_use ?? 0).toLocaleString();
    $('#lpTras').textContent = p.trastienda ?? 0;
    $('#lpReb').textContent = (p.rebotadas ?? 0).toLocaleString();
    $('#lpPoolSub').textContent = `${(p.pool ?? 0) + (p.in_use ?? 0)} LIVE`;
  } catch (e) {
    console.error('KPI error:', e);
  } finally {
    kpiRefreshing = false;
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
  _refreshing = true;
  const force = !!opts.force;
  const ids = opts.ids || getPaged().rows.map(r => r.id);
  if (!ids.length) { _refreshing = false; return; }
  const btn = $('#btnRefreshVisible');
  if (btn) {
    btn.classList.add('refreshing');
    btn.innerHTML = `⏹ Detener · 0/${ids.length}${force ? ' (forzado)' : ''}`;
    btn.style.setProperty('--prog', '0%');
    btn.style.pointerEvents = 'auto';
  }

  const idSet = new Set(ids);
  document.querySelectorAll('#accTable tbody tr[data-id]').forEach(tr => {
    if (idSet.has(parseInt(tr.dataset.id))) {
      tr.classList.add('row-refreshing');
    }
  });
  toast(`↻ Refrescando ${ids.length} en vivo…`);

  let updated = 0, failed = 0, skipped = 0;
  let started = false;
  let forceableIds = [];   // ids saltados por reglas anti-spam que SA puede forzar
  let skipReasons = {};
  let failReasons = {};
  let lastEventAt = Date.now();
  let watchdog = null;
  const ctrl = new AbortController();
  _refreshAbort = ctrl;
  const total = ids.length;

  // Helper: actualiza visual del botón con progreso
  const updateProgress = () => {
    if (!btn) return;
    const done = updated + failed + skipped;
    const pct = total > 0 ? (done / total) * 100 : 0;
    btn.innerHTML = `⏹ Detener · ${done}/${total}`;
    btn.style.setProperty('--prog', `${pct}%`);
  };

  // Watchdog: si no llega ningún evento en 90s, aborta con error visible
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
              toast(`⚠️ CapMonster bajo ($${ev.capmonster_balance?.toFixed(2)}) — sigue corriendo, recarga pronto`, 'error');
            }
            if (ev.cap_remaining === 0) {
              toast(`⚠️ Cap 30/10min agotado (${ev.cap_used} usados) — espera 10min`, 'error');
            }
          } else if (ev.type === 'account' && ev.data) {
            updated++;
            const i = state.rows.findIndex(x => x.id === ev.data.id);
            if (i >= 0) state.rows[i] = { ...state.rows[i], ...ev.data };
            _swapRowWithAnim(ev.data.id);
            updateProgress();
          } else if (ev.type === 'fail') {
            failed++;
            failReasons[ev.error || 'error'] = (failReasons[ev.error || 'error'] || 0) + 1;
            _markRowFail(ev.id, ev.error);
            updateProgress();
          } else if (ev.type === 'skip') {
            skipped++;
            skipReasons[ev.reason] = (skipReasons[ev.reason] || 0) + 1;
            if (ev.can_force) forceableIds.push(ev.id);
            _markRowSkip(ev.id, ev.reason);
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
      toast(`⚠️ 0 cuentas procesadas — bot deps no cargan en VPS?`, 'error');
    } else if (updated === 0 && skipped > 0) {
      toast(`⚠️ ${skipped} saltadas, 0 actualizadas`, 'error');
    } else if (updated === 0 && failed > 0) {
      // Todos fallaron — mostrar razón principal (BAN, rate limit, etc)
      const topReason = Object.entries(failReasons).sort((a,b)=>b[1]-a[1])[0];
      toast(`✗ ${failed} falló · ${topReason ? topReason[0].slice(0,60) : 'error'}`, 'error');
    } else {
      toast(`✓ ${parts.join(' · ')}`, failed ? 'error' : 'success');
    }
    // Si hay skips force-ables (SA), preguntar si quiere forzar
    if (forceableIds.length > 0 && !force) {
      const fresh = skipReasons['fresh'] || 0;
      const limit = skipReasons['daily_limit'] || 0;
      const detail = [];
      if (fresh) detail.push(`${fresh} actualizadas hace <30min`);
      if (limit) detail.push(`${limit} ya checadas 3+ veces hoy`);
      const msg = `${forceableIds.length} cuentas omitidas:\n• ${detail.join('\n• ')}\n\n¿Forzar refresh de ESAS cuentas?`;
      // Defer fuera del finally para que el botón se rehabilite
      setTimeout(() => {
        if (confirm(msg)) {
          refreshVisible({ ids: forceableIds, force: true });
        }
      }, 200);
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
    _refreshing = false;   // ← SIN ESTO el botón quedaba bloqueado para siempre
    if (btn) {
      btn.classList.remove('refreshing');
      btn.innerHTML = '↻ Actualizar visibles';
      btn.style.removeProperty('--prog');
    }
    setTimeout(() => {
      document.querySelectorAll('#accTable tbody tr.row-refreshing').forEach(tr => {
        tr.classList.remove('row-refreshing');
      });
    }, 800);
  }
}

// Repinta una fila con fade-out → fade-in + glow temporal
function _swapRowWithAnim(id) {
  const tr = document.querySelector(`#accTable tbody tr[data-id="${id}"]`);
  if (!tr) return;
  const r = state.rows.find(x => x.id === id);
  if (!r) return;
  // Generar el HTML nuevo de la fila con renderTable → reextraer la fila
  // Atajo: re-render full y luego añadir clase refreshed a esa fila
  // Más eficiente: regenerar solo el outerHTML
  const idx = state.rows.findIndex(x => x.id === id);
  if (idx < 0) return;
  // Hack: trigger renderTable para una sola fila — pero podemos reutilizar el
  // lock + grade + iconos manualmente. Por simplicidad: hacemos renderTable()
  // ÚNICAMENTE para la fila actualizada, sin tocar las demás.
  _renderSingleRow(tr, r);
  tr.classList.remove('row-refreshing');
  tr.classList.add('row-refreshed');
  setTimeout(() => tr.classList.remove('row-refreshed'), 1200);
}

function _renderSingleRow(tr, r) {
  // Replicamos la lógica mínima de renderTable para 1 fila
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
  const hasCards = (r.cards_count || 0) > 0;
  const hasNotes = (r.notes_count || 0) > 0;
  let iconsHtml = '';
  if (hasCards) iconsHtml += `<button class="row-ic ic-cards" data-id="${r.id}" data-email="${esc(r.email)}" title="${r.cards_count} tarjeta${r.cards_count>1?'s':''}">💳<sup>${r.cards_count}</sup></button>`;
  if (hasNotes) iconsHtml += `<button class="row-ic ic-notes" data-id="${r.id}" data-email="${esc(r.email)}" title="${r.notes_count} nota${r.notes_count>1?'s':''}">📝<sup>${r.notes_count}</sup></button>`;
  iconsHtml += `<button class="row-ic ic-add" data-id="${r.id}" data-email="${esc(r.email)}" title="Añadir nota rápida">+</button>`;
  const lockChip = r.locked_by
    ? `<span class="lock-chip op-${esc(opCol)} ${until?.expired ? 'expired' : ''}" title="Lockeada por ${esc(r.locked_by)}">🔒 ${esc(r.locked_by)}${until && !until.expired ? ` <span class="lock-chip-time dim">${until.text}</span>` : ''}</span>`
    : '';
  tr.className = `r-grade-${g} ${lockedCls} ${selCls} ${opClass} ${trasClass}`.trim();
  if (state.view === 'simple') {
    tr.innerHTML = `
      <td class="grade-bar-cell"></td>
      <td class="sel-cell"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
      <td class="num"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span></td>
      <td class="combo"><b data-id="${r.id}" data-combo="${esc(combo)}">${esc(combo)}</b>${lockChip}</td>
      <td class="dep">${dep}</td>
      <td class="row-icons">${iconsHtml}</td>`;
  } else {
    tr.innerHTML = `
      <td class="grade-bar-cell"></td>
      <td class="sel-cell"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
      <td class="num"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span></td>
      <td class="combo"><b data-id="${r.id}" data-combo="${esc(combo)}">${esc(combo)}</b></td>
      <td class="dep">${dep}</td>
      <td class="dep dim">${fmtAgo(r.last_checked_at)}</td>
      <td class="num">${r.check_count || 0}</td>
      <td class="row-icons">${iconsHtml}</td>`;
  }
}

function _markRowFail(id, reason) {
  const tr = document.querySelector(`#accTable tbody tr[data-id="${id}"]`);
  if (!tr) return;
  tr.classList.remove('row-refreshing');
  tr.classList.add('row-refresh-fail');
  if (reason) tr.title = `Falló: ${reason}`;
  setTimeout(() => tr.classList.remove('row-refresh-fail'), 2500);
}
function _markRowSkip(id, reason) {
  const tr = document.querySelector(`#accTable tbody tr[data-id="${id}"]`);
  if (!tr) return;
  tr.classList.remove('row-refreshing');
  tr.classList.add('row-refresh-skip');
  if (reason) tr.title = `Saltada: ${reason}`;
  setTimeout(() => tr.classList.remove('row-refresh-skip'), 1500);
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
  const isSuper = state.user?.role === 'superadmin';
  const defaultView = isSuper ? state.view : 'simple';
  return state.status === 'LIVE'
      && state.grade === ''
      && (state.view === defaultView)
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
$('#poolTable')?.addEventListener('click', e => {
  const btn = e.target.closest('.pool-hide-btn');
  if (btn) { e.stopPropagation(); removeFromPool(parseInt(btn.dataset.id)); return; }
  const combo = e.target.closest('td.combo b');
  if (combo?.dataset.combo) {
    e.stopPropagation();
    navigator.clipboard.writeText(combo.dataset.combo).then(() => toast(`✓ ${combo.dataset.combo}`, 'success'));
  }
});

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

// Ctrl+K → focus search
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    $('#searchInput').focus();
    $('#searchInput').select();
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
      if (key === 'view') return renderTable();
      await reload();
    });
  });
});

// Activity table — clicks interactivos
$('#actTable').addEventListener('click', e => {
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
  // Iconos de fila — interceptan ANTES de que se abra el modal
  const ic = e.target.closest('.row-ic');
  if (ic) {
    e.stopPropagation();
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

// ─── Modal de detalle (fijo con scroll interno solo en secciones largas) ───
async function openDetailModal(id) {
  const overlay = $('#detModalOverlay');
  const body = $('#detModalBody');
  const title = $('#detModalTitle');
  body.innerHTML = '<div class="detail-loading"><span class="dep-spinner"></span> Cargando…</div>';
  title.textContent = 'Detalle de cuenta';
  overlay.classList.remove('hidden');
  try {
    const r = await fetch(`/api/accounts/${id}/details`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    // Combo en el title — clickable para copiar
    const combo = `${data.email}:${data.password || ''}`;
    title.innerHTML = `<span class="d-copy mono" data-copy="${esc(combo)}" title="Click para copiar combo">${esc(combo)}</span>`;
    body.innerHTML = renderDetail(data);
    // Hints contextuales solo para admin (no invasivos, dismissables)
    showAdminHints();
    // Aura del modal según grade
    const modal = $('#detModal');
    modal.classList.remove('grade-A', 'grade-B', 'grade-C', 'grade-D', 'grade-U');
    const gc = gradeClass(data.grade);
    modal.classList.add(`grade-${gc}`);
    // Letra grande del grade en el header (premium feel)
    const isSA = state.user?.role === 'superadmin';
    const headerExtra = $('#detModalGradeBadge');
    if (headerExtra) {
      if (isSA && data.grade) {
        headerExtra.textContent = data.grade;
        headerExtra.className = `det-grade-badge grade-${gc}`;
        headerExtra.style.display = '';
      } else {
        headerExtra.style.display = 'none';
      }
    }
  } catch (e) {
    body.innerHTML = `<div class="detail-error">Error: ${esc(e.message)}</div>`;
  }
}
function closeDetailModal() {
  $('#detModalOverlay').classList.add('hidden');
  hideAdminHints();
}

function renderDetail(d) {
  const isSA = state.user?.role === 'superadmin';
  const naField = v => (!v || v === 'N/A') ? '<span class="dim">—</span>' : esc(v);
  const lockHtml = d.locked_by
    ? (() => {
        const u = fmtUntil(d.locked_until);
        return `por ${esc(d.locked_by)}${u ? ` <span class="${u.expired ? 'lock-expired' : (u.urgent ? 'lock-urgent' : 'dim')}">· ${u.text}</span>` : ''}`;
      })()
    : '<span class="dim">libre</span>';

  // SA ve todo, users ven solo datos de la persona + saldo + lock + último depósito
  const adminRows = isSA ? `
        <li><span>Grade</span><b>${esc(d.grade) || '?'}${d.grade_score != null ? ` <span class="dim mono">(${d.grade_score})</span>` : ''}</b></li>
        <li><span>Status</span><b>${esc(d.status)}</b></li>
        <li><span>Últ. check</span><b>${fmtAgo(d.last_checked_at)}</b></li>
        <li><span>Total checks</span><b>${d.check_count || 0}</b></li>
  ` : '';

  // Birthdate sin hora
  const bdate = d.birthdate ? String(d.birthdate).split('T')[0].split(' ')[0] : null;
  // CURP — usa el de BD si existe y es válido, si no calcula
  const curpStored = (d.curp && d.curp !== 'N/A') ? d.curp : null;
  const curpCalc = !curpStored ? computeCurp(d.fullname, bdate, d.address) : null;
  const curpShown = curpStored || curpCalc || '';
  // Botón validar gob.mx (solo si tenemos los datos mínimos)
  const canValidate = !!(d.fullname && bdate);
  const curpValidateBtn = canValidate
    ? `<button class="curp-validate-btn" data-acc-id="${d.id}" title="Copia los datos al portapapeles y abre gob.mx para validar el CURP en humano (Akamai bloquea bots)">🔍 Validar</button>`
    : '';
  const curpHtml = curpStored
    ? `<div class="curp-cell"><b class="mono d-copy" data-copy="${esc(curpStored)}" title="Click para copiar">${esc(curpStored)}</b><span class="dim mono" style="font-size:9px">✓ guardado</span>${curpValidateBtn}</div>`
    : curpCalc
      ? `<div class="curp-cell"><b class="mono d-copy" data-copy="${esc(curpCalc)}" title="Estimado — click para copiar">${esc(curpCalc)}</b><span class="dim mono" style="font-size:9px">est</span>${curpValidateBtn}</div>`
      : `<div class="curp-cell"><b><span class="dim">—</span></b>${curpValidateBtn}</div>`;

  const personal = `
    <div class="d-section">
      <h4>📋 Datos personales</h4>
      <ul class="d-list">
        <li><span>Nombre</span><b>${naField(d.fullname)}</b></li>
        <li><span>Fecha nac.</span><b>${bdate ? esc(bdate) : '<span class="dim">—</span>'}</b></li>
        <li class="d-list-multiline"><span>Domicilio</span><b>${naField(d.address)}</b></li>
        <li><span>Teléfono</span><b>${naField(d.phone)}</b></li>
        <li><span>CURP</span>${curpHtml}</li>
        <li><span>KYC</span><b>${d.kyc_verified ? '<span style="color:var(--accent)">✓ verificado</span>' : '<span class="dim">no</span>'}</b></li>
        <li><span>Saldo</span><b>${fmtMoney(d.balance_total)}${d.balance_real != null && d.balance_real !== d.balance_total ? ` <span class="dim mono">(real ${fmtMoney(d.balance_real)})</span>` : ''}</b></li>
        <li><span>Lock</span><b>${lockHtml}</b></li>
        <li><span>Últ. dep.</span><b>${d.last_deposit_amount ? fmtMoney(d.last_deposit_amount) + ' · ' + fmtAgo(d.last_deposit_date) : '<span class="dim">—</span>'}</b></li>
        ${adminRows}
      </ul>
    </div>`;

  const cards = (d.cards && d.cards.length > 0)
    ? `<div class="d-section">
        <h4>💳 Tarjetas guardadas <span class="d-count">${d.cards.length}</span></h4>
        <div class="d-cards">
          ${d.cards.map(c => {
            const num = c.card_number || '';
            const exp = (c.card_expiry || '').replace('/', '');
            const cvv = c.card_cvv || '';
            const pipe = `${num}|${exp}|${cvv}`;
            const stats = `${c.total_approved || 0}/${c.total_deposits || 0} ok`;
            return `<div class="d-card" data-copy="${esc(pipe)}" title="Click para copiar pipe">
              <div class="d-card-pipe">${esc(pipe)}</div>
              <div class="d-card-meta">
                <span class="d-card-stats">${stats}</span>
                <span class="d-card-status ${esc((c.status || '').toLowerCase())}">${esc(c.status || '')}</span>
              </div>
            </div>`;
          }).join('')}
        </div>
      </div>`
    : `<div class="d-section"><h4>💳 Tarjetas</h4><div class="d-empty">Sin tarjetas guardadas.</div></div>`;

  // BetMexico API: txn_type 1=depósito, 2=retiro. Gateway 1=tarjeta, 2=SPEI, 3=OXXO.
  // Iconos sutiles (monocromos) — el color va por estado, no por tipo
  const _txnType = t => ({1: '↓ Depósito', 2: '↑ Retiro'})[t] ?? '· Otro';
  const _txnGateway = g => ({1: 'Tarjeta', 2: 'SPEI', 3: 'OXXO'})[g] || (g ? `gw${g}` : '—');
  const _txnStatus = s => {
    const m = {6: 'Exitoso', 0: 'Pendiente', '-4': 'Fallido', 5: 'Error'};
    return m[s] ?? m[String(s)] ?? `cod ${s}`;
  };
  const _txnStatusCls = s => ({6: 'ok', 0: 'pending', '-4': 'fail', 5: 'fail'})[s]
    ?? ({6: 'ok', 0: 'pending', '-4': 'fail', 5: 'fail'})[String(s)] ?? '';
  const txns = (d.transactions && d.transactions.length > 0)
    ? `<div class="d-section">
        <h4>📊 Transacciones <span class="d-count">${d.transactions.length}</span></h4>
        <div class="d-txn-scroll">
          <table class="d-txn-table">
            <thead><tr><th>Cuándo</th><th>Tipo</th><th>Método</th><th class="num">Monto</th><th>Estado</th></tr></thead>
            <tbody>
              ${d.transactions.map(t => {
                const stCls = _txnStatusCls(t.status);
                const isFail = stCls === 'fail';
                const isCard = t.txn_type === 1 && t.gateway === 1;
                // Si fail: toda la fila en rojo (monto + método incluidos)
                // Si ok/pendiente: tarjeta acentuada (verde), SPEI/OXXO tenue
                const rowCls = isFail ? 'txn-row-fail' : (isCard ? '' : 'txn-row-other');
                const gwCls = isFail ? '' : (isCard ? 'txn-gw-card' : 'dim');
                return `<tr class="${rowCls}">
                  <td class="dim mono" title="${esc(t.txn_date || '')}">${fmtAbsYear(t.txn_date)}</td>
                  <td class="txn-type">${_txnType(t.txn_type)}</td>
                  <td class="txn-gw ${gwCls}">${esc(_txnGateway(t.gateway))}</td>
                  <td class="num">${fmtMoney(t.amount)}</td>
                  <td><span class="txn-st txn-st-${stCls}">${esc(_txnStatus(t.status))}</span></td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>`
    : `<div class="d-section"><h4>📊 Transacciones</h4><div class="d-empty">Sin transacciones registradas.</div></div>`;

  // Intentos hechos desde este dashboard (con tarjeta usada — sin enmascarar)
  const attempts = (d.deposit_attempts && d.deposit_attempts.length > 0)
    ? `<div class="d-section">
        <h4>🎯 Intentos del dashboard <span class="d-count">${d.deposit_attempts.length}</span></h4>
        <div class="d-txn-scroll">
          <table class="d-txn-table">
            <thead><tr><th>Cuándo</th><th>Monto</th><th>Tarjeta</th><th>Estado</th><th>Razón</th></tr></thead>
            <tbody>
              ${d.deposit_attempts.map(a => {
                const ok = a.status === 'approved';
                const rowCls = ok ? '' : 'txn-row-fail';
                const card = a.card_pipe
                  ? `<b class="mono d-copy" data-copy="${esc(a.card_pipe)}" title="Click para copiar">${esc(a.card_pipe)}</b>`
                  : '<span class="dim">—</span>';
                return `<tr class="${rowCls}">
                  <td class="dim mono" title="${esc(a.created_at || '')}">${fmtAbsYear(a.created_at)}</td>
                  <td class="num">${fmtMoney(a.amount)}</td>
                  <td class="combo">${card}</td>
                  <td><span class="txn-st txn-st-${ok ? 'ok' : 'fail'}">${esc(a.status || '')}</span></td>
                  <td class="dim">${esc(a.rejection_reason || '')}</td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>`
    : '';

  // Solo SA puede borrar notas (otros usuarios no, son immutables una vez enviadas)
  const renderNoteLi = n => `<li data-note-id="${n.id}">
    <div class="d-note-head">
      <span class="d-note-by">${esc(n.created_by_name || '—')}</span>
      <span class="d-note-when dim mono" title="${esc(n.created_at || '')}">${fmtAbs(n.created_at)} · ${fmtAgo(n.created_at)}</span>
      ${isSA ? `<button class="d-note-del" data-note-id="${n.id}" title="Borrar (SA)">✕</button>` : ''}
    </div>
    <div class="d-note-body">${esc(n.note_text)}</div>
  </li>`;

  const notesList = (d.notes && d.notes.length > 0)
    ? `<ul class="d-notes" id="dNotesList">${d.notes.map(renderNoteLi).join('')}</ul>`
    : '<ul class="d-notes" id="dNotesList"></ul><div class="d-empty" id="dNotesEmpty">Sin notas todavía.</div>';

  const notes = `<div class="d-section d-section-notes">
      <h4>📝 Notas <span class="d-count" id="dNotesCount">${(d.notes || []).length}</span></h4>
      <form class="d-note-form" data-acc-id="${d.id}">
        <textarea class="d-note-input" placeholder="Nueva nota (visible solo para ti${isSA ? '' : ' y SA'})…" maxlength="2000" rows="2"></textarea>
        <button type="submit" class="d-note-submit">Guardar</button>
      </form>
      ${notesList}
    </div>`;

  // Botones al footer: Seleccionar (toggle multi-selección, no cierra modal) + Depositar
  const isSelected = selectedIds.has(d.id);
  const selBtnLabel = isSelected ? '✓ Seleccionada · click para quitar' : '+ Seleccionar (multi)';
  const selBtnClass = isSelected ? 'd-select-btn is-selected' : 'd-select-btn';
  const depositFooter = `<div class="d-deposit-footer">
    <button class="${selBtnClass}" data-acc-id="${d.id}" title="Marca/desmarca esta cuenta para depósito multi (Matchmaker). NO cierra este panel.">${selBtnLabel}</button>
    <button class="d-deposit-btn" data-acc-id="${d.id}" title="Abrir modal de depósito en esta cuenta">💳 Depositar</button>
  </div>`;

  return `<div class="d-grid">${personal}${cards}${txns}${attempts}${notes}</div>${depositFooter}`;
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

// Click global: copia [data-copy] o [data-combo] desde cualquier lado del DOM
document.body.addEventListener('click', e => {
  const t = e.target.closest('[data-copy], [data-combo]');
  if (!t) return;
  // No interceptar checkboxes / botones internos del row
  if (e.target.closest('input, button:not(.d-copy)') && !t.classList.contains('d-copy')) return;
  const txt = t.dataset.copy || t.dataset.combo;
  if (!txt) return;
  e.stopPropagation();
  navigator.clipboard.writeText(txt)
    .then(() => toast(`✓ ${txt.slice(0, 60)}`, 'success'))
    .catch(err => toast(`Error: ${err.message}`, 'error'));
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
  $$('#depModeSeg .dep-mode-btn').forEach(b => b.classList.toggle('on', b.dataset.mode === mode));

  const isSingle = mode === 'single';
  const isMulti  = mode === 'multi';
  const isSched  = mode === 'schedule';

  // visibilidades
  $('#depTargetBlock').classList.toggle('hidden', isMulti);
  $('#depMultiAccts').classList.toggle('hidden', !isMulti);
  $('#depCardSection').classList.toggle('hidden', isMulti);
  $('#depMultiCards').classList.toggle('hidden', !isMulti);
  $('#depScheduleBlock').classList.toggle('hidden', !isSched);

  // título
  $('#depModalTitle').textContent = isSingle ? 'Depositar' : isMulti ? 'Multicuenta (Matchmaker)' : 'Programado';
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
  if (opts.ids && opts.ids.length > 0) {
    _depAccountIds = [...opts.ids].slice(0, 5);
  } else if (accountId) {
    _depAccountIds = [accountId];
  } else if (selectedIds.size > 0) {
    _depAccountIds = [...selectedIds].slice(0, 5);
  } else {
    toast('Sin cuenta seleccionada', 'error');
    return;
  }

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
  $('#depModalOverlay').classList.remove('hidden');

  // Mostrar/ocultar botones de modo según contexto
  const multiBtn = document.querySelector('#depModeSeg [data-mode="multi"]');
  if (multiBtn) multiBtn.style.display = (_depAccountIds.length >= 2) ? '' : 'none';

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
  if (_depBusy) { toast('Detén la misión primero', 'error'); return; }
  $('#depModalOverlay').classList.add('hidden');
  $('#depModal').classList.remove('dep-modal-wide');
  $('#depMatchView').classList.add('hidden');
  $('#depCap').style.display = 'none';
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

  // SINGLE
  _depBusy = true;
  $('#depExec').disabled = true;
  $('#depExec').textContent = 'Procesando…';
  const res = $('#depResult');
  res.className = 'dep-result loading';
  res.classList.remove('hidden');
  res.innerHTML = `<span class="dep-spinner"></span> Login → BeginDeposit → makePayment…`;

  try {
    const r = await fetch('/api/deposits/execute', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ account_id: _depAccountIds[0], card_pipe: pipe, amount }),
    });
    const data = await r.json();
    if (!r.ok) {
      res.className = 'dep-result error';
      res.innerHTML = `<b>✗ ${esc(data.detail || 'Error')}</b>`;
    } else if (data.success) {
      res.className = 'dep-result success';
      res.innerHTML = `<b>✓ Depósito aprobado</b> — $${amount.toFixed(2)} <span class="dim mono"> · ${data.duration_ms}ms</span>`;
      pushNotif({ icon: '💳', msg: `Depósito $${amount.toFixed(2)} aprobado` });
      reload();
    } else {
      res.className = 'dep-result error';
      res.innerHTML = `<b>✗ Rechazado</b><br><span class="mono">${esc(data.error || data.result_code || 'Sin detalle')}</span>`;
      pushNotif({ icon: '⚠️', msg: `Depósito rechazado: ${data.error || data.result_code}` });
    }
    $('#depExec').textContent = '🔁 Otro intento';
  } catch (e) {
    res.className = 'dep-result error';
    res.innerHTML = `<b>✗ Error de red</b><br><span class="mono">${esc(e.message)}</span>`;
    $('#depExec').textContent = '🔁 Reintentar';
  } finally {
    _depBusy = false;
    $('#depExec').disabled = false;
  }
}

// ── SCHEDULE: 1 tarjeta, 1 cuenta, N reps cada 1 min ──
async function executeScheduled(pipe, amount) {
  _depBusy = true;
  $('#depExec').disabled = true;
  $('#depExec').textContent = 'Programando…';
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
    const res = $('#depResult');
    res.className = 'dep-result success';
    res.classList.remove('hidden');
    res.innerHTML = `<b>⏰ Misión programada</b> — ${_depReps} repeticiones cada 1min<br><span class="dim mono">id: ${esc(data.sched_id)}</span><br><span class="dim">Sigue el progreso en el feed de Actividad. Si una rep falla, la misión se aborta automáticamente.</span>`;
    pushNotif({ icon: '⏰', msg: `Misión ${data.sched_id}: ${_depReps} reps en ${data.email}` });
    $('#depExec').textContent = '✓ Programada — ciérralo cuando quieras';
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
  // Tarjetas
  const cardsHtml = [..._mm.cards.entries()].map(([tail, c]) => {
    const cls = `mm-card mm-${c.status}`;
    const fails = c.fails ? `<span class="mm-fails">${c.fails}/2</span>` : '';
    const ic = c.status === 'matched' ? '🎯'
             : c.status === 'busy'    ? '<span class="dep-spinner"></span>'
             : c.status === 'retired' ? '💀'
             : '';
    const reason = (c.status === 'retired' && c.lastCode)
      ? `<span class="mm-reason">${esc(_mmLabel(c.lastCode))}</span>` : '';
    return `<div class="${cls}">
      <span class="mm-tail mono">···${tail}</span>
      ${fails}
      ${reason}
      <span class="mm-ic">${ic}</span>
    </div>`;
  }).join('');
  $('#mmCards').innerHTML = cardsHtml;

  // Cuentas
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
    return `<div class="${cls}">
      <span class="mm-email">${esc(email)}</span>
      ${matched}
      ${fails}
      ${reason}
      <span class="mm-ic">${ic}</span>
    </div>`;
  }).join('');
  $('#mmAccounts').innerHTML = accsHtml;

  // Stats
  $('#mmStMatches').textContent = _mm.matches;
  $('#mmStAttempts').textContent = _mm.attempts;
  $('#mmStAmount').textContent = _mm.amount;
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
  if (_depAccountIds.length < 1) { toast('Selecciona al menos 1 cuenta', 'error'); return; }
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
  // El modal se ensancha
  $('#depModal').classList.add('dep-modal-wide');

  _mmReset(_depAccountIds, cards, amount);
  _mmRender();
  $('#depFeed').innerHTML = '';

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
        try { handleMmEvent(JSON.parse(line.slice(6))); } catch {}
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
      const card = _mm.cards.get(ev.tail.replace('···', ''));
      const acc = _mm.accounts.get(ev.email);
      if (card) card.status = 'busy';
      if (acc) acc.status = 'busy';
      _mmRender();
      _mmFeedAdd('mm-trying',
        `<span class="dep-spinner"></span> <b class="mono">${esc(ev.tail)}</b> → <span>${esc(ev.email)}</span>`);
      break;
    }

    case 'match': {
      _mm.matches++;
      const tail = ev.tail.replace('···', '');
      const card = _mm.cards.get(tail);
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.status = 'matched'; card.matchedEmail = ev.email; }
      if (acc) { acc.status = 'done'; acc.matchedTail = tail; acc.matchedPipe = ev.pipe; }
      _mmRender();
      _mmFeedAdd('mm-match',
        `✓ <b class="mono">${esc(ev.tail)}</b> ↔ <b>${esc(ev.email)}</b> · $${ev.amount.toFixed(2)} <span class="dim mono">${ev.duration_ms}ms</span>`);
      pushNotif({ icon: '💳', msg: `Match: ${ev.tail} ↔ ${ev.email}` });
      break;
    }
    case 'done': {
      _mmFeedAdd('mm-done',
        `<b>Listo</b> · ${ev.matches} match${ev.matches !== 1 ? 'es' : ''} · ${ev.attempts} intentos${ev.pending ? ` · ${ev.pending} sin emparejar` : ''}`);
      // Limpia estados busy → idle al final
      for (const c of _mm.cards.values()) if (c.status === 'busy') c.status = 'idle';
      for (const a of _mm.accounts.values()) if (a.status === 'busy' || a.status === 'cooldown') a.status = a.fails >= 2 ? 'dead' : 'idle';
      _mmRender();
      // Si hubo matches, ofrecer programar los siguientes depósitos
      if (_mm.matches > 0) _renderPostMatchOffer();
      break;
    }

    case 'rejected': {
      const tail = ev.tail.replace('···', '');
      const card = _mm.cards.get(tail);
      const acc = _mm.accounts.get(ev.email);
      if (card) { card.fails = ev.card_fails ?? card.fails; card.status = 'idle'; card.lastCode = ev.code; }
      if (acc)  {
        acc.fails = ev.acct_fails ?? acc.fails;
        acc.lastCode = ev.code;
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
      if (acc) { acc.status = 'dead'; acc.deadCode = ev.code; acc.lastCode = ev.code; }
      _mmRender();
      const persisted = ev.persisted ? ' <span class="mm-persisted">guardada</span>' : '';
      _mmFeedAdd('mm-dead',
        `💀 <b>${esc(ev.email)}</b> · <b>${esc(_mmLabel(ev.code))}</b> <span class="dim mono">${esc(ev.code)}</span>${persisted}`);
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

// ── Wire-up ──
$('#depModalClose').addEventListener('click', closeDepositModal);
$('#depModalOverlay').addEventListener('click', e => {
  if (e.target.id === 'depModalOverlay') closeDepositModal();
});
$('#depModeSeg').addEventListener('click', e => {
  const btn = e.target.closest('.dep-mode-btn');
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
  if (e.key === 'Escape' && !$('#depModalOverlay').classList.contains('hidden')) closeDepositModal();
  if (e.key === 'Enter' && !$('#depModalOverlay').classList.contains('hidden') && document.activeElement?.id === 'depCardPipe') {
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

$('#bellBtn').addEventListener('click', () => {
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

$$('.ico-btn[title="Salir"], .power').forEach(btn => {
  btn.addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  });
});

// ─── init ───
(async () => {
  await loadMe();
  tickGreeting();
  setInterval(tickGreeting, 30_000);
  tickFrase();
  setInterval(tickFrase, 9_000);
  await reload();
  refreshKpis();
  setInterval(refreshKpis, 30_000);
  loadHealth(false);
  connectSSE();
})();

window.addEventListener('beforeunload', () => {
  if (_evtSrc) _evtSrc.close();
});
