import json
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SAMPLE=ROOT/'owner_audit_sample.json'; RESULTS=ROOT/'owner_audit_results.json'; PORT=8767; CHOICES={'AGREE','DISAGREE','UNSURE'}
class H(BaseHTTPRequestHandler):
 def sendj(self,x,s=200):
  b=json.dumps(x,ensure_ascii=False).encode();self.send_response(s);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/api/sample':self.sendj(json.loads(SAMPLE.read_text(encoding='utf-8')));return
  if self.path=='/api/results':self.sendj(json.loads(RESULTS.read_text(encoding='utf-8')));return
  p=Path(__file__).parent/('index.html' if self.path=='/' else self.path.lstrip('/'))
  if p.exists():
   b=p.read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if p.suffix=='.html' else 'text/javascript; charset=utf-8' if p.suffix=='.js' else 'text/css');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  self.send_error(404)
 def do_POST(self):
  if self.path!='/api/results':self.send_error(404);return
  try:d=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));c=d['choice']
  except Exception:self.send_error(400);return
  if c not in CHOICES:self.send_error(400);return
  x=json.loads(RESULTS.read_text(encoding='utf-8'));x.setdefault('decisions',{})[d['audit_item_id']]={'choice':c,'owner_note':d.get('owner_note',''),'timestamp':d.get('timestamp','')};RESULTS.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');self.sendj({'ok':True})
 def log_message(self,*a):pass
if __name__=='__main__':print('Owner audit: http://127.0.0.1:%d'%PORT);HTTPServer(('127.0.0.1',PORT),H).serve_forever()
