async function loadAnalysis() {
    try {
        const [pResp, eResp, prResp] = await Promise.all([
            fetch('/api/performance'), fetch('/api/equity'), fetch('/api/params')
        ]);
        const perf = await pResp.json();
        const equity = await eResp.json();
        const params = await prResp.json();

        // Performance table
        const strats = perf.strategies || [];
        document.getElementById('perf-table').innerHTML = `
            <table class="table table-sm table-hover"><thead class="table-dark"><tr><th>策略</th><th>交易数</th><th>胜率</th><th>平均盈利</th><th>平均亏损</th><th>盈亏比</th><th>权重</th></tr></thead><tbody>
            ${strats.map(s => `<tr><td><strong>${s.strategy_name}</strong></td><td>${s.total_trades}</td><td>${((s.win_rate||0)*100).toFixed(1)}%</td><td class="text-up">+${((s.avg_win_pct||0)*100).toFixed(2)}%</td><td class="text-down">-${((s.avg_loss_pct||0)*100).toFixed(2)}%</td><td>${(s.profit_factor||0).toFixed(2)}</td><td>${((s.current_weight||0)*100).toFixed(1)}%</td></tr>`).join('')}
            </tbody></table>`;

        // Weight evolution chart
        if (strats.length > 0) {
            const names = strats.map(s=>s.strategy_name);
            const weights = strats.map(s=>s.current_weight);
            const trace = { type:'bar', x:names, y:weights, marker:{color:['#42a5f5','#ffa726','#ce93d8']}, text:weights.map(w=>(w*100).toFixed(1)+'%'), textposition:'auto' };
            Plotly.newPlot('weight-chart', [trace], {paper_bgcolor:'#0f1b2d',plot_bgcolor:'#0f1b2d',font:{color:'#e0e0e0',size:11},margin:{l:40,r:20,t:10,b:40},yaxis:{title:'权重',tickformat:',.0%'}}, {responsive:true,displaylogo:false});
        }

        // Params display
        const paramsList = params.params || [];
        document.getElementById('params-display').innerHTML = paramsList.map(p => {
            let pObj = {};
            try { pObj = JSON.parse(p.params_json); } catch(e) {}
            return `<div class="card mb-2"><div class="card-header"><strong>${p.strategy_name}</strong> <small class="text-muted">更新: ${(p.updated_at||'').substr(0,10)} | Sharpe: ${p.sharpe||'N/A'}</small></div>
                <div class="card-body"><code>${JSON.stringify(pObj)}</code></div></div>`;
        }).join('') || '<p class="text-muted p-2">暂无数据</p>';

    } catch(e) { console.error(e); }
}
document.addEventListener('DOMContentLoaded', loadAnalysis);
