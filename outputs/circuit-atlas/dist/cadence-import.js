export function registerCadenceImport({button,modal,close,validate,apply,saveProject,getChangeCount}){
 button.onclick=async()=>{
  modal('Cadence에서 현재 회로 불러오기',`<p>Virtuoso에서 원하는 schematic을 활성화하고 Check and Save를 실행하세요. 현재 셀의 연결 구조를 읽습니다.</p><div class="info-box" id="cadenceStatus" role="status">연결 확인 중…</div><p class="small-note">브리지 로드가 필요하면 CIW에서 실행하세요.</p><pre>load("/home/buet/.circuit-atlas/bridge.il")</pre><div id="cadencePreview"></div><p>현재 프로젝트는 ‘이 회로 열기’를 눌러야 교체됩니다. 적용 후 실행 취소도 가능합니다.</p><div class="modal-actions"><button id="cadenceSave">현재 프로젝트 저장</button><button id="cadenceRead" disabled>현재 회로 읽기</button><button id="cadenceApply" class="primary" disabled>이 회로 열기</button></div>`);
  const status=document.querySelector('#cadenceStatus'),preview=document.querySelector('#cadencePreview'),read=document.querySelector('#cadenceRead'),accept=document.querySelector('#cadenceApply');
  const active=()=>status.isConnected&&document.querySelector('#modal').open;
  let token,staged;
  const request=async(operation)=>{
   const response=await fetch('/api/cadence/'+operation,{method:operation==='session'?'GET':'POST',headers:token?{'X-Circuit-Token':token}:{},signal:AbortSignal.timeout(80000)});
   if(response.status===404)throw Error('로컬 실행본에서만 연결할 수 있습니다. Start.cmd로 실행한 서버를 사용하거나 서버를 재시작하세요.');
   const body=await response.json();if(!response.ok)throw Error(body.error||'연결 실패');return body;
  };
  document.querySelector('#cadenceSave').onclick=saveProject;
  accept.onclick=()=>{if(staged){apply(staged);close();}};
  read.onclick=async()=>{
   read.disabled=true;accept.disabled=true;staged=null;preview.textContent='';status.textContent='Cadence에서 회로를 읽는 중…';
   try{
    const {data}=await request('snapshot');if(!active())return;validate(data.circuit);staged=data.circuit;
    const cell=staged.cells.find(c=>c.id===staged.top),pins=cell.instances.flatMap(i=>i.pins);
    preview.textContent=`${cell.id} · 소자 ${cell.instances.length}개 · 넷 ${cell.nets.length}개 · 포트 ${cell.ports.length}개 · 핀 ${pins.length}개 (미연결 ${pins.filter(p=>p.net===null).length}개). 현재 프로젝트 변경 ${getChangeCount()}건.`;
    status.textContent=cell.instances.length?'읽기 완료. 회로 정보를 확인한 뒤 열어 주세요.':'소자가 없는 셀입니다. 원하는 schematic 창이 활성화되어 있는지 확인하세요.';accept.disabled=false;
   }catch(e){if(active())status.textContent='읽기 실패: '+e.message;}finally{if(active())read.disabled=false;}
  };
  try{
   const session=await request('session');if(!active())return;token=session.token;
   if(!session.available)throw Error('이 PC에 MCP 실행 환경이 설정되지 않았습니다. 파일 가져오기는 계속 사용할 수 있습니다.');
   const {data}=await request('status');if(!active())return;
   status.textContent=data.bridge_ready?'SSH 연결 및 Virtuoso 브리지 정상':'SSH 연결됨. Virtuoso CIW에서 브리지를 로드해 주세요.';read.disabled=false;
  }catch(e){if(active())status.textContent='연결 확인 실패: '+e.message;}
 };
}
