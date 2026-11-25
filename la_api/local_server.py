"""Loopback-only local web bridge. Never expose this service publicly."""
from __future__ import annotations
import base64,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .pcap_session import extract_session
from .socket_client import JuFengClient

ROOT=Path(__file__).resolve().parent
STATE={"session":None,"client":None,"lock":threading.RLock()}

class Handler(BaseHTTPRequestHandler):
    server_version="LATrackerLocal/0.2"
    def log_message(self,fmt,*args):
        # Do not log request bodies: they may contain captured credentials.
        print("[LA Tracker local] "+(fmt%args))
    def send_json(self,status,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store")
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/" or path=="/index.html":
            raw=(ROOT/"local_console.html").read_bytes()
            self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if path=="/api/status":
            with STATE["lock"]:
                s,c=STATE["session"],STATE["client"]
                self.send_json(200,{"pcap_imported":bool(s),"connected":bool(c and c.login_info),
                    "account":s.account[:2]+"••••" if s else None,
                    "captured_server":s.server_id if s else None,
                    "endpoint":f"{s.host}:{s.port}" if s else None,
                    "login":c.login_info if c and c.login_info else None})
            return
        if path=="/api/catalog":
            raw=(ROOT/"api_catalog.json").read_bytes()
            self.send_response(200);self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw);return
        self.send_json(404,{"error":"not found"})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length<=0 or length>20_000_000:raise ValueError("Invalid request size")
            payload=json.loads(self.rfile.read(length))
            if path=="/api/session/import":
                raw=base64.b64decode(payload["pcap_base64"],validate=True)
                session=extract_session(raw)
                with STATE["lock"]:
                    if STATE["client"]:STATE["client"].close()
                    STATE["session"],STATE["client"]=session,None
                self.send_json(200,{"ok":True,"account":session.account[:2]+"••••",
                    "captured_server":session.server_id,"endpoint":f"{session.host}:{session.port}",
                    "token_found":True,"token_length":len(session.token_key),
                    "warning":"Token remains in process memory only; captured reconnect tokens can expire."});return
            if path=="/api/session/connect":
                with STATE["lock"]:
                    session=STATE["session"]
                    if not session:raise RuntimeError("Import your PCAP first")
                    if STATE["client"]:STATE["client"].close()
                    client=JuFengClient(session,host=payload.get("host") or None,
                        port=int(payload.get("port") or session.port))
                    STATE["client"]=client
                info=client.connect();self.send_json(200,{"ok":True,"login":info});return
            if path=="/api/query/rank":
                with STATE["lock"]:client=STATE["client"]
                if not client:raise RuntimeError("Reconnect first")
                result=client.query_rank(int(payload.get("server_id",139)),
                    int(payload.get("type",1)),int(payload.get("id",0)))
                self.send_json(200,{"ok":True,"message":result.message,
                    "raw_length":result.raw_length,"data":result.fields});return
            if path=="/api/query/union":
                with STATE["lock"]:client=STATE["client"]
                if not client:raise RuntimeError("Reconnect first")
                result=client.query_union(int(payload["union_id"]))
                self.send_json(200,{"ok":True,"message":result.message,
                    "raw_length":result.raw_length,"data":result.fields});return
            if path=="/api/session/disconnect":
                with STATE["lock"]:
                    if STATE["client"]:STATE["client"].close()
                    STATE["client"]=None
                self.send_json(200,{"ok":True});return
            self.send_json(404,{"error":"not found"})
        except Exception as exc:self.send_json(400,{"ok":False,"error":str(exc)})

def main():
    print("LA Tracker local console: http://127.0.0.1:8765")
    print("Loopback only; do not expose this service to a public network.")
    ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()

if __name__=="__main__":main()
