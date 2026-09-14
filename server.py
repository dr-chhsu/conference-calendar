"""Local preview. Publish public/ on an HTTPS static host for external subscribers."""
import argparse
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from calendar_app import ROOT

class Handler(SimpleHTTPRequestHandler):
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.ics':'text/calendar; charset=utf-8','.json':'application/json; charset=utf-8'}
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'public'),**kwargs)
    def end_headers(self):
        self.send_header('Cache-Control','public, max-age=300')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);args=p.parse_args()
    print(f'Preview: http://{args.host}:{args.port}',flush=True)
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
