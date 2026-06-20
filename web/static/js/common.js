// Common: SSE client + clock + status
let sseConn;
function connectSSE() {
    sseConn = new EventSource('/api/sse');
    sseConn.onopen = () => { document.getElementById('sse-ind').className = 'text-success'; document.getElementById('sse-ind').textContent = '● 已连接'; };
    sseConn.onerror = () => { document.getElementById('sse-ind').className = 'text-warning'; document.getElementById('sse-ind').textContent = '● 重连中'; };
    sseConn.addEventListener('status', e => {
        const d = JSON.parse(e.data);
        const dot = document.getElementById('status-dot');
        if (d.is_trading) { dot.className = 'badge badge-live'; dot.textContent = '● 交易中'; }
        else if (d.status === 'lunch_break') { dot.className = 'badge bg-warning'; dot.textContent = '● 午休'; }
        else { dot.className = 'badge bg-secondary'; dot.textContent = '● 收盘'; }
    });
    sseConn.addEventListener('scan_result', e => { if (typeof onScanResult === 'function') onScanResult(JSON.parse(e.data)); });
}
document.addEventListener('DOMContentLoaded', () => {
    connectSSE();
    setInterval(() => { document.getElementById('clock').textContent = new Date().toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}); }, 1000);
});
function togglePause() { fetch('/api/control', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action: document.getElementById('btn-pause').textContent.includes('暂停')?'pause':'resume'})}).then(r=>r.json()).then(d=>{document.getElementById('btn-pause').textContent = d.status==='paused'?'▶ 恢复':'⏯ 暂停';}); }
function formatChange(v) { if(v==null||isNaN(v))return{text:'--',cls:''}; const s=v>0?'+':''; return {text:s+v.toFixed(2)+'%', cls:v>0?'text-up':v<0?'text-down':''}; }
function formatMoney(v) { if(v==null||isNaN(v))return'--'; if(Math.abs(v)>=1e8)return(v/1e8).toFixed(2)+'亿'; if(Math.abs(v)>=1e4)return(v/1e4).toFixed(2)+'万'; return v.toFixed(2); }
var onScanResult = null;
