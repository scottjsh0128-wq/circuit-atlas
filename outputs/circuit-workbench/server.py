"""Local workbench HTTP API; same service/database is exposed through MCP."""
import sys,json,os,secrets,mimetypes,asyncio
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,unquote
HERE=Path(__file__).resolve().parent;ASSETS=HERE/'dist'
sys.path.insert(0,str(HERE.parent/'cadence-mcp'))
import workbench_service as service
from server import cadence_inspect_saved_simulation,cadence_get_current_schematic
TOKEN=secrets.token_hex(32)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,data,content_type='application/json; charset=utf-8'):
        body=json.dumps(data,ensure_ascii=True).encode() if content_type.startswith('application/json') else data
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def guarded(self):
        host=self.headers.get('Host');valid=host in ('127.0.0.1:4174','localhost:4174')
        if not valid or (self.headers.get('Origin') and self.headers['Origin']!='http://'+host) or self.headers.get('Sec-Fetch-Site')=='cross-site':
            self.send(403,{'error':'Same-origin local requests only'});return False
        return True
    def do_GET(self):
        if not self.guarded():return
        route=urlsplit(self.path).path
        try:
            if route=='/api/session':return self.send(200,{'token':TOKEN})
            if route=='/api/state':return self.send(200,service.public_state())
            if route=='/api/available-runs':
                files=sorted((HERE.parent/'cadence-mcp/simulation-results').glob('*/result.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:60];runs=[]
                for p in files:
                    try:
                        r=json.loads(p.read_text());runs.append({'job':r['job'],'cell':r['cell'],'recipe':r.get('recipe','saved'),'success':r['success'],'has_op':'operating_point' in r})
                    except (ValueError,KeyError):pass
                return self.send(200,{'runs':runs})
            file=(ASSETS/('index.html' if route=='/' else unquote(route).lstrip('/'))).resolve()
            if ASSETS.resolve() not in file.parents or not file.is_file():return self.send(404,{'error':'Not found'})
            self.send(200,file.read_bytes(),(mimetypes.guess_type(file)[0] or 'application/octet-stream')+'; charset=utf-8')
        except Exception as e:self.send(500,{'error':str(e)})
    def do_POST(self):
        if not self.guarded():return
        if not secrets.compare_digest(self.headers.get('X-Workbench-Token',''),TOKEN):return self.send(403,{'error':'Invalid session'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<0 or size>256*1024:return self.send(413,{'error':'Request too large'})
            args=json.loads(self.rfile.read(size) or b'{}')
            if not isinstance(args,dict):raise ValueError('Object required')
            route=urlsplit(self.path).path
            if route=='/api/project':result={'id':service.save_project(args)}
            elif route=='/api/block':result={'id':service.save_block(args)}
            elif route=='/api/spec':result={'id':service.save_spec(args)}
            elif route=='/api/inspect':
                result=asyncio.run(cadence_inspect_saved_simulation(service.get_block(args['block_id'])['cell']));service.save_inspection(args['block_id'],result)
            elif route=='/api/run':result=service.start_run(**args)
            elif route=='/api/cancel':result=service.cancel_run(args['id'])
            elif route=='/api/import':result=service.import_run(args['block_id'],args['job'])
            elif route=='/api/schematic':result=asyncio.run(cadence_get_current_schematic())
            elif route=='/api/waveform':
                uid=args['id'];state=service.public_state();run=next((r for r in state['runs'] if r['id']==uid),None)
                if not run or not run['result']:raise ValueError('Unknown run')
                job=run['result']['job']
                if len(job)!=32 or any(c not in '0123456789abcdef' for c in job):raise ValueError('Invalid artifact')
                file=HERE.parent/'cadence-mcp/simulation-results'/job/'tran.csv'
                if file.stat().st_size>30*1024*1024:raise ValueError('Waveform exceeds limit')
                result={'csv':file.read_text()}
            else:return self.send(404,{'error':'Unknown API route'})
            self.send(200,result)
        except (ValueError,KeyError,TypeError) as e:self.send(400,{'error':str(e)})
        except Exception as e:self.send(502,{'error':str(e)})
if __name__=='__main__':
    service.init();service.ensure_worker()
    print('Circuit Workbench: http://127.0.0.1:4174',flush=True)
    ThreadingHTTPServer(('127.0.0.1',4174),Handler).serve_forever()
