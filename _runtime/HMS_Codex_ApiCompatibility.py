#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, http.client, http.server, importlib.util, json, os, shutil, socket, socketserver, sys, threading, time
from pathlib import Path

VERSION="25.38"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def sha(b:bytes):return hashlib.sha256(b).hexdigest()

def send(handler,status,body,ctype="application/json",extra=None):
    if isinstance(body,(dict,list)):body=json.dumps(body,separators=(",",":"),ensure_ascii=False).encode()
    if isinstance(body,str):body=body.encode()
    handler.send_response(status);handler.send_header("Content-Type",ctype);handler.send_header("Content-Length",str(len(body)))
    for k,v in (extra or {}).items():handler.send_header(k,v)
    handler.end_headers();handler.wfile.write(body)

class EchoUpstream(http.server.BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,*a):pass
    def _body(self):
        n=int(self.headers.get("Content-Length","0") or 0);return self.rfile.read(n) if n else b""
    def do_GET(self):
        if self.path.startswith('/v1/models'):
            return send(self,200,{"object":"list","data":[{"id":"gpt-5.6-sol","object":"model","owned_by":"openai"}]})
        return send(self,200,{"ok":True,"path":self.path})
    def do_PATCH(self):
        raw=self._body();return send(self,200,{"ok":True,"method":"PATCH","body_sha256":sha(raw)})
    def do_POST(self):
        raw=self._body()
        try:o=json.loads(raw or b'{}')
        except:o={}
        if self.path.startswith('/v1/error429'):
            return send(self,429,{"error":{"message":"rate limited upstream","type":"rate_limit_error","code":"rate_limit_exceeded"}})
        if o.get('stream') is True:
            chunks=[
                'data: '+json.dumps({"type":"response.created","response":{"id":"r_stream"}})+'\n\n',
                'data: '+json.dumps({"type":"response.output_text.delta","delta":"OK"})+'\n\n',
                'data: '+json.dumps({"type":"response.completed","response":{"id":"r_stream","usage":{"input_tokens":12,"output_tokens":3,"total_tokens":15}}})+'\n\n',
                'data: [DONE]\n\n'
            ]
            data=''.join(chunks).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Connection','close');self.end_headers()
            for c in chunks:self.wfile.write(c.encode());self.wfile.flush();time.sleep(.01)
            self.close_connection=True;return
        return send(self,200,{"id":"resp_echo","object":"response","model":o.get('model'),"echo_sha256":sha(raw),"usage":{"input_tokens":20,"output_tokens":5,"total_tokens":25}})

class Server(socketserver.ThreadingMixIn,http.server.HTTPServer):daemon_threads=True;allow_reuse_address=True

def start_upstream():
    s=Server(('127.0.0.1',0),EchoUpstream);threading.Thread(target=s.serve_forever,daemon=True).start();return s

def start_gateway(gw,temp,up):
    keys=gw.KeyStore(temp/'keys.json');rec,key=keys.create('compat',['gpt-*'],[],['UP'],[],None,'',None,0,{}, {})
    cfg={
        'host':'127.0.0.1','port':0,'strategy':'stable-round-robin','session_affinity':True,'session_ttl_sec':3600,
        'health_fail_threshold':3,'health_cooldown_sec':5,'require_client_key':True,'max_failover_attempts':1,
        'retry_statuses':[429,500,502,503,504],'require_idempotency_for_post_replay':True,'stream_chunk_bytes':17,
        'upstream_timeout_sec':5,'usage_capture_max_bytes':2097152,'websocket_enabled':True,'cors_enabled':True,
        'cors_allowed_origins':['http://localhost:*','http://127.0.0.1:*'],'max_request_bytes':4*1024*1024,
        'targets':[{'id':'UP','account':'compat@example.com','base_url':f'http://127.0.0.1:{up.server_address[1]}','enabled':True,'priority':10,'weight':1,'model_allow':['gpt-*'],'model_deny':[]}]
    }
    cfgp=temp/'gateway.json';cfgp.write_text(json.dumps(cfg),'utf-8');trace=temp/'trace.jsonl'
    s=gw.ThreadingServer(('127.0.0.1',0),gw.Handler);s.keys=keys;s.configure_runtime(cfgp,cfg,str(trace));threading.Thread(target=s.serve_forever,daemon=True).start()
    return s,key,trace

