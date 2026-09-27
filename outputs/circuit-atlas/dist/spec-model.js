export const defaults={fs:200000,OSR:100,fin:955.2001953125,Ain:.5,Vref:.5,Cs:2e-12,Ci:10e-12,Cp:.5e-12,A0:1000,GBW:1.3e6,SR:1e6,PM:70,Temp:300,nkTC:4,Vsat:.45,Vhyst:0,jitter:0,N:65536,seed:1};
export function theory(p){
 for(const key of ['fs','OSR','Vref','Cs','Ci','A0','GBW','SR','Temp','N'])if(!Number.isFinite(p[key])||p[key]<=0)throw Error(key+' must be positive');
 for(const key of Object.keys(defaults))if(!Number.isFinite(p[key]))throw Error(key+' must be finite');
 if(p.Cp<0||p.Ain<=0||p.Ain>1||p.fin<=0||p.fin>=p.fs/2||p.Vsat<=0||p.nkTC<0||p.jitter<0||p.Vhyst<0)throw Error('Invalid model conditions');
 const a=p.Cs/p.Ci,beta=p.Ci/(p.Ci+p.Cs+p.Cp),BW=p.fs/(2*p.OSR),Tint=.5/p.fs,tau=1/(2*Math.PI*beta*p.GBW),step=a*p.Vref*(1+p.Ain),sigma=Math.sqrt(p.nkTC*1.380649e-23*p.Temp/p.Cs),signal=p.Ain*p.Vref/Math.sqrt(2);
 return {a,beta,BW,Tint,tau,step,sigma,sigmaIB:sigma/Math.sqrt(p.OSR),snrThermal:20*Math.log10(signal/(sigma/Math.sqrt(p.OSR))),sqnr:7.78-10*Math.log10(Math.PI**2/3)+30*Math.log10(p.OSR),A0min:20*Math.log10(p.OSR),A0recommended:20*Math.log10(3*p.OSR),SRrecommended:2*step/tau,
 settling:[.01,.001,.0001].map(error=>({error,ntau:-Math.log(error),tauMax:Tint/-Math.log(error),GBW:-Math.log(error)/(2*Math.PI*beta*Tint)})),caps:[70,80,90].map(snr=>({snr,C:p.nkTC*1.380649e-23*p.Temp/(p.OSR*signal**2)*10**(snr/10)}))};
}
export function spectrum(y,fs){
 const N=y.length;if(N<16||(N&(N-1)))throw Error('FFT length must be power of two');
 const re=new Float64Array(N),im=new Float64Array(N);let energy=0,mean=y.reduce((a,b)=>a+b,0)/N;
 for(let i=0;i<N;i++){const w=.5*(1-Math.cos(2*Math.PI*i/N));re[i]=(y[i]-mean)*w;energy+=w*w;}
 for(let i=1,j=0;i<N;i++){let bit=N>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j)[re[i],re[j]]=[re[j],re[i]];}
 for(let len=2;len<=N;len*=2){const ar=Math.cos(-2*Math.PI/len),ai=Math.sin(-2*Math.PI/len);for(let i=0;i<N;i+=len){let wr=1,wi=0;for(let j=0;j<len/2;j++){const u=i+j,v=u+len/2,tr=wr*re[v]-wi*im[v],ti=wr*im[v]+wi*re[v];re[v]=re[u]-tr;im[v]=im[u]-ti;re[u]+=tr;im[u]+=ti;const next=wr*ar-wi*ai;wi=wr*ai+wi*ar;wr=next;}}}
 const f=[],psd=[];for(let k=0;k<=N/2;k++){f.push(k*fs/N);psd.push((k===0||k===N/2?1:2)*(re[k]**2+im[k]**2)/(fs*energy));}return {f,psd,df:fs/N};
}
export function sndr(s,fin,BW){
 const k=Math.round(fin/s.df),last=Math.floor(BW/s.df);
 if(k<5||k+4>last||last>=s.psd.length)throw Error('Tone and Hann main lobe must fit inside BW');
 let signal=0,noise=0;for(let i=1;i<=last;i++){if(Math.abs(i-k)<=4)signal+=s.psd[i];else noise+=s.psd[i];}
 const value=10*Math.log10(signal/noise);return {sndr:value,enob:(value-1.76)/6.02};
}
function random(seed){let state=seed>>>0;return ()=>{state=(1664525*state+1013904223)>>>0;return (state+.5)/4294967296;};}
export function simulate(p,ideal=false){
 const t=theory(p),N=p.N;if(N<1024||N>131072||(N&(N-1)))throw Error('N: 1024–131072 power of two');
 const bin=Math.round(p.fin*N/p.fs),fin=bin*p.fs/N;
 if(bin+4>Math.floor(N/(2*p.OSR)))throw Error('입력 톤이 BW 경계에 있습니다. fin을 낮추거나 OSR을 줄이세요.');
 const rng=random(p.seed),gauss=()=>Math.sqrt(-2*Math.log(rng()))*Math.cos(2*Math.PI*rng());
 const y=new Float64Array(N),leak=ideal?1:1-(1+t.a)/p.A0,gain=ideal?1:1/(1+(1+t.a)/p.A0);let v=0,q=0,saturated=0,vmax=0;
 // Discard 4096 startup samples, then record N samples at the known coherent input bin.
 for(let i=-4096;i<N;i++){
  const time=i/p.fs+(ideal?0:p.jitter*gauss()),u=p.Ain*p.Vref*Math.sin(2*Math.PI*fin*time)+(ideal?0:t.sigma*gauss());
  const target=leak*v+t.a*gain*(u-q*p.Vref),dv=target-v;let actual=dv;
  if(!ideal){const step=Math.abs(dv);if(step<=p.SR*t.tau)actual=dv*(1-Math.exp(-t.Tint/t.tau));else{const t0=step/p.SR-t.tau;actual=Math.sign(dv)*(t0>=t.Tint?p.SR*t.Tint:step-p.SR*t.tau*Math.exp(-(t.Tint-t0)/t.tau));}}
  v=Math.max(-p.Vsat,Math.min(p.Vsat,v+actual));q=v>= (ideal?0:p.Vhyst*q)?1:-1;
  if(i>=0){y[i]=q;vmax=Math.max(vmax,Math.abs(v));if(Math.abs(v)>=p.Vsat*.999)saturated++;}
 }
 const spec=spectrum(y,p.fs);return {...sndr(spec,fin,t.BW),fin,vmax,saturation:saturated/N,spectrum:spec};
}
export function runModel(p,progress=()=>{}){
 const ideal=simulate(p,true),real=simulate(p),definitions=[['A0','OTA DC 이득','dB',[20,30,40,50,60,70,80],x=>10**(x/20)],['GBW','GBW','MHz',[.1,.2,.5,1,2,5,10],x=>x*1e6],['SR','슬루율','V/µs',[.05,.1,.2,.5,1,2,5],x=>x*1e6],['Cs','샘플링 캡','pF',[.05,.1,.25,.5,1,2,5],x=>x*1e-12],['jitter','클럭 지터','ps',[1,5,20,100,500,2000],x=>x*1e-12],['Vhyst','히스테리시스','mV',[0,1,5,20,50,100],x=>x*.001]];
 const sweeps=definitions.map(([key,title,unit,values,convert])=>{progress(title);return {key,title,unit,points:values.map(x=>{const q={...p,[key]:convert(x)};if(key==='Cs')q.Ci=q.Cs/(p.Cs/p.Ci);const r=simulate(q);return [x,r.sndr];})};});
 progress('입력 진폭');const amplitudes=[];for(let db=-60;db<=0;db+=3){const r=simulate({...p,Ain:10**(db/20)});amplitudes.push([db,r.sndr]);}
 const peak=amplitudes.reduce((a,b)=>b[1]>a[1]?b:a),crossings=[];
 for(let i=1;i<amplitudes.length;i++){const [x0,y0]=amplitudes[i-1],[x1,y1]=amplitudes[i];if(y0<0&&y1>=0)crossings.push(x0-y0*(x1-x0)/(y1-y0));}
 return {schema:'circuit-atlas-model/1',source:'sd1_all.m 기반 JavaScript 행동 모델; MATLAB 실행 아님',conditions:p,theory:theory(p),ideal,real,sweeps,amplitudes,peak,DR:crossings.length===1?peak[0]-crossings[0]:null,DRnote:'SNDR 0dB 상향 교차에서 피크 입력까지 보간 추정; 표준 DR 측정 아님'};
}
