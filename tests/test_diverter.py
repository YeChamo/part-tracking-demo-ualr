import unittest

from app.diverter import plan, preview, validate_timing


class DiverterPlannerTests(unittest.TestCase):
    def setUp(self):
        self.settings = {"program_id": "reject-1", "pass_program_id": "pass-1", "return_program_id": "return-1",
                         "belt_speed": 200, "distance_mm": 100, "delay_ms": 50,
                         "lead_ms": 200, "move_ms": 150, "bottle_length_mm": 100,
                         "clearance_ms": 100, "hold_ms": 500}

    def test_reject_plan_uses_exact_travel_lead_and_clearance(self):
        result = plan(self.settings, True, 10)
        self.assertEqual(result["program_id"], "reject-1")
        self.assertEqual(result["repeats"], 1)
        self.assertEqual(result["return_program_id"], "return-1")
        self.assertEqual(result["hold_seconds"], .5)
        self.assertAlmostEqual(result["arrival_at"], 10.55)
        self.assertAlmostEqual(result["due_at"], 10.35)
        # 100 mm bottle / 200 mm/s + 100 ms margin = 600 ms.
        self.assertAlmostEqual(result["clearance_at"], 11.15)

    def test_pass_and_reject_can_each_repeat_primary_cycles(self):
        settings = dict(self.settings, reject_cycles=2, pass_cycles=3)
        reject, passed = plan(settings, True, 10), plan(settings, False, 10)
        self.assertEqual((reject["program_id"], reject["repeats"]), ("reject-1", 2))
        self.assertEqual((passed["program_id"], passed["repeats"]), ("pass-1", 3))
        for key in ("arrival_at", "due_at", "clearance_at", "hold_seconds", "return_program_id"):
            self.assertEqual(reject[key], passed[key])

    def test_pass_no_action_suppresses_return(self):
        result = plan(dict(self.settings, pass_program_id=""), False, 10)
        self.assertEqual(result["program_id"], "")
        self.assertEqual(result["return_program_id"], "")

    def test_primary_program_alone_is_whole_saved_cycle(self):
        result = plan(dict(self.settings, return_program_id=""), True, 10)
        self.assertEqual(result["program_id"], "reject-1")
        self.assertEqual(result["return_program_id"], "")
        self.assertIn("own hold and return", preview(dict(self.settings, return_program_id="")))

    def test_defaults_plan_without_arming_and_use_default_bottle_length(self):
        result = plan({}, False, 10)
        self.assertEqual(result["arrival_at"], 10)
        self.assertEqual(result["due_at"], 10)
        self.assertAlmostEqual(result["clearance_at"], 10.5)
        self.assertEqual(result["hold_seconds"], .5)
        self.assertEqual(result["repeats"], 1)
        self.assertEqual(result["program_id"], "")
        with self.assertRaisesRegex(ValueError, "lead"):
            validate_timing({})

    def test_validate_timing_allows_exact_move_and_travel_boundaries(self):
        settings = dict(self.settings, distance_mm=30, delay_ms=0, lead_ms=150, move_ms=150)
        self.assertIsNone(validate_timing(settings))
        self.assertAlmostEqual(plan(settings, True, 10)["due_at"], 10)

    def test_lead_shorter_than_move_is_rejected_only_when_arming(self):
        settings = dict(self.settings, lead_ms=100)
        self.assertEqual(plan(settings, True, 10)["program_id"], "reject-1")
        with self.assertRaisesRegex(ValueError, "move time"):
            validate_timing(settings)

    def test_travel_shorter_than_lead_is_not_clamped(self):
        settings = dict(self.settings, distance_mm=10, delay_ms=0, lead_ms=200)
        self.assertAlmostEqual(plan(settings, True, 10)["due_at"], 9.85)
        with self.assertRaisesRegex(ValueError, "travel time"):
            validate_timing(settings)

    def test_negative_nonfinite_or_wrong_numeric_types_rejected(self):
        nonnegative = ("distance_mm", "delay_ms", "lead_ms", "move_ms", "clearance_ms", "hold_ms")
        positive = ("belt_speed", "bottle_length_mm")
        for key in nonnegative + positive:
            for value in (-1, float("nan"), float("inf"), "bad", None, True):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValueError):
                        plan(dict(self.settings, **{key: value}), True, 10)
            if key in positive:
                with self.subTest(key=key, value=0):
                    with self.assertRaises(ValueError):
                        plan(dict(self.settings, **{key: 0}), True, 10)

    def test_cycle_count_is_integer_one_to_ten_for_both_outcomes(self):
        for key in ("reject_cycles", "pass_cycles"):
            for value in (0, -1, 11, 1.5, float("nan"), float("inf"), True, None, "two"):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValueError):
                        plan(dict(self.settings, **{key: value}), True, 10)
        result = plan(dict(self.settings, reject_cycles="2"), True, 10)
        self.assertEqual(result["repeats"], 2)

    def test_program_ids_match_saved_ethermotion_id_syntax(self):
        for key in ("program_id", "pass_program_id", "return_program_id"):
            for value in ("two words", "../reject", "x" * 65, "test?", None, 123):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValueError):
                        plan(dict(self.settings, **{key: value}), True, 10)
        result = plan(dict(self.settings, program_id="  Route_A-2  "), True, 10)
        self.assertEqual(result["program_id"], "Route_A-2")

    def test_invalid_capture_timestamp_and_overflow_rejected(self):
        for value in (-1, float("nan"), float("inf"), None, True):
            with self.subTest(captured=value):
                with self.assertRaises(ValueError):
                    plan(self.settings, True, value)
        with self.assertRaisesRegex(ValueError, "finite"):
            plan(dict(self.settings, belt_speed=1e-300, distance_mm=1e308), True, 10)
        with self.assertRaisesRegex(ValueError, "finite"):
            plan(dict(self.settings, belt_speed=1, distance_mm=1e308), True, 1e308)

    def test_preview_reports_delay_clearance_and_both_return_deadlines(self):
        text = preview(self.settings)
        self.assertIn("Trigger delay: 350 ms", text)
        self.assertIn("600 ms after arrival", text)
        self.assertIn("1150 ms after detection", text)
        self.assertIn("clear AND", text)
        self.assertIn("500 ms after each primary cycle completes", text)
        self.assertNotIn("Cannot arm", text)

    def test_preview_explains_impossible_timing(self):
        text = preview(dict(self.settings, distance_mm=10, delay_ms=0))
        self.assertIn("Trigger delay: -150 ms", text)
        self.assertIn("Cannot arm", text)

    def test_planning_does_not_mutate_settings(self):
        before = dict(self.settings)
        plan(self.settings, True, 10)
        validate_timing(self.settings)
        preview(self.settings)
        self.assertEqual(self.settings, before)


if __name__ == "__main__":
    unittest.main()
