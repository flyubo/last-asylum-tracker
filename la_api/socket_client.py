"""Local JuFeng TCP client. Captured tokens are kept in memory and never logged."""
from __future__ import annotations
import base64, socket, threading, time
from dataclasses import dataclass
from typing import Any
from .pcap_session import CapturedSession, parse_protobuf_fields
from .protocol import Frame, FrameCounter, FrameDecoder, encode_frame

def _varint(value:int)->bytes:
    if value<0: raise ValueError("negative values unsupported")
    out=bytearray()
    while value>127: out.append((value&127)|128); value>>=7
    out.append(value); return bytes(out)
def _int_field(n:int,v:int)->bytes: return _varint(n<<3)+_varint(v)
def _string_field(n:int,v:str)->bytes:
    b=v.encode(); return _varint((n<<3)|2)+_varint(len(b))+b

def _json_value(wire:int,value:Any,depth:int=0):
    if wire==0:return value
    if wire in (1,5):return value.hex()
    if wire==2:
        try:
            s=value.decode("utf-8")
            if s and all(c.isprintable() or c in "\r\n\t" for c in s):return s
        except UnicodeDecodeError:pass
        if depth<5:
            try:
                nested=parse_protobuf_fields(value)
                if nested:return _json_fields(nested,depth+1)
            except Exception:pass
        return {"base64":base64.b64encode(value).decode(),"length":len(value)}
    return str(value)
def _json_fields(fields,depth=0):
    out={}
    for n,w,v in fields:
        k=f"field_{n}"; item=_json_value(w,v,depth)
        if k in out:
            if not isinstance(out[k],list):out[k]=[out[k]]
            out[k].append(item)
        else:out[k]=item
    return out

@dataclass
class QueryResult:
    message:str
    fields:dict
    raw_length:int

class JuFengClient:
    def __init__(self,session:CapturedSession,host:str|None=None,port:int|None=None,timeout:float=10):
        self.session=session; self.host=host or session.host; self.port=port or session.port
        self.timeout=timeout; self.sock=None; self.tx=FrameCounter(); self.rx=FrameDecoder(FrameCounter())
        self.pending=[]; self.lock=threading.RLock(); self.login_info={}
    def _send(self,name,body):
        if self.sock is None:raise RuntimeError("Not connected")
        self.sock.sendall(encode_frame(name,body,self.tx))
    def _next_frame(self,timeout=None):
        if self.pending:return self.pending.pop(0)
        if self.sock is None:raise RuntimeError("Not connected")
        self.sock.settimeout(timeout or self.timeout)
        while True:
            data=self.sock.recv(65536)
            if not data:raise ConnectionError("Server closed TCP connection")
            frames=self.rx.feed(data)
            if frames:self.pending.extend(frames[1:]);return frames[0]
    def _wait_for(self,accepted:set[str],timeout=None):
        deadline=time.monotonic()+(timeout or self.timeout); seen=[]
        while time.monotonic()<deadline:
            frame=self._next_frame(max(.2,deadline-time.monotonic()))
            if frame.name in accepted:return frame
            if frame.name in {"PermanentAccountS2C","LoginErrorS2C","LoginReconnectErrorS2C"}:
                raise RuntimeError(f"Server rejected reconnect ({frame.name}); captured token may have expired")
            seen.append(frame.name)
        raise TimeoutError(f"Waiting for {sorted(accepted)} timed out; received {seen[-8:]}")
    def _wait_sequence(self,expected:list[str],timeout=None):
        """Wait for the captured login handshake sequence without advancing early."""
        deadline=time.monotonic()+(timeout or self.timeout); seen=[]
        for wanted in expected:
            while time.monotonic()<deadline:
                frame=self._next_frame(max(.2,deadline-time.monotonic()))
                if frame.name==wanted:
                    break
                if frame.name in {"PermanentAccountS2C","LoginErrorS2C","LoginReconnectErrorS2C"}:
                    raise RuntimeError(f"Server rejected login ({frame.name})")
                seen.append(frame.name)
            else:
                raise TimeoutError(f"Waiting for login sequence {expected}; stopped before {wanted}; received {seen[-8:]}")
    def connect(self):
        with self.lock:
            stage="TCP connect"
            try:
                self.sock=socket.create_connection((self.host,self.port),timeout=self.timeout)
                stage="waiting for LoginNoticeS2C after LoginNoticeC2S"
                notice=_int_field(1,self.session.server_id)+_string_field(2,self.session.account)+_string_field(3,"ko")
                self._send("LoginNoticeC2S",notice)
                # The captured client waits for the notice and BOTH AckCode frames
                # before sending the next login request. Returning on the first
                # AckCode (or notice) races the server handshake and gets the
                # connection closed.
                self._wait_sequence(["LoginNoticeS2C","AckCode","AckCode"],15)
                stage="waiting for LoginReconnectRespS2C after LoginReconnectC2S"
                reconnect=_string_field(1,self.session.account)+_int_field(2,self.session.account_uid)+_string_field(3,self.session.token_key)
                self._send("LoginReconnectC2S",reconnect)
                response=self._wait_for({"LoginReconnectRespS2C","LoginRespS2C"},15)
                stage="parsing reconnect response"
                outer=parse_protobuf_fields(response.body)
                nested=next((v for n,w,v in outer if n==1 and w==2),response.body)
                fields=parse_protobuf_fields(nested); values={n:v for n,w,v in fields if w==0}
                game_uid=int(values.get(4,0)); server_id=int(values.get(3,self.session.server_id)); union_id=int(values.get(34,0))
                if not game_uid:raise RuntimeError("Reconnect response did not contain gameUid")
                self.login_info={"game_uid":game_uid,"server_id":server_id,"union_id":union_id}
                stage="sending LoginSuccessC2S"
                self._send("LoginSuccessC2S",_int_field(1,game_uid))
                return dict(self.login_info)
            except Exception as exc:
                raise RuntimeError(f"{stage}: {type(exc).__name__}: {exc}") from exc
    def query_rank(self,server_id:int,rank_type:int=1,rank_id:int=0):
        with self.lock:
            if self.sock is None or not self.login_info:raise RuntimeError("Connect first")
            body=_int_field(1,server_id)+_int_field(2,rank_type)+_int_field(3,rank_id)
            self._send("QueryRankInfoC2S",body)
            f=self._wait_for({"RankInfoS2C","QueryRankInfoS2C"},15)
            return QueryResult(f.name,_json_fields(parse_protobuf_fields(f.body)),len(f.body))
    def query_union(self,union_id:int):
        with self.lock:
            if self.sock is None or not self.login_info:raise RuntimeError("Connect first")
            self._send("QueryUnionPublicInfoC2S",_int_field(1,union_id))
            f=self._wait_for({"QueryUnionPublicInfoS2C"},15)
            return QueryResult(f.name,_json_fields(parse_protobuf_fields(f.body)),len(f.body))
    def close(self):
        with self.lock:
            if self.sock:
                try:self.sock.close()
                finally:self.sock=None
            self.pending.clear();self.login_info.clear()
