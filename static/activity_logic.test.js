// static/activity_logic.test.js
const A = require('./activity_logic.js');
let fails = 0;
function eq(got, exp, msg){ if(JSON.stringify(got)!==JSON.stringify(exp)){console.error('FAIL',msg,'got',got,'exp',exp);fails++;} }

// dedupe scheduled doble-evento -> 1
const deduped = A.dedupeActivity([
  {kind:'scheduled', sched_id:'s1', iter:1, ts:'2026-06-29T10:00:00'},
  {kind:'scheduled_aborted', sched_id:'s1', iter:1, ts:'2026-06-29T10:00:01'},
]);
eq(deduped.length, 1, 'scheduled doble-evento colapsa a 1');

// copy humano deposito aprobado
const c1 = A.formatActivityCopy({kind:'deposit', status:'approved', who:'Lau', target:'a@x.com:p', amount:300}, true);
eq(c1.icon, '💰', 'icono deposito ok');
eq(c1.cls, 'ok', 'clase ok');
if(!/Lau/.test(c1.text) || !/300/.test(c1.text) || !/aprobad/i.test(c1.text)){console.error('FAIL copy deposito', c1.text);fails++;}

// no-SA ve 'tú' en vez de su nombre
const c2 = A.formatActivityCopy({kind:'lock', who:'Lau', target:'a@x.com'}, false);
if(!/tú|Tú/.test(c2.text)){console.error('FAIL no-SA debe decir tú', c2.text);fails++;}

// BUG 2026-07-06: rate-limit (429) NO es rechazo del banco
const c3 = A.formatActivityCopy({kind:'deposit', status:'rate_limited', who:'Lau', target:'a@x.com:p', amount:100, reason:'BetMexico rate-limit (429)'}, true);
if(/banco/i.test(c3.text)){console.error('FAIL rate-limit NO debe decir banco', c3.text);fails++;}
eq(c3.cls, 'neutral', 'rate-limit cls neutral (no fail)');

// rechazo REAL de banco (status rejected) SÍ dice banco, cls fail
const c4 = A.formatActivityCopy({kind:'deposit', status:'rejected', who:'Lau', target:'a@x.com:p', amount:100}, true);
eq(c4.cls, 'fail', 'banco real cls fail');
if(!/banco/i.test(c4.text)){console.error('FAIL banco real debe decir banco', c4.text);fails++;}

// cuenta muerta (autoexclusión) tampoco es banco
const c5 = A.formatActivityCopy({kind:'deposit', status:'account_dead', who:'Lau', target:'a@x.com:p', amount:100, reason:'Cuenta autoexcluida'}, true);
if(/banco/i.test(c5.text)){console.error('FAIL account_dead NO debe decir banco', c5.text);fails++;}

if(fails){console.error(fails+' FALLOS');process.exit(1);} else {console.log('OK activity_logic');}
