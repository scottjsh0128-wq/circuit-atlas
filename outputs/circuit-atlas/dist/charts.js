// SVG data charts. Pointer readout, linear/log axes and SVG export.
const NS='http://www.w3.org/2000/svg';
export function chart(host,series,{xLabel='',yLabel='',logX=false,vertical=[],horizontal=[]}={}){
 host.replaceChildren();const W=820,H=300,L=72,R=22,T=20,B=48;
 const points=series.flatMap(s=>s.points).filter(p=>p.every(Number.isFinite)&&(!logX||p[0]>0));
 if(!points.length){host.textContent='표시할 데이터가 없습니다.';return;}
 const xs=points.map(p=>logX?Math.log10(p[0]):p[0]),ys=points.map(p=>p[1]);let xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys,...horizontal.map(h=>h.value)),ymax=Math.max(...ys,...horizontal.map(h=>h.value));if(xmax===xmin)xmax=xmin+1;if(ymax===ymin)ymax=ymin+1;const pad=(ymax-ymin)*.08;ymin-=pad;ymax+=pad;
 const X=x=>L+((logX?Math.log10(x):x)-xmin)/(xmax-xmin)*(W-L-R),Y=y=>H-B-(y-ymin)/(ymax-ymin)*(H-T-B);
 const svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('width',W);svg.setAttribute('height',H);svg.style.height='auto';svg.setAttribute('role','img');svg.setAttribute('aria-label',xLabel+' / '+yLabel);svg.style.background='#111d26';
 const el=(tag,attrs,content)=>{const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(content!==undefined)n.textContent=content;svg.append(n);return n;};
 for(let i=0;i<=5;i++){const x=L+i*(W-L-R)/5,y=T+i*(H-T-B)/5;el('line',{x1:x,x2:x,y1:T,y2:H-B,stroke:'#30414c'});el('line',{x1:L,x2:W-R,y1:y,y2:y,stroke:'#30414c'});el('text',{x,y:H-B+20,fill:'#aac0ce','font-size':12,'text-anchor':'middle'},(logX?10**(xmin+(xmax-xmin)*i/5):xmin+(xmax-xmin)*i/5).toPrecision(3));el('text',{x:L-8,y:y+4,fill:'#aac0ce','font-size':12,'text-anchor':'end'},(ymax-(ymax-ymin)*i/5).toPrecision(3));}
 for(const h of horizontal)el('line',{x1:L,x2:W-R,y1:Y(h.value),y2:Y(h.value),stroke:'#e7b773','stroke-dasharray':'5 5'});
 for(const v of vertical)if(v.value>0&&X(v.value)>=L&&X(v.value)<=W-R){el('line',{x1:X(v.value),x2:X(v.value),y1:T,y2:H-B,stroke:'#e7b773','stroke-dasharray':'5 5'});el('text',{x:X(v.value)+4,y:T+12,fill:'#e7b773','font-size':12},v.name);}
 const colors=['#70dfb2','#69b3ff','#df95ea','#eac76e'];
 series.forEach((s,i)=>{const valid=s.points.filter(p=>p.every(Number.isFinite)&&(!logX||p[0]>0));const path=valid.map((p,k)=>(k?'L':'M')+X(p[0]).toFixed(2)+','+Y(p[1]).toFixed(2)).join(' ');el('path',{d:path,fill:'none',stroke:s.color||colors[i%4],'stroke-width':1.4});});
 el('text',{x:W/2,y:H-5,fill:'#c9dce6','text-anchor':'middle','font-size':13},xLabel);el('text',{x:14,y:15,fill:'#c9dce6','font-size':12},yLabel);host.append(svg);
 series.forEach((s,i)=>el('text',{x:170+i*150,y:14,fill:s.color||colors[i%4],'font-size':11},s.name));
 const legend=document.createElement('div');legend.className='chart-legend';series.forEach((s,i)=>{const label=document.createElement('span');label.style.color=s.color||colors[i%4];label.textContent=s.name;legend.append(label);});host.append(legend);
 const readout=document.createElement('small');readout.textContent='그래프 위에서 값을 확인하세요.';host.append(readout);
 svg.onpointermove=e=>{const rect=svg.getBoundingClientRect(),px=(e.clientX-rect.left)/rect.width*W;const xx=xmin+(px-L)/(W-L-R)*(xmax-xmin),x=logX?10**xx:xx;readout.textContent=series.map(s=>{let p=s.points[0];for(const a of s.points)if(Math.abs(a[0]-x)<Math.abs(p[0]-x))p=a;return `${s.name}: ${p[0].toPrecision(5)}, ${p[1].toPrecision(5)}`;}).join(' | ');};
 const save=document.createElement('button');save.textContent='SVG 저장';save.className='quiet';save.onclick=()=>{const blob=new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='circuit-chart.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};host.append(save);
}
