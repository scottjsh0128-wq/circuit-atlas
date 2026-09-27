import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomBytes,timingSafeEqual} from 'node:crypto';
import {spawn} from 'node:child_process';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.join(here,'dist');
const python=process.env.CADENCE_MCP_PYTHON||path.resolve(here,'../../work/cadence-mcp-venv/Scripts/python.exe');
const gateway=path.resolve(here,'../cadence-mcp/web_gateway.py');
export function invokeCadence(operation,arguments_={}){
 if(!['status','snapshot','simulation-inspect','simulation-run'].includes(operation))return Promise.reject(Error('Unsupported operation'));
 return new Promise((resolve,reject)=>{
  const child=spawn(python,[gateway,operation],{windowsHide:true,stdio:['pipe','pipe','pipe']});let out='',err='',size=0;
  child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(arguments_));
  const stop=()=>{if(process.platform==='win32'&&child.pid)spawn('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'}).on('error',()=>{});else child.kill();};
  const timer=setTimeout(()=>{stop();reject(Error('Cadence request timed out'));},100000);
  child.stdout.on('data',b=>{size+=b.length;if(size>24*1024*1024){stop();reject(Error('Snapshot exceeds size limit'));}else out+=b.toString();});
  child.stderr.on('data',b=>err=(err+b.toString()).slice(-2000));
  child.on('error',e=>{clearTimeout(timer);reject(e);});
  child.on('close',()=>{clearTimeout(timer);try{const result=JSON.parse(out);if(!result.ok)throw Error(result.error);resolve(result.data);}catch(e){reject(Error(e.message+(out?'':': '+err)));}});
 });
}
export function createAppServer({invoke=invokeCadence,available=fs.existsSync(python)&&fs.existsSync(gateway)}={}){
 const token=randomBytes(32).toString('hex');let busy=false;
 const server=http.createServer(async(req,res)=>{
  const send=(code,data)=>res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}).end(JSON.stringify(data));
  try{
   const port=server.address().port;
   if(![`127.0.0.1:${port}`,`localhost:${port}`].includes(req.headers.host))return send(403,{error:'Invalid host'});
   const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
   if(name.startsWith('/api/')){
    if((req.headers.origin&&req.headers.origin!==`http://${req.headers.host}`)||req.headers['sec-fetch-site']==='cross-site')return send(403,{error:'Same-origin requests only'});
    if(name==='/api/cadence/session'&&req.method==='GET')return send(200,{available,token});
    const operation={'/api/cadence/status':'status','/api/cadence/snapshot':'snapshot','/api/cadence/simulation-inspect':'simulation-inspect','/api/cadence/simulation-run':'simulation-run','/api/cadence/simulation-history':'simulation-history','/api/cadence/simulation-waveform':'simulation-waveform'}[name];
    if(!operation)return send(404,{error:'Unknown API route'});
    if(req.method!=='POST')return send(405,{error:'POST required'});
    const supplied=Buffer.from(req.headers['x-circuit-token']||''),expected=Buffer.from(token);
    if(supplied.length!==expected.length||!timingSafeEqual(supplied,expected))return send(403,{error:'Invalid session token'});
    if(!available)return send(503,{error:'Local MCP runtime is not configured'});
    if(busy)return send(409,{error:'Another Cadence request is running. Retry shortly.'});
    busy=true;try{
     let body='',size=0;for await(const chunk of req){size+=chunk.length;if(size>16384)return send(413,{error:'Request too large'});body+=chunk.toString();}
     let args;try{args=JSON.parse(body||'{}');}catch{return send(400,{error:'Invalid JSON'});}
     if(!args||Array.isArray(args)||typeof args!=='object')return send(400,{error:'Object required'});
     const resultsRoot=path.resolve(here,'../cadence-mcp/simulation-results');
     if(operation==='simulation-history'){
      const runs=(fs.existsSync(resultsRoot)?fs.readdirSync(resultsRoot,{withFileTypes:true}):[]).filter(e=>e.isDirectory()&&/^[a-f0-9]{32}$/.test(e.name)).map(e=>path.join(resultsRoot,e.name,'result.json')).filter(p=>fs.existsSync(p)).sort((a,b)=>fs.statSync(b).mtimeMs-fs.statSync(a).mtimeMs).slice(0,20).map(p=>{try{return JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));}catch{return null;}}).filter(Boolean);
      return send(200,{data:{runs}});
     }
     if(operation==='simulation-waveform'){
      if(typeof args.job!=='string'||!/^[a-f0-9]{32}$/.test(args.job))return send(400,{error:'Invalid job'});
      const file=path.join(resultsRoot,args.job,'tran.csv');if(!fs.existsSync(file))return send(404,{error:'파형 CSV가 없는 실행입니다.'});
      if(fs.statSync(file).size>30*1024*1024)return send(413,{error:'Waveform too large'});
      return send(200,{data:{csv:fs.readFileSync(file,'utf8')}});
     }
     return send(200,{data:await invoke(operation,args)});}catch(e){return send(502,{error:e.message});}finally{busy=false;}
   }
   if(!['GET','HEAD'].includes(req.method))return send(405,{error:'GET required'});
   const file=path.resolve(root,'.'+(name==='/'?'/index.html':name));
   if(!file.startsWith(root+path.sep))return send(403,{error:'Invalid path'});
   const body=fs.readFileSync(file),types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.il':'text/plain','.md':'text/plain'};
   res.writeHead(200,{'Content-Type':(types[path.extname(file)]||'application/octet-stream')+'; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}).end(req.method==='HEAD'?undefined:body);
  }catch{return send(404,{error:'Not found'});}
 });return server;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))createAppServer().listen(4173,'127.0.0.1',()=>console.log('Circuit Atlas: http://127.0.0.1:4173'));
