document.addEventListener('DOMContentLoaded', () => {
  const grid = document.getElementById('accountsGrid');
  const logoutBtn = document.getElementById('logoutBtn');

  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
      } catch (e) {}
      window.location.href = '/login';
    });
  }

  async function loadMyAccounts() {
    try {
      const res = await fetch('/api/operator/my-accounts');
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      const data = await res.json();
      if (!data.ok || !data.accounts || data.accounts.length === 0) {
        grid.innerHTML = '<div class="empty-msg">No tienes cuentas con depósitos aprobados registrados aún.</div>';
        return;
      }

      grid.innerHTML = data.accounts.map(acc => {
        const balReal = parseFloat(acc.balance_real || 0).toFixed(2);
        const balBonos = parseFloat(acc.balance_bonos || 0).toFixed(2);
        const lastDepAmt = parseFloat(acc.last_deposit_amount || 0).toFixed(2);
        const lastDepDate = acc.last_deposit_date ? new Date(acc.last_deposit_date).toLocaleString() : 'N/A';
        const grade = acc.grade || 'N/A';

        return `
          <div class="account-card">
            <div class="acc-email">${acc.email}</div>
            <div class="acc-balance">$${balReal} <span style="font-size:12px; font-weight:normal; color:#8b949e;">MXN</span></div>
            <div class="acc-meta">
              <div>• Bonos: $${balBonos} MXN</div>
              <div>• Último depósito: $${lastDepAmt} MXN (${lastDepDate})</div>
              <div>• Calificación: <b>${grade}</b></div>
            </div>
          </div>
        `;
      }).join('');
    } catch (err) {
      grid.innerHTML = `<div class="empty-msg" style="color:#f85149;">Error al cargar tus cuentas: ${err.message}</div>`;
    }
  }

  loadMyAccounts();
});
