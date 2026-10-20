"""Checks for phase accounting and previously published energy examples."""
import unittest

from run_checks import energy_budget, split_load_scenario


class EnergyTests(unittest.TestCase):
    def setUp(self):
        self.args = dict(usable_wh=86.4, pack_v=10.8, motion_s=305.8,
                         preflight_s=20, motor_a=1.5, logic_v=3.3, awake_ma=150,
                         efficiency=0.9, idle_ma=0.5)

    def test_published_split_load_example(self):
        row = split_load_scenario(**self.args)
        self.assertAlmostEqual(row["estimated_days"], 55.56, places=2)
        self.assertAlmostEqual(row["motor_budget"][0]["maximum_motor_branch_average_a"], 1.375, places=3)
        self.assertAlmostEqual(row["motor_budget"][1]["maximum_motor_branch_average_a"], 0.851, places=3)

    def test_service_replaces_idle_instead_of_double_counting(self):
        baseline = split_load_scenario(**self.args)
        row = split_load_scenario(**self.args, service_period_s=3, service_duration_ms=10)
        self.assertAlmostEqual(row["awake_seconds_per_day"] + row["idle_seconds_per_day"], 86400)
        self.assertAlmostEqual(baseline["idle_seconds_per_day"] - row["idle_seconds_per_day"],
                               row["additional_service_seconds_per_day"])
        # Independent watt-seconds difference: 0.55 W awake versus 0.0054 W asleep.
        self.assertAlmostEqual(row["daily_wh"] - baseline["daily_wh"],
                               (0.55 - 0.0054) * row["additional_service_seconds_per_day"] / 3600)

    def test_continuous_awake_and_impossible_target(self):
        row = split_load_scenario(**self.args, service_period_s=0.1, service_duration_ms=100)
        self.assertEqual(row["idle_seconds_per_day"], 0)
        self.assertAlmostEqual(row["awake_logic_wh_per_day"], 13.2)
        self.assertFalse(row["motor_budget"][0]["nonmotor_loads_fit_budget"])
        self.assertEqual(row["motor_budget"][0]["maximum_motor_branch_average_a"], 0)

    def test_invalid_inputs_and_zero_load(self):
        for changes in (dict(motion_s=86401), dict(efficiency=0),
                        dict(awake_ma=float("nan")), dict(service_period_s=0),
                        dict(service_period_s=1, service_duration_ms=1001)):
            with self.assertRaises(ValueError):
                split_load_scenario(**dict(self.args, **changes))
        zero = split_load_scenario(**dict(self.args, motion_s=0, preflight_s=0, awake_ma=0, idle_ma=0))
        self.assertIsNone(zero["estimated_days"])
        self.assertIsNone(zero["motor_budget"][0]["maximum_motor_branch_average_a"])

    def test_two_current_definitions_remain_distinct(self):
        result = energy_budget()
        whole = next(row for row in result["scenarios"]
                     if row["total_moving_seconds_per_day"] == 305.8
                     and row["mean_pack_current_while_moving_a"] == 1.5 and row["pack_idle_ma"] == 0.5)
        self.assertEqual(whole["estimated_days"], 57.4)
        self.assertLess(result["split_load_planning"]["baseline"]["estimated_days"], whole["estimated_days"])


if __name__ == "__main__":
    unittest.main()
