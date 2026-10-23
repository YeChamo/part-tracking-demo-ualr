import math
import unittest

from app.tracking import BottleTracker, TrackingConfig


def bottle(x, width=60):
    return (x, 100, x + width, 280)


class TrackingTests(unittest.TestCase):
    def feed(self, tracker, x, t, reasons=None, moving=True):
        return tracker.update([bottle(x)], [reasons or []], t, 1000, 400, moving)

    def test_ltr_leading_edge_and_exactly_one_decision(self):
        tracker = BottleTracker()
        output = []
        for n, x in enumerate(range(180, 901, 30)):
            tracks, decisions = self.feed(tracker, x, n * 0.1)
            output.extend(decisions)
            if x == 750:
                self.assertEqual(len(decisions), 1)  # Leading edge 810; center 780.
                self.assertFalse(decisions[0].bad)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0].id, 1)
        self.assertTrue(tracks[0].decided)

    def test_rtl_mirrors_entry_and_leading_edge(self):
        tracker = BottleTracker(TrackingConfig(direction="rtl"))
        output = []
        for n, x in enumerate(range(760, 39, -30)):
            _, decisions = self.feed(tracker, x, n * 0.1)
            output.extend(decisions)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0].bbox[0], 190)

    def test_early_reject_clears_when_current_color_is_correct_at_line(self):
        tracker = BottleTracker()
        for n, x in enumerate(range(180, 751, 30)):
            tracks, decisions = self.feed(tracker, x, n * 0.1, ["Color: red (divert)"] if n < 19 else [])
        self.assertEqual(tracks[0].id, 1)
        self.assertFalse(tracks[0].bad)
        self.assertEqual(tracks[0].reasons, [])
        self.assertFalse(decisions[0].bad)
        self.assertEqual(decisions[0].reasons, [])

    def test_each_fresh_inspection_replaces_old_reasons_after_dropout(self):
        tracker = BottleTracker()
        self.feed(tracker, 180, 0, ["Missing cap"])
        self.feed(tracker, 210, 0.1, ["Missing cap"])
        tracks, _ = self.feed(tracker, 240, 0.2)
        self.assertFalse(tracks[0].bad)
        tracks, _ = self.feed(tracker, 270, 0.3, ["Color: red (divert)"])
        self.assertTrue(tracks[0].bad)
        self.assertEqual(tracks[0].reasons, ["Color: red (divert)"])
        tracker.update([], [], 0.4, 1000, 400)
        tracks, _ = self.feed(tracker, 330, 0.5)
        self.assertFalse(tracks[0].bad)
        self.assertEqual(tracks[0].reasons, [])
        self.assertEqual(tracks[0].id, 1)

    def test_unknown_inspection_fails_closed_immediately(self):
        for reason in ("Inspection unavailable: camera failed", "Unknown color"):
            with self.subTest(reason=reason):
                tracker = BottleTracker()
                tracks, _ = self.feed(tracker, 180, 0, [reason])
                self.assertTrue(tracks[0].bad)
                self.assertEqual(tracks[0].reasons, [reason])

    def test_current_mismatch_at_crossing_diverts_without_historical_reasons(self):
        for reason in ("Color: red (divert)", "Cap differs from taught bottle", "Unknown color"):
            with self.subTest(reason=reason):
                tracker = BottleTracker()
                for n, x in enumerate(range(180, 721, 30)):
                    self.feed(tracker, x, n * 0.1)
                tracks, decisions = self.feed(tracker, 750, 1.9, [reason])
                self.assertEqual(len(decisions), 1)
                self.assertTrue(decisions[0].bad)
                self.assertTrue(tracks[0].bad)
                self.assertEqual(decisions[0].reasons, [reason])

    def test_initial_unknown_can_recover_on_the_crossing_frame(self):
        for reason in ("Unknown color", "Inspection unavailable: color model warming up"):
            with self.subTest(reason=reason):
                tracker = BottleTracker()
                for n, x in enumerate(range(180, 751, 30)):
                    tracks, decisions = self.feed(tracker, x, n * 0.1, [reason] if x < 750 else [])
                self.assertEqual(tracks[0].id, 1)
                self.assertEqual(len(decisions), 1)
                self.assertFalse(decisions[0].bad)
                self.assertEqual(decisions[0].reasons, [])

    def test_color_change_after_crossing_cannot_emit_another_decision(self):
        tracker = BottleTracker()
        outputs = []
        for n, x in enumerate(range(180, 901, 30)):
            _, decisions = self.feed(tracker, x, n * 0.1, ["Color: red (divert)"] if x >= 780 else [])
            outputs.extend(decisions)
        self.assertEqual(len(outputs), 1)
        self.assertFalse(outputs[0].bad)
        self.assertEqual(outputs[0].reasons, [])

    def test_transient_upstream_noise_clears_before_crossing(self):
        tracker = BottleTracker()
        for n, x in enumerate(range(180, 751, 30)):
            _, decisions = self.feed(tracker, x, n * 0.1, ["Color: blue (divert)"] if n == 2 else [])
        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0].bad)
        self.assertEqual(decisions[0].reasons, [])

    def test_dropouts_never_generate_predictions_as_decisions(self):
        tracker = BottleTracker()
        for n, x in enumerate(range(180, 721, 30)):
            self.feed(tracker, x, n * 0.1)
        tracks, decisions = tracker.update([], [], 1.9, 1000, 400)
        self.assertEqual(decisions, [])
        self.assertFalse(tracks[0].decided)
        tracks, decisions = tracker.update([], [], 2.3, 1000, 400)
        self.assertEqual(tracks, [])
        self.assertEqual(decisions, [])
        # A bottle reappearing near the output cannot become a new identity.
        tracks, decisions = self.feed(tracker, 810, 2.4)
        self.assertEqual((tracks, decisions), ([], []))

    def test_fresh_match_after_short_dropout_can_cross(self):
        tracker = BottleTracker()
        for n, x in enumerate(range(180, 721, 30)):
            self.feed(tracker, x, n * 0.1)
        tracker.update([], [], 1.9, 1000, 400)
        tracks, decisions = self.feed(tracker, 780, 2.0)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(tracks[0].id, 1)

    def test_no_late_spawning_or_stopped_crossings(self):
        tracker = BottleTracker()
        self.assertEqual(self.feed(tracker, 500, 0), ([], []))
        self.assertEqual(self.feed(tracker, 180, 0.1, moving=False), ([], []))
        self.feed(tracker, 180, 0.2)
        tracks, decisions = self.feed(tracker, 750, 0.3, moving=False)
        self.assertEqual(tracks[0].bbox, bottle(180))
        self.assertEqual(decisions, [])
        # Tracks are frozen across a pause, including their miss timeout.
        self.feed(tracker, 180, 20, moving=False)
        tracks, decisions = self.feed(tracker, 210, 20.1)
        self.assertEqual(tracks[0].id, 1)
        self.assertEqual(decisions, [])

    def test_sequential_bottles_keep_ids_with_reordered_detections_and_dropout(self):
        tracker = BottleTracker()
        outputs = []
        original = None
        for n in range(37):
            lead = 180 + n * 25
            rear = lead - 200
            boxes = []
            flags = []
            if 0 <= lead <= 940 and n != 15:
                boxes.append(bottle(lead))
                flags.append(["Missing cap"])
            if 0 <= rear <= 940:
                boxes.append(bottle(rear))
                flags.append([])
            if n % 2:
                boxes.reverse()
                flags.reverse()
            tracks, decisions = tracker.update(boxes, flags, n * 0.1, 1000, 400)
            if n == 1:
                original = tracks[0].id
            outputs.extend(decisions)
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0].id, original)
        self.assertTrue(outputs[0].bad)
        self.assertFalse(outputs[1].bad)
        self.assertNotEqual(outputs[0].id, outputs[1].id)

    def test_stale_capture_cannot_mutate_or_emit(self):
        tracker = BottleTracker()
        self.feed(tracker, 180, 1)
        tracks, decisions = self.feed(tracker, 750, 1)
        self.assertEqual(tracks[0].bbox, bottle(180))
        self.assertEqual(decisions, [])
        tracks, decisions = self.feed(tracker, 750, 0.9)
        self.assertEqual(tracks[0].hits, 1)
        self.assertEqual(decisions, [])

    def test_reset_keeps_ids_monotonic(self):
        tracker = BottleTracker()
        first = self.feed(tracker, 180, 1)[0][0].id
        tracker.reset()
        second = self.feed(tracker, 180, 0)[0][0].id
        self.assertGreater(second, first)

    def test_validation_rejects_invalid_configuration_and_capture(self):
        for kwargs in ({"direction": "up"}, {"line": math.nan}, {"entry": 0.9}, {"confirm_frames": 0}, {"confirm_frames": 1.2}, {"max_miss": math.inf}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                TrackingConfig(**kwargs)
        tracker = BottleTracker()
        for captured in (math.nan, math.inf, -1):
            with self.subTest(captured=captured), self.assertRaises(ValueError):
                self.feed(tracker, 180, captured)
        with self.assertRaises(ValueError):
            tracker.update([bottle(180)], [], 0, 1000, 400)
        with self.assertRaises(ValueError):
            tracker.update([(-1, 0, 20, 30)], [[]], 0, 1000, 400)
        with self.assertRaises(ValueError):
            tracker.update([(1, 0, math.inf, 30)], [[]], 0, 1000, 400)


if __name__ == "__main__":
    unittest.main()
