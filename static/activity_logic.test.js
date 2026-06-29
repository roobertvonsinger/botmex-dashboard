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

if(fails){console.error(fails+' FALLOS');process.exit(1);} else {console.log('OK activity_logic');}
