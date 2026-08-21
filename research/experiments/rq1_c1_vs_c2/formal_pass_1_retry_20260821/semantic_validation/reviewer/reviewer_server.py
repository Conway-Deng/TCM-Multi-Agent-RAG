import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SAMPLE=ROOT/'human_validation_sample.jsonl'; DECISIONS=ROOT/'human_validation.json'; PORT=8766
LABELS={'SUPPORTED','PARTIALLY_SUPPORTED','NOT_SUPPORTED','CONTRADICTED','UNRESOLVED'}
class Handler(BaseHTTPRequestHandler):
  def send_json(self,obj,status=200):
    data=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
  def do_GET(self):
    if self.path=='/api/sample': self.send_json([json.loads(x) for x in SAMPLE.read_text(encoding='utf-8').splitlines() if x]); return
    if self.path=='/api/review': self.send_json(json.loads(DECISIONS.read_text(encoding='utf-8'))); return
    name='index.html' if self.path=='/' else self.path.lstrip('/'); p=Path(__file__).parent/name
    if p.exists() and p.is_file():
      data=p.read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8' if p.suffix=='.html' else 'text/javascript; charset=utf-8' if p.suffix=='.js' else 'text/css; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
    self.send_error(404)
  def do_POST(self):
    if self.path!='/api/review': self.send_error(404); return
    try: body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))); item=body['item_id']; label=body['label'];
    except Exception: self.send_error(400); return
    if label not in LABELS: self.send_error(400,'invalid label'); return
    doc=json.loads(DECISIONS.read_text(encoding='utf-8')); doc.setdefault('decisions',{})[item]={'label':label,'review_notes':body.get('review_notes',''),'review_timestamp':body.get('review_timestamp','')}; DECISIONS.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); self.send_json({'ok':True})
  def log_message(self,*args): pass
if __name__=='__main__': print('Reviewer: http://127.0.0.1:%d'%PORT); HTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