def request(port,key,method,path,obj=None,headers=None,raw=None):
    h={'Authorization':'Bearer '+key};h.update(headers or {})
    body=raw
    if obj is not None:body=json.dumps(obj,separators=(",",":"),ensure_ascii=False).encode();h['Content-Type']='application/json'
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=5);c.request(method,path,body=body,headers=h);r=c.getresponse();data=r.read();hs=dict(r.getheaders());status=r.status;c.close();return status,hs,data

def raw_chunked(port,key,path,raw):
    s=socket.create_connection(('127.0.0.1',port),timeout=5)
    head=(f'POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {key}\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n').encode();s.sendall(head)
    for i in range(0,len(raw),11):
        c=raw[i:i+11];s.sendall(f'{len(c):X}\r\n'.encode()+c+b'\r\n')
    s.sendall(b'0\r\n\r\n');buf=b''
    while True:
        d=s.recv(65536)
        if not d:break
        buf+=d
    s.close();head,_,body=buf.partition(b'\r\n\r\n');status=int(head.split(b' ',2)[1]);return status,head,body

def audit(root:Path,temp:Path):
    shutil.rmtree(temp,ignore_errors=True);temp.mkdir(parents=True)
    gw=loadmod('hms_gateway_2538',root/'HMS_Codex_SmartGateway.py');up=start_upstream();srv,key,trace=start_gateway(gw,temp,up);port=srv.server_address[1]
    tests=[]
    def add(name,ok,detail='',level='SYNTHETIC_VERIFIED'):tests.append({'name':name,'status':'PASS' if ok else 'FAIL','level':level,'detail':detail})
    try:
        st,hs,b=request(port,key,'GET','/hms/compatibility');o=json.loads(b);surf=o.get('surfaces',{})
        add('contract.discovery',st==200 and tuple(int(x) for x in str(o.get('version','0.0')).split('.')[:2]) >= tuple(int(x) for x in VERSION.split('.')[:2]) and surf.get('/v1/responses')=='PASS_THROUGH',json.dumps(o,separators=(",",":")))
        st,hs,b=request(port,key,'GET','/v1/models');o=json.loads(b);add('models.aggregate',st==200 and any(x.get('id')=='gpt-5.6-sol' for x in o.get('data',[])),str(o.get('data')))

        complex_req={
            'model':'gpt-5.6-sol','input':[{'role':'user','content':[{'type':'input_text','text':'PRIVATE_MARKER_2538'},{'type':'input_image','image_url':'data:image/png;base64,AAA'},{'type':'input_file','file_id':'file_fake'}]}],
            'tools':[{'type':'function','name':'calc','parameters':{'type':'object'}},{'type':'mcp','server_label':'demo'},{'type':'web_search_preview'}],
            'text':{'format':{'type':'json_schema','name':'out','schema':{'type':'object'}}},'reasoning':{'effort':'medium'}
        }
        raw=json.dumps(complex_req,separators=(",",":"),ensure_ascii=False).encode();st,hs,b=request(port,key,'POST','/v1/responses',raw=raw,headers={'Content-Type':'application/json','Idempotency-Key':'compat-1'})
        o=json.loads(b);add('responses.body_preservation',st==200 and o.get('echo_sha256')==sha(raw) and hs.get('X-HMS-Compatibility-Version')==VERSION,f"status={st} hash={o.get('echo_sha256')}")

        stream_req={'model':'gpt-5.6-sol','input':'hello','stream':True};st,hs,b=request(port,key,'POST','/v1/responses',obj=stream_req,headers={'Accept':'text/event-stream','Idempotency-Key':'compat-stream'})
        text=b.decode('utf-8','replace');add('streaming.sse',st==200 and 'response.output_text.delta' in text and 'response.completed' in text and '[DONE]' in text,f'bytes={len(b)}')

        chat={'model':'gpt-5.6-sol','messages':[{'role':'user','content':'hello'}],'tools':[{'type':'function','function':{'name':'x','parameters':{'type':'object'}}}]};rawc=json.dumps(chat,separators=(",",":")).encode();st,_,b=request(port,key,'POST','/v1/chat/completions',raw=rawc,headers={'Content-Type':'application/json','Idempotency-Key':'compat-chat'});add('chat_completions.pass_through',st==200 and json.loads(b).get('echo_sha256')==sha(rawc),f'status={st}')

        patch_raw=b'{"model":"gpt-5.6-sol","op":"probe"}';st,_,b=request(port,key,'PATCH','/v1/responses/resp_fake',raw=patch_raw,headers={'Content-Type':'application/json'});add('transport.patch',st==200 and json.loads(b).get('method')=='PATCH',f'status={st}')

        chunk_obj={'model':'gpt-5.6-sol','input':'chunked-input','stream':False};chunk_raw=json.dumps(chunk_obj,separators=(",",":")).encode();st,_,b=raw_chunked(port,key,'/v1/responses',chunk_raw);o=json.loads(b);add('transport.chunked_request',st==200 and o.get('echo_sha256')==sha(chunk_raw),f'status={st}')

        st,_,b=request(port,'bad-key','POST','/v1/responses',obj={'model':'gpt-5.6-sol','input':'x'});o=json.loads(b);err=o.get('error') or {};add('errors.gateway_openai_shape',st==401 and isinstance(err,dict) and err.get('type')=='authentication_error' and err.get('code')=='INVALID_CLIENT_KEY',json.dumps(o))

        # Upstream error must not be rewritten. Route generic path to same target; max attempts=1.
        st,_,b=request(port,key,'POST','/v1/error429',obj={'model':'gpt-5.6-sol','input':'x'},headers={'Idempotency-Key':'compat-429'});o=json.loads(b);err=o.get('error') or {};add('errors.upstream_passthrough',st==429 and err.get('code')=='rate_limit_exceeded' and 'hms_error' not in o,json.dumps(o))

        # Feature telemetry contains labels only, never body/tool arguments/private marker.
        time.sleep(.05);tr=trace.read_text('utf-8');rows=[json.loads(x) for x in tr.splitlines() if x.strip()]
        row=next((x for x in rows if x.get('path')=='/v1/responses' and 'mcp' in (x.get('compat_features') or [])),{})
        needed={'responses','tool_calls','mcp','web_search','image_input','attachments','structured_output','reasoning'}
        feats=set(row.get('compat_features') or []);add('telemetry.capability_labels',needed.issubset(feats),str(sorted(feats)))
        add('privacy.no_body_or_secret_trace','PRIVATE_MARKER_2538' not in tr and key not in tr,'trace contains metadata/capability labels only')

        # CORS contract
        c=http.client.HTTPConnection('127.0.0.1',port,timeout=5);c.request('OPTIONS','/v1/responses',headers={'Origin':'http://localhost:3000','Access-Control-Request-Method':'POST'});r=c.getresponse();r.read();hh=dict(r.getheaders());status=r.status;c.close();add('cors.loopback',status==204 and hh.get('Access-Control-Allow-Origin')=='http://localhost:3000',f'status={status}')
    finally:
        srv.shutdown();srv.server_close();up.shutdown();up.server_close()
    passed=sum(x['status']=='PASS' for x in tests);failed=len(tests)-passed
    matrix={k:'SYNTHETIC_VERIFIED' for k in ['models','responses','chat_completions','streaming_sse','tool_calls','mcp','web_search','image_input','attachments','structured_output','reasoning','chunked_request','patch','error_mapping','privacy']}
    return {'version':VERSION,'verdict':'PASS' if failed==0 else 'FAIL','summary':{'pass':passed,'fail':failed,'total':len(tests)},'matrix':matrix,'tests':tests,'runtime_windows_codex':'DEFERRED_BY_OPERATOR','soak':'NOT_YET'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--temp',required=True);ap.add_argument('--output');a=ap.parse_args()
    data=audit(Path(a.root),Path(a.temp));out={'ok':data['verdict']=='PASS','data':data}
    if a.output:Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2));sys.exit(0 if out['ok'] else 2)
if __name__=='__main__':main()
