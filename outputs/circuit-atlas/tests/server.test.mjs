import test from 'node:test';
import http from 'node:http';
import assert from 'node:assert/strict';
import {createAppServer} from '../server.mjs';
test('local API requires same origin and token; dispatches fixed MCP operations',async()=>{
 let calls=[];const server=createAppServer({available:true,invoke:async op=>{calls.push(op);return {bridge_ready:true};}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 try{
  assert.equal((await fetch(base)).status,200);
  assert.equal((await fetch(base+'/api/cadence/status',{method:'POST'})).status,403);
  const {token}=await (await fetch(base+'/api/cadence/session')).json();
  const headers={'X-Circuit-Token':token};
  assert.equal((await fetch(base+'/api/cadence/status',{method:'POST',headers:{...headers,Origin:'https://example.com'}})).status,403);
  assert.equal(await new Promise((resolve,reject)=>{http.get(base+'/api/cadence/session',{headers:{Host:'evil.example'}},res=>{res.resume();resolve(res.statusCode);}).on('error',reject);}),403);
  const response=await fetch(base+'/api/cadence/status',{method:'POST',headers});assert.equal(response.status,200);assert.equal((await response.json()).data.bridge_ready,true);
  assert.equal((await fetch(base+'/api/cadence/shell',{method:'POST',headers})).status,404);
  assert.equal((await fetch(base+'/api/cadence/snapshot',{headers})).status,405);
  assert.equal((await fetch(base+'/server.mjs')).status,404);
  assert.deepEqual(calls,['status']);
 }finally{await new Promise(r=>server.close(r));}
});
test('concurrent requests rejected and error releases request lock',async()=>{
 let finish;const server=createAppServer({available:true,invoke:()=>new Promise((_,reject)=>finish=reject)});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 try{
  const {token}=await (await fetch(base+'/api/cadence/session')).json();const options={method:'POST',headers:{'X-Circuit-Token':token}};
  const pending=fetch(base+'/api/cadence/snapshot',options);
  while(!finish)await new Promise(r=>setTimeout(r,5));
  assert.equal((await fetch(base+'/api/cadence/status',options)).status,409);finish(Error('bridge unavailable'));assert.equal((await pending).status,502);
 }finally{await new Promise(r=>server.close(r));}
});
test('simulation API forwards numeric override data and rejects malformed bodies',async()=>{
 let received;const server=createAppServer({available:true,invoke:async(op,args)=>{received={op,args};return {success:true};}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 try{
  const {token}=await (await fetch(base+'/api/cadence/session')).json();const options={method:'POST',headers:{'X-Circuit-Token':token}};
  const args={cell:'test',expected_sha256:'hash',overrides:{'V8.freq':'1k'}};
  assert.equal((await fetch(base+'/api/cadence/simulation-run',{...options,body:JSON.stringify(args)})).status,200);
  assert.deepEqual(received,{op:'simulation-run',args});
  assert.equal((await fetch(base+'/api/cadence/simulation-run',{...options,body:'{'})).status,400);
  assert.equal((await fetch(base+'/api/cadence/simulation-run',{...options,body:'x'.repeat(17000)})).status,413);
 }finally{await new Promise(r=>server.close(r));}
});
