// Dashboard: Portfolio + positions + signals live update
let portfolioData = null;

async function loadDashboard() {
    try {
        const [pResp, eResp, sResp] = await Promise.all([
            fetch('/api/portfolio'), fetch('/api/equity'), fetch('/api/performance')
        ]);
        const portfolio = await pResp.json();
        const equity = await eResp.json();
        const perf = await sResp.json();

        updateSummary(portfolio);
        updateEquityChart(equity.equity || []);
        updateWeights(perf.strategies || []);
        updatePositions(portfolio.positions || []);
        updateStatus(portfolio);
    } catch(e) { console.error(e); }
}

function updateSummary(p) {
    document.getElementById('s-equity').textContent = '¥' + (p.total_equity||0).toLocaleString();
    document.getElementById('s-cash').textContent = '¥' + (p.cash||0).toLocaleString();
    document.getElementById('s-mv').textContent = '¥' + (p.market_value||0).toLocaleString();
    const pnlEl = document.getElementById('s-pnl');
    const pnl = p.net_profit || 0;
    pnlEl.textContent = '¥' + (pnl>0?'+':'') + Math.abs(pnl).toLocaleString();
    pnlEl.className = pnl > 0 ? 'text-up' : pnl < 0 ? 'text-down' : '';
    const retEl = document.getElementById('s-return');
    const ret = p.total_return_pct || 0;
    retEl.textContent = (ret>0?'+':'') + ret.toFixed(2) + '%';
    retEl.className = ret > 0 ? 'text-up' : ret < 0 ? 'text-down' : '';
    document.getElementById('s-dd').textContent = (p.drawdown_pct||0).toFixed(2) + '%';
    document.getElementById('s-pos').textContent = (p.position_count||0) + '/' + (p.max_positions||3);
    if (p.halted) document.getElementById('status-dot').textContent += ' [暂停开仓]';
    portfolioData = p;
}

function updateEquityChart(data) {
    if (!data || data.length === 0) return;
    const dates = data.map(d => d.date);
    const values = data.map(d => d.total_equity);
    const trace = { type:'scatter', x:dates, y:values, name:'净值', line:{color:'#42a5f5',width:2}, fill:'tozeroy', fillcolor:'rgba(66,165,245,0.1)' };
    const layout = { paper_bgcolor:'#0f1b2d', plot_bgcolor:'#0f1b2d', font:{color:'#e0e0e0',size:10}, margin:{l:60,r:20,t:10,b:30}, xaxis:{gridcolor:'rgba(255,255,255,.05)'}, yaxis:{title:'净值',gridcolor:'rgba(255,255,255,.05)'} };
    Plotly.newPlot('equity-chart', [trace], layout, {responsive:true, displaylogo:false});
}

function updateWeights(strategies) {
    if (!strategies || strategies.length === 0) {
        document.getElementById('weight-display').innerHTML = '<p class="text-muted">暂无数据</p>'; return;
    }
    document.getElementById('weight-display').innerHTML = strategies.map(s => {
        const pct = (s.current_weight * 100).toFixed(1);
        return `<div class="mb-1"><small>${s.strategy_name}</small>
            <div class="progress" style="height:18px"><div class="progress-bar bg-info" style="width:${pct}%">${pct}% (胜率:${((s.win_rate||0)*100).toFixed(0)}%)</div></div></div>`;
    }).join('');
}

function updatePositions(positions) {
    if (!positions || positions.length === 0) {
        document.getElementById('positions-table').innerHTML = '<p class="text-muted p-3">暂无持仓</p>'; return;
    }
    document.getElementById('positions-table').innerHTML = `
        <table class="table table-sm table-hover mb-0"><thead class="table-dark"><tr><th>代码</th><th>名称</th><th>数量</th><th>成本</th><th>现价</th><th>市值</th><th>浮盈</th><th>止损</th><th>止盈</th><th>策略</th></tr></thead><tbody>
        ${positions.map(p => {
            const pnlCls = (p.unrealized_pnl||0) > 0 ? 'text-up' : 'text-down';
            return `<tr><td>${p.symbol}</td><td>${p.name}</td><td>${p.quantity}</td>
                <td>${(p.avg_cost||0).toFixed(2)}</td><td>${(p.current_price||0).toFixed(2)}</td>
                <td>${formatMoney(p.market_value)}</td>
                <td class="${pnlCls}">${(p.unrealized_pnl||0)>0?'+':''}${formatMoney(p.unrealized_pnl)} (${p.unrealized_pnl_pct}%)</td>
                <td>${(p.stop_loss_price||0).toFixed(2)}</td><td>${(p.take_profit_price||0).toFixed(2)}</td>
                <td><small>${p.strategies||''}</small></td></tr>`;
        }).join('')}</tbody></table>`;
}

function updateStatus(p) {
    document.getElementById('status-display').innerHTML = `
        <div class="small"><span class="text-muted">初始资金:</span> ¥${(p.initial_capital||0).toLocaleString()}</div>
        <div class="small"><span class="text-muted">可用现金:</span> ¥${(p.cash||0).toLocaleString()}</div>
        <div class="small"><span class="text-muted">持仓上限:</span> ${p.max_positions||3} 只</div>
        <div class="small"><span class="text-muted">单只上限:</span> 30%</div>
        <div class="small mt-1"><span class="badge ${p.halted?'bg-danger':'bg-success'}">${p.halted?'停开仓':'正常'}</span></div>`;
}

// Real-time handler
onScanResult = function(data) {
    if (data.buys && data.buys.length > 0 || data.sells && data.sells.length > 0) {
        loadDashboard(); // Refresh on trade
    }
    // Update recent signals
    if (data.signals_generated) {
        const div = document.getElementById('recent-signals');
        if (div) div.innerHTML = `<div class="p-2"><small>最近扫描: ${new Date(data.time).toLocaleTimeString()} | 信号: ${data.signals_generated} | 买入: ${(data.buys||[]).length} | 卖出: ${(data.sells||[]).length}</small></div>`;
    }
};

// Sector analysis
async function loadSectors() {
    try {
        const resp = await fetch('/api/sectors');
        const data = await resp.json();
        if (data.error) { console.warn('Sectors:', data.error); return; }
        const sectors = data.sectors || [];
        const container = document.getElementById('sector-list');
        if (!container) return;
        document.getElementById('sector-time').textContent = '数据时间: ' + (data.data_time || '--');
        container.innerHTML = sectors.map(sec => {
            const avg = sec.avg_change_pct;
            const cls = avg > 0 ? 'text-up' : avg < 0 ? 'text-down' : '';
            const sign = avg > 0 ? '+' : '';
            const stocks = (sec.all_stocks || []).map(s =>
                `${s.name}(${s.code}) <span class="${s.change_pct>0?'text-up':'text-down'}">${s.change_pct>0?'+':''}${s.change_pct.toFixed(1)}%</span>`
            ).join('&nbsp;');
            return `<div class="col-6 col-md-4 col-lg-2 mb-2">
                <div class="card h-100" style="cursor:pointer">
                    <div class="card-body py-2 px-3">
                        <small class="text-muted">${sec.sector}</small>
                        <h5 class="${cls} mb-1">${sign}${avg.toFixed(2)}%</h5>
                        <small class="text-muted">${sec.stock_count}只成分股</small>
                        <div style="font-size:0.75rem;margin-top:4px;line-height:1.4">${stocks}</div>
                    </div>
                </div>
            </div>`;
        }).join('');
    } catch(e) { console.error('Sectors error:', e); }
}

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    loadSectors();
});
setInterval(loadDashboard, 30000);
setInterval(loadSectors, 60000);
