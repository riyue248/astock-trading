async function loadSignals() {
    try {
        const resp = await fetch('/api/signals?limit=100');
        const data = await resp.json();
        document.getElementById('signal-count').textContent = '共 ' + (data.signals||[]).length + ' 条';
        const tbody = document.querySelector('#signals-table tbody');
        tbody.innerHTML = (data.signals||[]).map(s => {
            const actionCls = s.final_action === 'buy' ? 'text-up fw-bold' : s.final_action === 'sell' ? 'text-down fw-bold' : '';
            return `<tr><td>${(s.scanned_at||'').substr(11,8)}</td><td>${s.symbol} ${s.name}</td>
                <td>${(s.trend_score||0).toFixed(2)}<br><small>${s.trend_action||''}</small></td>
                <td>${(s.momentum_score||0).toFixed(2)}<br><small>${s.momentum_action||''}</small></td>
                <td>${(s.reversal_score||0).toFixed(2)}<br><small>${s.reversal_action||''}</small></td>
                <td class="fw-bold">${(s.composite_score||0).toFixed(3)}</td>
                <td class="${actionCls}">${s.final_action}</td>
                <td><small>${s.decision_reason||''}</small></td></tr>`;
        }).join('');
    } catch(e) { console.error(e); }
}
document.addEventListener('DOMContentLoaded', loadSignals);
setInterval(loadSignals, 15000);
