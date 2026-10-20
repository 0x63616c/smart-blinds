"""Real loopback DTLS; exact Wi-Fi policy/parser, synthetic network and no GPIO."""
import ctypes as C
import os
from pathlib import Path
import secrets
import socket
import time
import unittest

from integrations.thread_transport.client import Session, TransportError, _load
from integrations.thread_transport.wire_fixture import WireFixture
from .client import TelemetrySession, ProtocolError, decode

LIBRARY = Path(os.environ.get("SB_TELEMETRY_LIBRARY", "work/telemetry-build/libsb_telemetry.dylib"))

class Peer:
    def __init__(self):
        self.boot=secrets.randbits(64) or 1
        self.key=secrets.token_bytes(32)
        self.identity="disposable_wifi"
        with socket.socket(socket.AF_INET6,socket.SOCK_DGRAM) as s:
            s.bind(("::1",0));self.port=s.getsockname()[1]
        self.lib=_load(LIBRARY)
        self.lib.sb_telemetry_peer_new.argtypes=[C.c_uint16,C.c_char_p,C.POINTER(C.c_uint8),C.c_uint64]
        self.lib.sb_telemetry_peer_new.restype=C.c_void_p
        self.lib.sb_telemetry_peer_free.argtypes=[C.c_void_p]
        self.lib.sb_telemetry_peer_free.restype=None
        self.lib.sb_telemetry_peer_loss.argtypes=[C.c_void_p]
        self.lib.sb_telemetry_peer_loss.restype=None
        self.lib.sb_telemetry_peer_requests.argtypes=[C.c_void_p]
        self.lib.sb_telemetry_peer_requests.restype=C.c_uint
        k=(C.c_uint8*32).from_buffer_copy(self.key)
        try:self.handle=self.lib.sb_telemetry_peer_new(self.port,self.identity.encode(),k,self.boot)
        finally:C.memset(k,0,32)
        if not self.handle:raise RuntimeError("Could not bind loopback fixture")
    def session(self,**kw):
        return TelemetrySession(LIBRARY,"::1",self.port,self.identity,self.key,expected_boot=self.boot,**kw)
    def mode(self,value):
        self.lib.sb_telemetry_peer_mode.argtypes=[C.c_void_p,C.c_uint]
        self.lib.sb_telemetry_peer_mode(self.handle,value)
    @property
    def requests(self):
        return self.lib.sb_telemetry_peer_requests(self.handle)
    def __enter__(self):return self
    def __exit__(self,*_):self.lib.sb_telemetry_peer_free(self.handle)

