"""Extract a user's own reconnect session from a classic PCAP. Secrets remain in memory."""
from __future__ import annotations
import socket, struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from .protocol import FrameDecoder, ProtocolError

@dataclass
class CapturedSession:
    account: str
    account_uid: int
    token_key: str
    server_id: int
    host: str
    port: int
    reconnect_body: bytes = b""
    notice_body: bytes = b""

def _varint(data: bytes, pos: int):
    value=shift=0
    while pos<len(data) and shift<70:
        b=data[pos]; pos+=1; value|=(b&127)<<shift
        if not b&128: return value,pos
        shift+=7
    raise ValueError("invalid protobuf varint")

def parse_protobuf_fields(data: bytes):
    out=[]; pos=0
    while pos<len(data):
        key,pos=_varint(data,pos); number,wire=key>>3,key&7
        if not number: raise ValueError("invalid protobuf field")
        if wire==0: value,pos=_varint(data,pos)
        elif wire==1:
            if pos+8>len(data): raise ValueError("truncated fixed64")
            value=data[pos:pos+8]; pos+=8
        elif wire==2:
            size,pos=_varint(data,pos)
            if pos+size>len(data): raise ValueError("truncated field")
            value=data[pos:pos+size]; pos+=size
        elif wire==5:
            if pos+4>len(data): raise ValueError("truncated fixed32")
            value=data[pos:pos+4]; pos+=4
        else: raise ValueError(f"unsupported wire type {wire}")
        out.append((number,wire,value))
    return out

def _ip_payload(packet: bytes, linktype: int):
    if linktype==1:
        if len(packet)<14: return None
        off,etype=14,struct.unpack_from("!H",packet,12)[0]
        while etype in (0x8100,0x88A8,0x9100):
            if len(packet)<off+4:return None
            etype=struct.unpack_from("!H",packet,off+2)[0]; off+=4
        return packet[off:] if etype==0x0800 else None
    if linktype in (101,228): return packet if packet and packet[0]>>4==4 else None
    if linktype==113:
        return packet[16:] if len(packet)>=16 and struct.unpack_from("!H",packet,14)[0]==0x0800 else None
    return None

def _read_pcap(data: bytes):
    if len(data)<24: raise ValueError("PCAP file too short")
    endian_map={b"\xd4\xc3\xb2\xa1":"<",b"\xa1\xb2\xc3\xd4":">",b"\x4d\x3c\xb2\xa1":"<",b"\xa1\xb2\xc3\x4d":">"}
    if data[:4] not in endian_map: raise ValueError("Only classic PCAP is supported, not PCAPNG")
    endian=endian_map[data[:4]]; linktype=struct.unpack_from(endian+"IHHIIII",data,0)[6]
    pos=24; packets=[]
    while pos+16<=len(data):
        _sec,_frac,incl,_orig=struct.unpack_from(endian+"IIII",data,pos); pos+=16
        if incl>len(data)-pos: break
        ip=_ip_payload(data[pos:pos+incl],linktype); pos+=incl
        if ip is None or len(ip)<40 or ip[0]>>4!=4 or ip[9]!=6: continue
        ihl=(ip[0]&15)*4
        if len(ip)<ihl+20: continue
        src,dst=socket.inet_ntoa(ip[12:16]),socket.inet_ntoa(ip[16:20]); off=ihl
        sport,dport,seq=struct.unpack_from("!HHI",ip,off)
        thl=((struct.unpack_from("!H",ip,off+12)[0]>>12)&15)*4
        payload=ip[off+thl:]
        if payload: packets.append((src,sport,dst,dport,seq,payload))
    return packets

def _reassemble(segments: Iterable[tuple[int,bytes]]):
    ordered=sorted(segments,key=lambda x:x[0]); out=bytearray(); expected=None
    for seq,payload in ordered:
        if expected is None: expected=seq
        if seq+len(payload)<=expected: continue
        if seq<expected: payload=payload[expected-seq:]
        if seq>expected: raise ValueError(f"TCP stream gap: {seq-expected} bytes")
        out.extend(payload); expected=seq+len(payload)
    return bytes(out)

def extract_session(pcap_bytes: bytes) -> CapturedSession:
    """Prefer a real captured reconnect exchange; keep its request body in memory only."""
    flows={}
    for src,sp,dst,dp,seq,payload in _read_pcap(pcap_bytes):
        flows.setdefault((src,sp,dst,dp),[]).append((seq,payload))
    decoded={}
    for flow,segs in flows.items():
        try:
            frames=FrameDecoder().feed(_reassemble(segs))
            if frames: decoded[flow]=frames
        except (ValueError,ProtocolError):
            continue

    # The November 21 capture contains a genuine LoginReconnectC2S on a
    # second TCP connection. Use that exact client-generated protobuf body.
    for flow,frames in decoded.items():
        reconnect=next((f for f in frames if f.name=="LoginReconnectC2S"),None)
        notice=next((f for f in frames if f.name=="LoginNoticeC2S"),None)
        if reconnect is None or notice is None:
            continue
        nf={n:v for n,w,v in parse_protobuf_fields(notice.body)}
        account=nf.get(2,b"")
        if isinstance(account,bytes):
            account=account.decode("utf-8","strict")
        if not account:
            continue
        reverse=(flow[2],flow[3],flow[0],flow[1])
        token_frame=next((f for f in decoded.get(reverse,[]) if f.name=="LoginReconnectTokenKeyS2C"),None)
        account_uid=0
        token_key=""
        if token_frame:
            tf={n:v for n,w,v in parse_protobuf_fields(token_frame.body)}
            account_uid=int(tf.get(1,0)) if isinstance(tf.get(1,0),int) else 0
            token=tf.get(2,b"")
            if isinstance(token,bytes):
                try: token=token.decode("ascii")
                except UnicodeDecodeError: token=""
            token_key=token if isinstance(token,str) else ""
        return CapturedSession(
            account=account, account_uid=account_uid, token_key=token_key,
            server_id=int(nf.get(1,0)), host=flow[2], port=flow[3],
            reconnect_body=reconnect.body, notice_body=notice.body,
        )

    # Compatibility fallback for captures that contain only an initial login.
    for flow,frames in decoded.items():
        notice=next((f for f in frames if f.name=="LoginNoticeC2S"),None)
        if not notice: continue
        fields={n:v for n,w,v in parse_protobuf_fields(notice.body)}
        account=fields.get(2,b"")
        if not isinstance(account,bytes) or not account: continue
        account=account.decode("utf-8","strict")
        reverse=(flow[2],flow[3],flow[0],flow[1])
        token_frame=next((f for f in decoded.get(reverse,[]) if f.name=="LoginReconnectTokenKeyS2C"),None)
        if not token_frame: continue
        tf={n:v for n,w,v in parse_protobuf_fields(token_frame.body)}
        token=tf.get(2,b"")
        if isinstance(token,bytes): token=token.decode("ascii","strict")
        if tf.get(1) and token:
            return CapturedSession(account,int(tf[1]),token,int(fields.get(1,0)),flow[2],flow[3])
    raise ValueError("No usable login or reconnect session found in PCAP")

def extract_session_file(path: str | Path) -> CapturedSession:
    return extract_session(Path(path).read_bytes())
