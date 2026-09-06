import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "simulator.py"
spec = importlib.util.spec_from_file_location("stageguard_simulator", MODULE_PATH)
sim = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(sim)


class SimulationStateTests(unittest.TestCase):
    def test_fault_fixture_has_expected_four_evidence_classes(self):
        state = sim.SimulationState(start_faulted=True)
        state.frames_dropped["cam-3"] = 20.0
        text = state.prometheus_text()
        self.assertIn('feed_id="cam-3"} 20.', text)
        self.assertIn('feed_id="cam-1"} 0.', text)
        self.assertIn('uplink="uplink-b"} 18.0', text)
        self.assertIn('feed_id="cam-3"} 41.0', text)
        self.assertIn('feed_id="cam-3"} 37.0', text)

    def test_healthy_fixture_clears_packet_loss_and_counter_growth(self):
        state = sim.SimulationState(start_faulted=False)
        text = state.prometheus_text()
        self.assertIn('uplink="uplink-b"} 0.3', text)
        self.assertIn('scenario="uplink-b-packet-loss"} 0', text)

    def test_reset_is_replayable(self):
        state = sim.SimulationState(start_faulted=True)
        state.frames_dropped["cam-3"] = 99.0
        state.reset()
        snap = state.snapshot()
        self.assertFalse(snap["faulted"])
        self.assertEqual(snap["frames_dropped"]["cam-3"], 0.0)
        state.set_fault(True)
        self.assertTrue(state.snapshot()["faulted"])


if __name__ == "__main__":
    unittest.main()
