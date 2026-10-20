"""Native DTLS + exact endpoint; all sensor values are explicitly synthetic."""
from copy import deepcopy
import json
import secrets
import time
import unittest

from integrations.thread_transport.client import TransportError, Rejected, _now_us
from integrations.thread_transport.wire_fixture import WireFixture
from .client import decode, ProtocolError, TelemetrySession
from .fixture import Peer, LIBRARY


def wire():
    return {
        "schema": 1, "boot": "0000000000000001", "nonce": "0000000000000002", "sent_us": "00000000000f4240",
        "battery": {"sample_us": "0000000000000000", "bus_epoch": 1, "serial": 1,
                    "pack": "000000000000004d", "soc_pct": 42.188, "state": "retained"},
        "charger": {"sample_us": "0000000000000000", "bus_epoch": 1, "state": "not_charging", "input_present": True},
        "pd": {"sample_us": "0000000000000000", "bus_epoch": 1, "epoch": 1, "serial": 1,
               "state": "policy_observed", "current_ma": 2500, "attached": True},
        "pending": False, "fault": {"kind": "none", "code": 0}, "charge_authorized": False,
    }


class ParserTests(unittest.TestCase):
    def test_observation_age_includes_original_zero_stamp_rtt_and_host_elapsed(self):
        value = decode(json.dumps(wire()).encode(), boot=1, nonce=2, sent_host_us=100, received_us=10101)
        self.assertEqual(value.display(110102)["battery"]["age_ms"], 1112)
        self.assertEqual(value.display(110102)["battery"]["sample_us"], "0000000000000000")
        modified = value.display(110102)
        modified["battery"]["soc_pct"] = 99
        self.assertEqual(value.display(110102)["battery"]["soc_pct"], 42.188)
        with self.assertRaises(ProtocolError):
            value.display(100)

    def test_malformed_and_inconsistent_schema_rejected(self):
        changes = [
            lambda x: x.update(schema=True), lambda x: x.update(ready=True),
            lambda x: x.update(boot="0000000000000003"), lambda x: x.update(nonce="0000000000000003"),
            lambda x: x.update(charge_authorized=True), lambda x: x.update(pending=True),
            lambda x: x["battery"].update(soc_pct=float("nan")),
            lambda x: x["battery"].update(state="absent"),
            lambda x: x["battery"].update(sample_us="ffffffffffffffff"),
            lambda x: x["charger"].update(state="unknown"),
            lambda x: x["pd"].update(current_ma=1500),
            lambda x: x["pd"].update(state="detached"), lambda x: x["pd"].update(attached=False),
            lambda x: x["fault"].update(kind="charger", code=4),
        ]
        for mutate in changes:
            value = wire(); mutate(value)
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                decode(json.dumps(value).encode(), boot=1, nonce=2, sent_host_us=100, received_us=110)
        with self.assertRaises(ProtocolError):
            decode(b'{"schema":1,"schema":1}', boot=1, nonce=2, sent_host_us=100, received_us=110)


class NativeTests(unittest.TestCase):
    def test_one_handshake_original_observation_survives_idle(self):
        with Peer() as p, p.session() as s:
            first = s.poll().display(_now_us())
            time.sleep(.03)
            second = s.poll().display(_now_us())
            self.assertEqual(first["battery"]["sample_us"], second["battery"]["sample_us"])
            self.assertEqual(first["battery"]["serial"], second["battery"]["serial"])
            self.assertGreater(second["battery"]["age_ms"], first["battery"]["age_ms"])
            self.assertEqual(s._handle.handshakes, 1)
            self.assertFalse(second["charge_authorized"])
            self.assertFalse(hasattr(s, "wake"))
            # Native allowlist is independent of the Python wrapper.
            with s._handle._lock, self.assertRaises(TransportError):
                s._handle._exchange(1, p.boot.to_bytes(8, "big")+(1).to_bytes(8, "big"))
            self.assertEqual(p.requests, 2)

    def test_pending_and_fault_retain_history_but_remove_current_presentation(self):
        with Peer() as p, p.session() as s:
            original = s.poll().display(_now_us())
            p.mode(1)
            pending = s.poll().display(_now_us())
            self.assertTrue(pending["pending"])
            self.assertIsNone(pending["charger"]["input_present"])
            self.assertEqual(pending["pd"]["state"], "unavailable")
            self.assertEqual(pending["battery"]["sample_us"], original["battery"]["sample_us"])
            p.mode(2)
            fault = s.poll().display(_now_us())
            self.assertEqual(fault["battery"]["state"], "invalid")
            self.assertEqual(fault["fault"], {"kind": "charger", "code": 4})

    def test_attached_source_can_be_blocked_before_charger(self):
        with Peer() as p, p.session() as s:
            p.mode(4)
            value = s.poll().display(_now_us())
            self.assertTrue(value["pd"]["attached"])
            self.assertFalse(value["charger"]["input_present"])
            self.assertFalse(value["charge_authorized"])

    def test_future_sample_and_cleared_first_fault_close_session(self):
        for bad_mode in (3, 0):
            with self.subTest(mode=bad_mode), Peer() as p, p.session() as s:
                if bad_mode == 0:
                    p.mode(2); s.poll()
                p.mode(bad_mode)
                with self.assertRaises(ProtocolError):
                    s.poll()
                calls = p.requests
                with self.assertRaises(TransportError):
                    s.poll()
                self.assertEqual(p.requests, calls)

    def test_wrong_auth_and_boot_never_auto_recovers(self):
        with Peer() as p:
            for identity, key in (("wrong", p.key), (p.identity, secrets.token_bytes(32))):
                with TelemetrySession(LIBRARY, "::1", p.port, identity, key, expected_boot=p.boot, timeout_ms=200) as s:
                    with self.assertRaises(TransportError):
                        s.poll()
                    with self.assertRaises(TransportError):
                        s.poll()
            self.assertEqual(p.requests, 0)
        with Peer() as p, TelemetrySession(LIBRARY, "::1", p.port, p.identity, p.key,
                                           expected_boot=(p.boot ^ 1) or 2) as s:
            with self.assertRaises(Rejected):
                s.poll()
            calls = p.requests
            with self.assertRaises(TransportError):
                s.poll()
            self.assertEqual(calls, p.requests)

    def test_second_owner_replay_and_corruption_cannot_change_observation(self):
        with Peer() as p, WireFixture(p.port) as wire, TelemetrySession(
                LIBRARY, "::1", wire.port, p.identity, p.key, expected_boot=p.boot) as first:
            first.poll()
            calls = p.requests
            wire.inject(); wire.inject(corrupt=True); time.sleep(.03)
            self.assertEqual(calls, p.requests)
            with p.session(timeout_ms=200) as second:
                with self.assertRaises(TransportError):
                    second.poll()
            self.assertEqual(first.poll()._wire["battery"]["state"], "retained")


if __name__ == "__main__":
    unittest.main()
