"""Real loopback DTLS sessions with disposable keys; fixture clock is simulated."""
import concurrent.futures
import ctypes as C
import os
from pathlib import Path
import secrets
import socket
import time
import unittest

from integrations.thread_transport.wire_fixture import WireFixture
from integrations.thread_transport.client import ProtocolError, Rejected, Session, TransportError, _json, _load

LIBRARY = Path(os.environ.get("SB_THREAD_LIBRARY", "work/thread-transport-build/libsb_thread.dylib"))


def free_port():
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as sock:
        sock.bind(("::1", 0))
        return sock.getsockname()[1]


class Peer:
    def __init__(self, *, key=None, identity="disposable", boot=None, port=None):
        self.key = key or secrets.token_bytes(32)
        self.identity = identity
        self.boot = boot or secrets.randbits(64) or 1
        self.port = port or free_port()
        self.library = _load(LIBRARY)
        self.library.sb_test_peer_new.argtypes = [C.c_uint16, C.c_char_p, C.POINTER(C.c_uint8), C.c_uint64]
        self.library.sb_test_peer_new.restype = C.c_void_p
        self.library.sb_test_peer_free.argtypes = [C.c_void_p]
        self.library.sb_test_peer_free.restype = None
        self.library.sb_test_peer_clock.argtypes = [C.c_void_p, C.c_uint64]
        self.library.sb_test_peer_clock.restype = None
        self.library.sb_test_peer_shift_clock.argtypes = [C.c_void_p, C.c_int64]
        self.library.sb_test_peer_shift_clock.restype = None
        self.library.sb_test_peer_requests.argtypes = [C.c_void_p]
        self.library.sb_test_peer_requests.restype = C.c_uint
        value = (C.c_uint8 * 32).from_buffer_copy(self.key)
        try:
            self.handle = self.library.sb_test_peer_new(self.port, self.identity.encode(), value, self.boot)
        finally:
            C.memset(value, 0, 32)
        if not self.handle:
            raise RuntimeError("Loopback fixture could not bind")

    def session(self, **kwargs):
        return Session(LIBRARY, "::1", self.port, self.identity, self.key, **kwargs)

    def clock(self, ms):
        self.library.sb_test_peer_clock(self.handle, ms)

    def shift_clock(self, us):
        self.library.sb_test_peer_shift_clock(self.handle, us)

    @property
    def requests(self):
        return self.library.sb_test_peer_requests(self.handle)

    def close(self):
        if self.handle:
            self.library.sb_test_peer_free(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def raw(session, kind, body=b""):
    with session._lock:
        return session._exchange(kind, body)


def wake_body(boot, sequence):
    return boot.to_bytes(8, "big") + sequence.to_bytes(8, "big")


class TransportTests(unittest.TestCase):
    def test_real_handshake_persistent_session_and_wake_lifecycle(self):
        with Peer(boot=0xFEDCBA9876543210) as peer, peer.session() as session:
            status = session.status()
            self.assertEqual(status.boot, peer.boot)
            self.assertFalse(status.awake)
            self.assertEqual(session.handshakes, 1)
            self.assertEqual(session.wake(status.boot, 1), 10000)
            self.assertTrue(session.status().awake)
            # A fresh encrypted request cannot replay or extend an active window.
            self.assertEqual(raw(session, 1, wake_body(peer.boot, 1))[0], 128)
            self.assertEqual(raw(session, 1, wake_body(peer.boot, 2))[0], 128)
            peer.clock(10000)
            self.assertFalse(session.status().awake)
            self.assertEqual(raw(session, 1, wake_body(peer.boot, 2))[0], 128)
            peer.clock(15000)
            self.assertEqual(raw(session, 1, wake_body(peer.boot, 1))[0], 128)
            self.assertEqual(session.wake(peer.boot, 2), 10000)
            self.assertEqual(session.handshakes, 1)  # No subprocess/handshake per request.

    def test_encrypted_record_replay_and_corruption(self):
        with Peer() as peer, WireFixture(peer.port) as wire, Session(
            LIBRARY, "::1", wire.port, peer.identity, peer.key) as session:
            session.status()
            session.wake(peer.boot, 1)
            calls, responses = peer.requests, wire.responses
            wire.inject()  # Exact DTLS epoch/sequence/ciphertext replay.
            time.sleep(0.05)
            self.assertEqual(peer.requests, calls)
            self.assertEqual(wire.responses, responses)  # No duplicate CoAP ACK either.
            wire.inject(corrupt=True)
            time.sleep(0.05)
            self.assertEqual(peer.requests, calls)

    def test_wrong_key_never_reaches_resource(self):
        with Peer() as peer, Session(LIBRARY, "::1", peer.port, peer.identity,
                                      secrets.token_bytes(32), timeout_ms=500) as session:
            with self.assertRaises(TransportError):
                session.status()
            self.assertEqual(session.handshakes, 0)
            self.assertEqual(peer.requests, 0)
            with self.assertRaises(TransportError):
                session.status()  # No automatic reconnect or retry.

    def test_wrong_identity_rejected_even_with_same_key(self):
        with Peer() as peer, Session(LIBRARY, "::1", peer.port, "wrong", peer.key,
                                      timeout_ms=500) as session:
            with self.assertRaises(TransportError):
                session.status()
            self.assertEqual(peer.requests, 0)

    def test_server_schema_and_boot_rejection(self):
        with Peer() as peer, peer.session() as session:
            session.status()
            for payload in (b"", b"x" * 15, b"x" * 17, wake_body(peer.boot ^ 1, 1), wake_body(peer.boot, 0)):
                self.assertEqual(raw(session, 1, payload)[0], 128)
            self.assertEqual(raw(session, 0, b"x")[0], 128)
            self.assertEqual(session.status().last_wake, 0)
            with self.assertRaises(ProtocolError):
                session.wake(peer.boot ^ 1, 1)

    def test_timeout_discards_queued_requests_and_requires_fresh_session(self):
        port, key = free_port(), secrets.token_bytes(32)
        with Session(LIBRARY, "::1", port, "disposable", key, timeout_ms=200) as failed:
            with self.assertRaises(TransportError):
                failed.status()
            with Peer(port=port, key=key) as peer:
                with self.assertRaises(TransportError):
                    failed.status()
                time.sleep(0.05)
                self.assertEqual(peer.requests, 0)
                with peer.session() as fresh:
                    self.assertEqual(fresh.status().boot, peer.boot)
                    self.assertEqual(peer.requests, 1)

    def test_seven_independent_sessions(self):
        peers = [Peer(boot=100 + i, identity=f"blind_{i}") for i in range(7)]
        try:
            def exchange(peer):
                with peer.session() as session:
                    status = session.status()
                    session.wake(status.boot, 1)
                    return session.status(), session.handshakes
            with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
                results = list(pool.map(exchange, peers))
            self.assertEqual([status.boot for status, _ in results], list(range(100, 107)))
            self.assertTrue(all(status.awake and count == 1 for status, count in results))
        finally:
            for peer in peers:
                peer.close()

    def test_reboot_requires_recovery_and_rejects_old_boot(self):
        peer = Peer(boot=111)
        session = peer.session(timeout_ms=500)
        try:
            session.status()
            session.wake(111, 1)
            port, key = peer.port, peer.key
            peer.close()
            with Peer(port=port, key=key, boot=222) as rebooted:
                with self.assertRaises(TransportError):
                    session.status()
                with rebooted.session() as fresh:
                    self.assertEqual(fresh.status().boot, 222)
                    self.assertEqual(raw(fresh, 1, wake_body(111, 2))[0], 128)
                    self.assertEqual(fresh.wake(222, 1), 10000)
        finally:
            session.close()
            peer.close()

    def test_typed_boundary_rejects_ambiguous_values(self):
        for value in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]', b'\xff'):
            with self.assertRaises(ProtocolError):
                _json(value)
        with Peer() as peer, peer.session() as session:
            with self.assertRaises(ProtocolError):
                session.wake(peer.boot, 1)  # No status/boot negotiation yet.
            status = session.status()
            for invalid in (True, 0, -1, 1 << 64):
                with self.assertRaises(ValueError):
                    session.wake(status.boot, invalid)
            session.wake(status.boot, 1)
            with self.assertRaises(ProtocolError):
                session.wake(status.boot, 1)


if __name__ == "__main__":
    unittest.main()
