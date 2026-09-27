export const categories=[['1','동작점','DC / OP'],['2','입출력 범위','DC sweep'],['3','로딩','AC / transient'],['4','속도 · 정착','step response'],['5','안정성','STB / phase'],['6','노이즈','noise / sampled noise'],['7','Offset · mismatch','MC / threshold'],['8','선형성','spectrum / sweep'],['9','전력','supply current'],['10','PVT','corner / temperature'],['11','전원 · 기판','PSRR / CMRR'],['12','타이밍 · 초기조건','clock / startup']];
export const templates={ota:'OTA / 증폭기',comparator:'비교기',integrator:'SC 적분기',switch:'Switch / S&H',bias:'Bias / Reference',sar:'SAR ADC',sigma_delta:'ΣΔ ADC',custom:'사용자 정의'};
export const metrics={
 'op.margin.min':{name:'포화 의도 소자의 최소 마진',category:'1',unit:'V',direction:'min',hint:'포화 의도로 지정한 소자의 |VDS|−|VDSAT| 최소값. 진단용; PDK 영역 판정 대체 아님.'},
 'op.gm_id.mean':{name:'평균 gm/ID',category:'1',unit:'1/V',direction:'min',hint:'ID 절댓값 1 fA 초과 소자만 포함. 진단 지표.'},
 'power.dc':{name:'선택 전원의 DC 공급 전력',category:'9',unit:'W',direction:'max',hint:'선택된 전압원의 −Σpwr. DC 전용 실행에서 계산.'},
 'swing.range':{name:'유효 출력 스윙',category:'2',unit:'V',direction:'min',hint:'입력/부하 sweep과 유효 범위 기준을 설정해야 합니다.'},
 'loading.cin':{name:'입력 용량',category:'3',unit:'F',direction:'max',hint:'주입/샘플링 테스트벤치가 필요합니다.'},
 'settling.time':{name:'정착시간',category:'4',unit:'s',direction:'max',hint:'입출력 step, 오차 기준, 평가 구간이 필요합니다.'},
 'stability.pm':{name:'위상 마진',category:'5',unit:'deg',direction:'min',hint:'해당 루프의 STB/probe와 phase 조건이 필요합니다.'},
 'noise.input_rms':{name:'입력 환산 잡음',category:'6',unit:'V',direction:'max',hint:'주파수 대역과 입력 환산 이득을 지정해야 합니다.'},
 'offset.sigma':{name:'Offset σ',category:'7',unit:'V',direction:'max',hint:'MC 설정/표본 수/수렴 결과가 필요합니다.'},
 'adc.sndr':{name:'SNDR',category:'8',unit:'dB',direction:'min',hint:'ADC 샘플·FS·입력 톤·BW·FFT 측정 레시피가 필요합니다.'},
 'pvt.coverage':{name:'필수 조건 커버리지',category:'10',unit:'%',direction:'min',hint:'필수 코너 행렬 정의 후 지원 예정입니다.'},
 'supply.psrr':{name:'PSRR',category:'11',unit:'dB',direction:'min',hint:'전원 주입 주파수와 측정 경로가 필요합니다.'},
 'startup.time':{name:'기동시간',category:'12',unit:'s',direction:'max',hint:'전원 ramp/초기조건과 정상상태 기준이 필요합니다.'}
};
export function condition(run){const c=run.result?.operating_point?.context||{};return {recipe:run.payload.recipe,temperature:c['OpPointTemp.Value']===undefined?null:Number(c['OpPointTemp.Value']),corner:run.result?.model_sections?.join(',')||null};}
export function valueFor(spec,run,block){
 if(run.status!=='completed'||!run.result?.success||run.payload.cell!==block.cell)return null;
 const context=condition(run);for(const [key,value]of Object.entries(spec.scope||{}))if(value!==''&&value!==null&&String(context[key])!==String(value))return null;
 const op=run.result.operating_point;if(!op)return null;
 if(spec.unit!==metrics[spec.metric]?.unit)return null;
 if(op.kind!=='dc')return null;
 const devices=op.devices||[];
 if(spec.metric==='op.margin.min'){const values=devices.filter(d=>block.roles[d.name]==='saturation').map(d=>d.margin).filter(Number.isFinite);return values.length?Math.min(...values):null;}
 if(spec.metric==='op.gm_id.mean'){const values=devices.map(d=>d.gm_id).filter(Number.isFinite);return values.length?values.reduce((a,b)=>a+b,0)/values.length:null;}
 if(spec.metric==='power.dc'){const sources=block.rails.map(name=>op.sources.find(s=>s.name===name));return sources.length&&sources.every(s=>s&&Number.isFinite(s.raw.pwr))?-sources.reduce((sum,s)=>sum+s.raw.pwr,0):null;}
 return null;
}
export function evaluate(spec,runs,block){
 const source=block.inspection?.sha256||runs.find(r=>r.block_id===block.id&&r.status==='completed'&&r.result?.success&&r.payload.cell===block.cell)?.result.source_sha256;
 const candidates=runs.filter(r=>r.block_id===block.id&&r.payload.cell===block.cell&&r.result?.source_sha256===source);
 const measured=candidates.map(run=>({run,value:valueFor(spec,run,block)})).filter(v=>Number.isFinite(v.value));
 if(!measured.length){const older=runs.some(r=>r.block_id===block.id&&r.payload.cell===block.cell&&Number.isFinite(valueFor(spec,r,block)));return {status:older?'stale':'unmeasured',label:older?'이전 회로 결과':'미측정',count:0};}
 const worst=measured.reduce((a,b)=>spec.comparison==='min'?(a.value<b.value?a:b):(a.value>b.value?a:b));
 if(spec.target===null)return {status:'unset',label:'목표 미설정',count:measured.length,worst};
 const margin=spec.comparison==='min'?worst.value-spec.target:spec.target-worst.value;
 // An unsuccessful run in the same source scope prevents a global pass.
 const incomplete=runs.some(r=>r.block_id===block.id&&r.payload.cell===block.cell&&r.payload.expected_sha256===source&&['failed','interrupted','queued','running','cancelled'].includes(r.status));
 return {status:margin<0?'fail':incomplete?'partial':'pass',label:margin<0?'미달':incomplete?'조건 미완료':'측정 범위 만족',count:measured.length,worst,margin};
}
export function fmt(v){if(!Number.isFinite(v))return '—';if(v===0)return '0';return Number(v).toPrecision(4);}
