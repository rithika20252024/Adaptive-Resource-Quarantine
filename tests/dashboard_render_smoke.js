const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const elements = {};
const context = {
 document: {getElementById: id => elements[id] ||= {textContent:'',innerHTML:''}},
 console,
};
let script=fs.readFileSync(require('path').join(__dirname,'../arq/web/static/index.html'),'utf8').split('<script>')[1].split('</script>')[0];
script=script.replace('    fetchStatus();\n    setInterval(fetchStatus, 1000);','');
vm.createContext(context);vm.runInContext(script,context);
const row={pid:123,name:'cpu fixture',telemetry_status:'ok',score:.79,cpu_pct:100,mem_mb:8,ml_score:1,ml_margin:4,ml_raw_score:5,ml_threshold:1,ml_anomaly:true,ml_mode:'shadow',stage:'NORMAL',policy_stage:'SOFT_QUARANTINE',control_status:'dry_run',duty_cycle:1,managed:true};
context.renderTable([row],false);
const html=elements.procTableBody.innerHTML;
assert(html.includes('SOFT_QUARANTINE'));
assert(html.includes('Unrestricted (dry run)'));
assert(html.includes('4.000'));
assert(!html.includes('>NORMAL<'));
assert.equal(elements.quarantinedProcs.textContent,0);
context.renderTable([{...row,pid:1,managed:false}],false);
assert(elements.procTableBody.innerHTML.includes('Monitor only'));
assert(!elements.procTableBody.innerHTML.includes('stopPid('));
console.log('Dashboard JS smoke checks passed: proposal vs applied state, margin, restriction count and unmanaged controls.');
