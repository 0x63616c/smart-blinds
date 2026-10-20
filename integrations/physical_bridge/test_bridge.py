"""Real read-only HTTP -> sole owner -> localhost DTLS, no owner devices."""
from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import Mock
import json
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from integrations.telemetry_transport.client import decode
from integrations.telemetry_transport.test_telemetry import wire
from integrations.telemetry_transport.fixture import Peer, LIBRARY
from .service import Pairing, PhysicalBridge
from .server import PhysicalServer


TOKEN = "disposable-bridge-token-" + "x"*32


def pairing(p, device_id="blind-1"):
    return Pairing(device_id, "Fixture blind", "::1", p.port, p.identity, p.key, p.boot)


def await_state(bridge):
    until = time.monotonic()+3
    while time.monotonic() < until:
        state = bridge.state()
        if all(d["available"] for d in state["devices"]):
            return state
        time.sleep(.005)
    raise AssertionError("Read-only telemetry did not arrive")


class BridgeTests(unittest.TestCase):
    def test_literal_aliases_reject_before_any_owner_starts(self):
        original = Pairing("one", "Fixture", "::1", 5684, "test", b"x"*32, 1)
        for left, right in (("::1", "0:0:0:0:0:0:0:1"), ("127.0.0.1", "::ffff:127.0.0.1")):
            factory = Mock(side_effect=AssertionError("owner started before validation"))
            with self.subTest(left=left, right=right), self.assertRaises(ValueError):
                PhysicalBridge("aliases", [replace(original, host=left),
                    replace(original, device_id="two", host=right)], LIBRARY, factory=factory)
            factory.assert_not_called()

    def test_display_boundaries_and_first_failure_no_reconnect(self):
        now = [0]
        made, closed = [], []
        value = wire(); value["sent_us"] = "0000000000000000"
        observation = decode(json.dumps(value).encode(), boot=1, nonce=2, sent_host_us=0, received_us=0)
        class Session:
            def __init__(self, *args, **kwargs):
                made.append(threading.get_ident())
            def poll(self): return observation
            def close(self): closed.append(threading.get_ident())
        p = Pairing("one", "Fixture", "::1", 5684, "test", b"x"*32, 1)
        bridge = PhysicalBridge("boundaries", [p], LIBRARY, factory=Session, clock=lambda: now[0])
        try:
            await_state(bridge)
            for age, battery, source in ((60_000, True, True), (60_001, True, False),
                                          (1_800_000, True, False), (1_800_001, False, False)):
                now[0] = age*1000
                d = bridge.state()["devices"][0]
                self.assertEqual(d["battery_percent"] is not None, battery)
                self.assertEqual(d["usb_connected"] is not None, source)
                self.assertEqual(d["charging"] is not None, source)
                self.assertEqual(d["battery_sample_us"], "0000000000000000")
            self.assertEqual(len(made), 1)
        finally:
            bridge.close()
        self.assertEqual(made, closed)
        class Failed(Session):
            def poll(self): raise TimeoutError("disposable test")
        made.clear(); closed.clear()
        bridge = PhysicalBridge("failed", [p], LIBRARY, factory=Failed)
        try:
            until = time.monotonic()+1
            while not bridge.readers[0].failed and time.monotonic()<until:
                time.sleep(.001)
            for _ in range(20): self.assertFalse(bridge.state()["devices"][0]["available"])
            self.assertEqual(len(made), 1)
        finally:
            bridge.close()
        self.assertEqual(made, closed)

    def test_real_http_is_cache_only_and_all_commands_reject(self):
        with Peer() as peer:
            bridge = PhysicalBridge("physical-fixture", [pairing(peer)], LIBRARY)
            server = PhysicalServer(TOKEN, bridge, port=0)
            thread = threading.Thread(target=server.serve_forever); thread.start()
            try:
                state = await_state(bridge)
                self.assertEqual(state["mode"], "physical_read_only")
                self.assertEqual(state["devices"][0]["battery_percent"], 42.188)
                requests = peer.requests
                url = f"http://127.0.0.1:{server.server_port}"
                for _ in range(3):
                    with urlopen(Request(url+"/v2/state", headers={"Authorization": "Bearer "+TOKEN}), timeout=1) as r:
                        self.assertEqual(r.headers["Cache-Control"], "no-store")
                        self.assertFalse(json.load(r)["devices"][0]["charge_authorized"])
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(url+"/v1/move", data=b"{}", headers={"Authorization": "Bearer "+TOKEN}), timeout=1)
                self.assertEqual(error.exception.code, 405)
                error.exception.close()
                with self.assertRaises(HTTPError) as error:
                    urlopen(url+"/v2/state", timeout=1)
                self.assertEqual(error.exception.code, 401)
                error.exception.close()
                self.assertEqual(peer.requests, requests)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=1)

    def test_seven_explicit_peers_and_duplicate_owner_rejection(self):
        with ExitStack() as stack:
            peers = [stack.enter_context(Peer()) for _ in range(7)]
            selected = [pairing(p, f"blind-{i+1}") for i, p in enumerate(peers)]
            with self.assertRaises(ValueError):
                PhysicalBridge("duplicate", [selected[0], pairing(peers[0], "another")], LIBRARY)
            bridge = PhysicalBridge("seven-physical-fixtures", selected, LIBRARY)
            try:
                state = await_state(bridge)
                self.assertEqual(len(state["devices"]), 7)
                self.assertTrue(all(d["charging"] is False and d["usb_connected"] is True for d in state["devices"]))
                self.assertTrue(all(p.requests == 1 for p in peers))
                self.assertNotIn("group", state)
            finally:
                bridge.close()


if __name__ == "__main__":
    unittest.main()
