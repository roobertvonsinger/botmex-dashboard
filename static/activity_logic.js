(function (root) {
  function _minute(ts) { return String(ts || '').slice(0, 16); }
  function dedupeActivity(events) {
    const seen = new Map();
    const out = [];
    for (const ev of events) {
      const key = ev.sched_id != null
        ? `s:${ev.sched_id}:${ev.iter}`
        : `${ev.kind}:${ev.target || ev.email || ''}:${ev.amount ?? ''}:${_minute(ev.ts)}`;
      if (seen.has(key)) continue;
      seen.set(key, true);
      out.push(ev);
    }
    return out;
  }
  function _who(ev, viewerIsSA) { return viewerIsSA ? (ev.who || '—') : 'Tú'; }
  function _email(t) { return String(t || '').split(':')[0]; }
  function formatActivityCopy(ev, viewerIsSA) {
    const who = _who(ev, viewerIsSA);
    const email = _email(ev.target || ev.email);
    const amt = ev.amount != null ? `$${ev.amount}` : '';
    if (ev.kind === 'deposit') {
      if (ev.status === 'approved') return { icon: '✅', cls: 'ok', text: `${who} depositó ${amt} a ${email} — aprobado` };
      if (ev.code === '3DS_REQUIRED' || ev.reason === '3DS' || ev.status === 'threeds') return { icon: '🔐', cls: 'neutral', text: `${who} ${amt} a ${email} — pidió verificación 3DS` };
      // SOLO status 'rejected' es rechazo REAL de banco (bug 2026-07-06): rate-limit,
      // cuenta muerta, login/gateway/timeout NO se atribuyen al banco.
      if (ev.status === 'rejected') return { icon: '❌', cls: 'fail', text: `${who} intentó ${amt} a ${email} — rechazado (banco)` };
      const motivo = ev.reason || ev.code || '';
      return { icon: '⚠️', cls: 'warn', text: `${who} ${amt} a ${email} — no aplicado${motivo ? ` (${motivo})` : ''}` };
    }
    if (ev.kind === 'withdrawal') {
      if (ev.status === 'successful' || ev.status === 'completed') return { icon: '✅', cls: 'ok', text: `${who} retiró ${amt} de ${email}` };
      if (ev.status === 'failed' || ev.status === 'rejected') return { icon: '❌', cls: 'fail', text: `${who} falló retiro ${amt} de ${email}` };
      return { icon: '🏧', cls: 'neutral', text: `${who} inició retiro ${amt} de ${email}` };
    }
    if (ev.kind === 'lock') return { icon: '🔒', cls: 'neutral', text: `${who} tomó ${email}` };
    if (ev.kind === 'unlock' || ev.kind === 'unlock_auto') return { icon: '✔️', cls: 'neutral', text: `${email} liberada` };
    if (ev.kind === 'account_cooling') return { icon: '⏸', cls: 'warn', text: `${email} en pausa ~${ev.minutes || ''}m (muchos intentos)` };
    if (ev.kind === 'mark') return { icon: '📌', cls: 'neutral', text: `${who} fijó ${email}` };
    if (ev.kind === 'pool_move') return { icon: ev.publish ? '↘' : '↗', cls: 'neutral', text: `${who} ${ev.publish ? 'expuso' : 'retiró'} ${ev.count || ''} cuenta(s) ${ev.publish ? 'al' : 'del'} pool` };
    if (ev.kind === 'critical_error') return { icon: '🚨', cls: 'fail', text: ev.msg || 'Problema de conexión' };
    return { icon: '·', cls: 'neutral', text: `${who} ${email}` };
  }
  const api = { dedupeActivity, formatActivityCopy };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ActivityLogic = api;
})(typeof window !== 'undefined' ? window : globalThis);
