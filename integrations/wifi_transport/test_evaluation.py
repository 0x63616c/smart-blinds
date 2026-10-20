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

LIBRARY = Path(os.environ.get("SB_WIFI_LIBRARY", "work/wifi-transport-build/libsb_wifi.dylib"))

class Peer:
    def __init__(self):
        self.boot=secrets.randbits(64) or 1
        self.key=secrets.token_bytes(32)
        self.identity="disposable_wifi"
        with socket.socket(socket.AF_INET6,socket.SOCK_DGRAM) as s:
            s.bind(("::1",0));self.port=s.getsockname()[1]
        self.lib=_load(LIBRARY)
        self.lib.sb_wifi_peer_new.argtypes=[C.c_uint16,C.c_char_p,C.POINTER(C.c_uint8),C.c_uint64]
        self.lib.sb_wifi_peer_new.restype=C.c_void_p
        self.lib.sb_wifi_peer_free.argtypes=[C.c_void_p]
        self.lib.sb_wifi_peer_free.restype=None
        self.lib.sb_wifi_peer_loss.argtypes=[C.c_void_p]
        self.lib.sb_wifi_peer_loss.restype=None
        self.lib.sb_wifi_peer_requests.argtypes=[C.c_void_p]
        self.lib.sb_wifi_peer_requests.restype=C.c_uint
        k=(C.c_uint8*32).from_buffer_copy(self.key)
        try:self.handle=self.lib.sb_wifi_peer_new(self.port,self.identity.encode(),k,self.boot)
        finally:C.memset(k,0,32)
        if not self.handle:raise RuntimeError("Could not bind loopback fixture")
    def session(self,**kw):
        return Session(LIBRARY,"::1",self.port,self.identity,self.key,**kw)
    def __enter__(self):return self
    def __exit__(self,*_):self.lib.sb_wifi_peer_free(self.handle)

class EvaluationTests(unittest.TestCase):
    def test_real_dtls_clock_and_motion_disabled(self):
        with Peer() as p,p.session() as s:
            self.assertEqual(s.status().boot,p.boot)
            self.assertEqual(s.wake(p.boot,1),10000)
            readiness=s.qualify_clock(p.boot,1)
            self.assertTrue(readiness.clock_assessed)
            self.assertFalse(readiness.clock_model_validated)
            self.assertFalse(readiness.clock_qualified)
            self.assertFalse(readiness.motor_ready)
            self.assertEqual(s.handshakes,1)

    def test_second_controller_cannot_replace_owner(self):
        with Peer() as p,p.session() as first:
            first.status();first.wake(p.boot,1)
            with p.session(timeout_ms=300) as other:
                with self.assertRaises(TransportError):other.status()
            self.assertEqual(first.status().last_wake,1)
            self.assertEqual(first.handshakes,1)

    def test_old_boot_and_motion_routes_are_rejected(self):
        class RawMotionProbe(Session):
            _native_constructor="sb_motion_client_new"
        with Peer() as p,RawMotionProbe(LIBRARY,"::1",p.port,p.identity,p.key) as s:
            s.status()
            with s._lock:
                old_boot=(p.boot^1) or 2
                self.assertEqual(s._exchange(1,old_boot.to_bytes(8,"big")+(1).to_bytes(8,"big"))[0],128)
                self.assertEqual(s._exchange(2,p.boot.to_bytes(8,"big")+(1).to_bytes(8,"big"))[0],128)
                self.assertEqual(s._exchange(5,bytes(80))[0],163)
                self.assertEqual(s._exchange(6)[0],163)
            self.assertFalse(s.status().awake)
            s.wake(p.boot,1)
            with s._lock:
                self.assertEqual(s._exchange(5,bytes(80))[0],163)
                self.assertEqual(s._exchange(6)[0],163)

    def test_wrong_authentication_never_reaches_parser(self):
        with Peer() as p:
            for identity,key in [("wrong",p.key),(p.identity,secrets.token_bytes(32))]:
                with Session(LIBRARY,"::1",p.port,identity,key,timeout_ms=300) as s:
                    with self.assertRaises(TransportError):s.status()
                    with self.assertRaises(TransportError):s.status()
            self.assertEqual(p.lib.sb_wifi_peer_requests(p.handle),0)

    def test_replay_and_malformed_wake(self):
        with Peer() as p,WireFixture(p.port) as wire,Session(LIBRARY,"::1",wire.port,p.identity,p.key) as s:
            s.status();s.wake(p.boot,1)
            calls=p.lib.sb_wifi_peer_requests(p.handle)
            wire.inject();wire.inject(corrupt=True);time.sleep(.05)
            self.assertEqual(p.lib.sb_wifi_peer_requests(p.handle),calls)
            with s._lock:
                self.assertEqual(s._exchange(1,b"x"*15)[0],128)
                self.assertEqual(s._exchange(1,p.boot.to_bytes(8,"big")+(1).to_bytes(8,"big"))[0],128)
            self.assertEqual(s.status().last_wake,1)

    def test_network_loss_revokes_owner_without_reconnect(self):
        with Peer() as p,p.session() as s:
            s.status();s.wake(p.boot,1)
            p.lib.sb_wifi_peer_loss(p.handle);time.sleep(.02)
            with self.assertRaises(TransportError):s.status()
            with self.assertRaises(TransportError):s.status()
            with p.session(timeout_ms=300) as replacement:
                with self.assertRaises(TransportError):replacement.status()

if __name__=="__main__":unittest.main()
