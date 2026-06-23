async function loadTrades() {
    try {
        const [tResp, sResp] = await Promise.all([fetch('/api/trades?limit=100'), fetch('/api/trades/stats')]);
        const trades = await tResp.json();
        const stats = await sResp.json();
        document.getElementById('trade-stats').innerHTML = `
            <div class="row g-2">
                <div class="col-6 col-md"><div class="card text-center py-1"><small class="text-muted">总交易</small><strong>${stats.total_trades}</strong></div></div>
                <div class="col-6 col-md"><div class="card text-center py-1"><small class="text-muted">持仓中</small><strong>${stats.open_positions||0}</strong></div></div>
                <div class="col-6 col-md"><div class="card text-center py-1"><small class="text-muted">已平仓</small><strong>${stats.closed_trades||0}</strong></div></div>
                <div class="col-6 col-md"><div class="card text-center py-1"><small class="text-muted">胜率</small><strong>${stats.closed_trades?((stats.win_rate*100).toFixed(1)+'%'):'--'}</strong></div></div>
                <div class="col-6 col-md"><div class="card text-center py-1"><small class="text-muted">已实现盈亏</small><strong class="${stats.total_pnl>0?'text-up':stats.total_pnl<0?'text-down':''}">${stats.total_pnl!=null?(stats.total_pnl>0?'+':'')+'¥'+Math.abs(stats.total_pnl||0).toFixed(0):'--'}</strong></div></div>
            </div>`;
        const tbody = document.querySelector('#trades-table tbody');
        tbody.innerHTML = (trades.trades||[]).map(t => {
            const pnlCls = (t.profit_pct||0) > 0 ? 'text-up' : (t.profit_pct||0) < 0 ? 'text-down' : '';
            return `<tr><td>${t.id}</td><td>${(t.created_at||'').substr(0,19)}</td><td>${t.symbol}</td><td>${t.name}</td>
                <td>${t.side==='buy'?'🟢买入':'🔴卖出'}</td><td>${t.price.toFixed(2)}</td><td>${t.quantity}</td><td>${formatMoney(t.amount)}</td>
                <td class="${pnlCls}">${t.profit_amount!=null?(t.profit_amount>0?'+':'')+t.profit_amount.toFixed(2)+' ('+(t.profit_pct*100).toFixed(2)+'%)':'--'}</td>
                <td><small>${t.close_reason||''}</small></td><td><small>${t.strategies||''}</small></td></tr>`;
        }).join('');
    } catch(e) { console.error(e); }
}
document.addEventListener('DOMContentLoaded', loadTrades);
