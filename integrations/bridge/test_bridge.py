import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from integrations.bridge.auth import Channel, PacketError
from integrations.bridge.server import SimulatorServer
from integrations.bridge.simulator import Simulation


class AuthenticationTests(unittest.TestCase):
    def pair(self, boot=123, session=b"s" * 16):
        return (Channel(b"k" * 32, session, boot, "blind-1", coordinator=True),
                Channel(b"k" * 32, session, boot, "blind-1", coordinator=False))

    def test_authentication_replay_direction_and_tampering(self):
        sender, receiver = self.pair()
        packet = sender.encode("stop", {"sequence": 7}, 1000)
        with self.assertRaises(PacketError):
            sender.decode(packet, 1000)  # reflection
        corrupted = packet[:-1] + bytes([packet[-1] ^ 1])
        with self.assertRaises(PacketError):
            receiver.decode(corrupted, 1000)
        self.assertEqual(receiver.decode(packet, 1000), ("stop", {"sequence": 7}))
        with self.assertRaises(PacketError):
            receiver.decode(packet, 1001)

    def test_sessions_boots_and_delayed_commands(self):
        sender, _ = self.pair()
        packet = sender.encode("prepare", {}, 1000)
        for boot, session in ((124, b"s" * 16), (123, b"t" * 16)):
            _, receiver = self.pair(boot, session)
            with self.assertRaises(PacketError):
                receiver.decode(packet, 1000)
        _, receiver = self.pair()
        with self.assertRaises(PacketError):
            receiver.decode(packet, 1251)

    def test_uncertainty_bound_and_limits(self):
        sender, receiver = self.pair()
        self.assertEqual(receiver.decode(sender.encode("report", {}, 1010), 1000,
                                         clock_error_ms=10), ("report", {}))
        with self.assertRaises(PacketError):
            sender.encode("report", {"height": float("nan")}, 1000)
        with self.assertRaises(PacketError):
            sender.encode("report", {"data": "x" * 1500}, 1000)


class SimulationTests(unittest.TestCase):
    def advance(self, sim, until):
        for now in range(sim.now + 10, until + 1, 10):
            sim.tick(now)

    def test_seven_blinds_end_at_same_height_and_not_same_percentage(self):
        sim = Simulation(1000)
        sim.move(50)
        self.advance(sim, 50000)
        state = sim.state()
        self.assertEqual(state["group"]["phase"], "complete")
        self.assertEqual({d["height_mm"] for d in state["devices"]}, {1030})
        self.assertGreater(len({d["position"] for d in state["devices"]}), 1)
        self.assertEqual(state["group"]["position"], 50)

    def test_lost_member_stops_and_cannot_rejoin_old_move(self):
        sim = Simulation(1000)
        sim.move(50)
        self.advance(sim, 6000)
        sim.nodes["blind-3"].online = False
        self.advance(sim, 7000)
        self.assertEqual(sim.job.phase.value, "aborted")
        self.assertEqual(sim.nodes["blind-3"].fault, "lease_expired")
        stopped = {n.device_id: n.height for n in sim.nodes.values()}
        sim.nodes["blind-3"].online = True
        self.advance(sim, 9000)
        self.assertEqual({n.device_id: n.height for n in sim.nodes.values()}, stopped)

    def test_alignment_is_explicit_and_individual_full_open_is_separate(self):
        sim = Simulation(1000)
        sim.nodes["blind-1"].height = 400
        with self.assertRaisesRegex(ValueError, "needs_alignment"):
            sim.move(50)
        self.assertIsNone(sim.state()["group"]["position"])
        sim.move(50, align=True)
        self.advance(sim, 50000)
        self.assertEqual(sim.state()["group"]["position"], 50)
        sim.move(100, device_id="blind-7")
        self.advance(sim, 120000)
        self.assertEqual(sim.nodes["blind-7"].height, 2180)
        self.assertIsNone(sim.state()["group"]["position"])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = SimulatorServer("test-token-" + "z" * 32, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def request(self, path, body=None, token=None):
        req = Request(f"http://127.0.0.1:{self.server.server_port}{path}",
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={"Authorization": "Bearer " + (token or self.server.token),
                               "Content-Type": "application/json"})
        with urlopen(req, timeout=2) as response:
            return response.status, json.load(response)

    def test_real_loopback_http_requires_token_and_reports_simulation(self):
        with self.assertRaises(HTTPError) as error:
            self.request("/v1/state", token="wrong")
        self.assertEqual(error.exception.code, 401)
        error.exception.close()
        code, state = self.request("/v1/state")
        self.assertEqual((code, state["mode"], len(state["devices"])), (200, "simulation", 7))
        self.assertEqual(self.request("/v1/move", {"target": "room", "position": 50, "align": False})[0], 202)
        self.assertEqual(self.request("/v1/stop", {})[0], 202)


if __name__ == "__main__":
    unittest.main()
