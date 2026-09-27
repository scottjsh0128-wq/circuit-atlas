import {registerDashboard} from './spec-dashboard.js';
const $=s=>document.querySelector(s);
let dashboard;
let token,info,edits={},running=false,stopRequested=false;
let history=[];try{history=JSON.parse(localStorage.getItem('cadence-simulation-history-v1')||'[]');if(!Array.isArray(history))history=[];}catch{}
const text=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;return el;};
async function api(op,args={}){
 if(!token){const res=await fetch('/api/cadence/session');if(!res.ok)throw Error('로컬 서버를 재시작한 뒤 다시 시도하세요.');const session=await res.json();if(!session.available)throw Error('이 PC의 MCP 실행 환경이 필요합니다.');token=session.token;}
 const res=await fetch('/api/cadence/'+op,{method:'POST',headers:{'X-Circuit-Token':token,'Content-Type':'application/json'},body:JSON.stringify(args),signal:AbortSignal.timeout(110000)});
 const body=await res.json();if(!res.ok)throw Error(body.error||'요청 실패');return body.data;
}
function controls(){ $('#inspect').disabled=running;$('#cell').disabled=running;$('#run').disabled=running||!info;$('#reset').disabled=running||!info;$('#sweep').disabled=running||!info;$('#stop').disabled=!running;$('#sweepKeys').disabled=running;$('#sweepValues').disabled=running;$('#parameters').querySelectorAll('input').forEach(e=>e.disabled=running);}
function renderParameters(){
 const target=$('#parameters');target.replaceChildren();const query=$('#filter').value.toLowerCase();
 for(const p of info?.parameters||[]){if(!p.key.toLowerCase().includes(query))continue;
  const row=text('label','');row.className='parameter-row';const label=text('span',p.key);label.append(text('small','원본 '+p.value));const input=document.createElement('input');input.value=edits[p.key]??p.value;input.setAttribute('aria-label',p.key);input.spellcheck=false;input.disabled=running;
  row.classList.toggle('changed',input.value!==p.value);input.oninput=()=>{if(input.value===p.value)delete edits[p.key];else edits[p.key]=input.value;row.classList.toggle('changed',input.value!==p.value);};row.append(label,input);target.append(row);
 }
}
function renderResults(){
 dashboard?.update(history);
 const target=$('#results');target.replaceChildren();if(!history.length){target.append(text('p','아직 실행한 실험이 없습니다.'));return;}
 for(const result of history){
  const card=text('article','');card.className='run-card';card.append(text('h3',`${result.success?'실행 완료':'실행 실패'} · ${result.cell}`),text('p',`${result.saved_at||''} · 스펙 판정: 미설정`));
  const changes=(result.overrides||[]).map(c=>`${c.key}: ${c.before} → ${c.after}`).join('\n');card.append(text('pre',changes||'원본 조건 실행'));
  if(result.measurements){const m=result.measurements;card.append(text('p',`${m.sample_count} 샘플 · ${m.time_start_s}–${m.time_end_s} s · 초기 응답 포함`));const table=document.createElement('table');const head=document.createElement('tr');['신호','최소','최대','단위'].forEach(v=>head.append(text('th',v)));table.append(head);for(const metric of m.metrics){const row=document.createElement('tr');[metric.signal,Number(metric.min).toPrecision(5),Number(metric.max).toPrecision(5),metric.unit].forEach(v=>row.append(text('td',v)));table.append(row);}card.append(table);}
  if(result.measurement_error)card.append(text('p','측정 실패: '+result.measurement_error));
  const details=document.createElement('details');details.append(text('summary','시뮬레이터 로그 · 저장 위치'),text('pre',(result.log_tail||'')+'\n'+(result.local_result_file||'')));card.append(details);target.append(card);
 }
}
$('#inspect').onclick=async()=>{running=true;info=null;edits={};controls();renderParameters();$('#source').textContent='';$('#status').textContent='저장된 ADE 설정을 읽는 중…';try{info=await api('simulation-inspect',{cell:$('#cell').value.trim()});$('#source').textContent=`분석 ${info.analyses.join(', ')} · 변경 가능 ${info.parameters.length}개 · 저장된 넷리스트 기준`;$('#status').textContent='값을 수정한 뒤 실행하세요. 새 Cadence 변경은 ADE에서 넷리스트 생성 후 다시 읽어야 합니다.';renderParameters();}catch(e){$('#status').textContent='읽기 실패: '+e.message;}finally{running=false;controls();}};
async function execute(candidates){
 if(!info||running)return;running=true;stopRequested=false;controls();const experiment=info;
 try{
  for(let index=0;index<candidates.length;index++){
   if(stopRequested)break;
   $('#status').textContent=`실험 ${index+1}/${candidates.length} 실행 중…`;
   const result=await api('simulation-run',{cell:experiment.cell,expected_sha256:experiment.sha256,overrides:candidates[index]});
   result.saved_at=new Date().toLocaleString();history.unshift(result);history=history.slice(0,20);renderResults();try{localStorage.setItem('cadence-simulation-history-v1',JSON.stringify(history));}catch{}
   if(!result.success||result.measurement_error){$('#status').textContent='실행 또는 측정 실패로 중단했습니다. 로그를 확인하세요.';return;}
  }
  $('#status').textContent=stopRequested?'중지했습니다. 완료된 결과는 유지됩니다.':'실험 완료. 결과와 경고를 확인하세요.';
 }catch(e){$('#status').textContent='요청 실패: '+e.message;}finally{running=false;controls();}
}
$('#run').onclick=()=>execute([{...edits}]);
$('#stop').onclick=()=>{stopRequested=true;$('#status').textContent='현재 실행이 끝나면 중지합니다.';};
$('#sweep').onclick=()=>{
 const keys=$('#sweepKeys').value.split(',').map(s=>s.trim()).filter(Boolean),values=$('#sweepValues').value.split(',').map(s=>s.trim()).filter(Boolean);
 if(!keys.length||!values.length||values.length>12||keys.some(k=>!info.parameters.some(p=>p.key===k))){$('#status').textContent='목록에 있는 파라미터와 최대 12개의 시험값을 입력하세요.';return;}
 execute(values.map(value=>({...edits,...Object.fromEntries(keys.map(key=>[key,value]))})));
};
$('#reset').onclick=()=>{edits={};renderParameters();};$('#filter').oninput=renderParameters;
$('#download').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema:'circuit-atlas-experiments/1',runs:history},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='cadence-experiments.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
renderResults();

dashboard=registerDashboard({api,getRuns:()=>history,setRuns:runs=>{history=runs;renderResults();}});
