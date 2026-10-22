"""Virtual conveyor integration checks. No GUI, cameras, or motion are opened."""
from __future__ import annotations

import unittest

from app.barcode_fixture import demo_barcode, normalize_ean13
from app.settings import DEFAULTS
from app.simulation import HEIGHT, WIDTH, Simulation
from app.tracking import BottleTracker, TrackingConfig


class SimulationTrackingTests(unittest.TestCase):
    def run_conveyor(self, *, direction="ltr", pass_color="orange", rule="color",
                     seconds=60, force_first_divert=False):
        settings = dict(DEFAULTS, direction=direction, pass_color=pass_color, rule=rule)
        simulation = Simulation()
        simulation.next_bad = force_first_divert
        tracker = BottleTracker(TrackingConfig(
            direction=direction, line=settings["line"], entry=settings["entry"],
            confirm_frames=settings["confirm_frames"], max_miss=settings["max_miss"],
        ))
        step = 1.0 / 30.0
        identities = {}
        seen_bottles = {}
        last_progress = {}
        expected_crossings = set()
        decided_sequences = set()
        decision_ids = set()
        events = []
        for tick in range(int(seconds * 30)):
            boxes, reasons = simulation.update(step, settings)
            # Oracle: the virtual physical bottle's leading edge crosses the
            # configured line. It is independent of detector matching and IDs.
            for bottle in simulation.bottles:
                seq = bottle["seq"]
                seen_bottles[seq] = {"color": bottle["kind"], "barcode": demo_barcode(seq)}
                progress = ((bottle["x"] + 44) / WIDTH if direction == "ltr"
                            else 1.0 - (bottle["x"] - 44) / WIDTH)
                previous = last_progress.get(seq, progress)
                if not bottle["ejected"] and previous < settings["line"] <= progress:
                    expected_crossings.add(seq)
                last_progress[seq] = progress
            tracks, decisions = tracker.update(boxes, reasons, (tick + 1) * step, WIDTH, HEIGHT)
            for track in tracks:
                if track.missed:
                    continue
                cx = (track.bbox[0] + track.bbox[2]) / 2
                physical = min(simulation.bottles, key=lambda b: abs(b["x"] - cx))
                self.assertAlmostEqual(physical["x"], cx, places=6)
                seq = physical["seq"]
                # A tracker identity may never inherit a following bottle's
                # color or barcode, in either conveyor direction.
                self.assertEqual(identities.setdefault(track.id, seq), seq)
                meta = seen_bottles[seq]
                self.assertEqual(normalize_ean13(meta["barcode"]), meta["barcode"])
                self.assertEqual(meta["barcode"], demo_barcode(physical["seq"]))
                self.assertEqual(meta["color"], physical["kind"])
            for decision in decisions:
                self.assertNotIn(decision.id, decision_ids)
                decision_ids.add(decision.id)
                seq = identities[decision.id]
                self.assertNotIn(seq, decided_sequences)
                self.assertIn(seq, expected_crossings)
                decided_sequences.add(seq)
                physical = seen_bottles[seq]
                expected_bad = (rule == "all" or
                                (rule == "color" and physical["color"] != pass_color) or
                                (rule == "every_n" and seq % settings["every_n"] == 0))
                self.assertEqual(decision.bad, expected_bad,
                                 f"Wrong route for bottle {seq}: {physical['color']}, pass {pass_color}")
                if expected_bad:
                    self.assertTrue(decision.reasons)
                    simulation.eject(decision.bbox)
                else:
                    self.assertEqual(decision.reasons, [])
                events.append({"id": decision.id, "sequence": seq,
                               "color": physical["color"], "barcode": physical["barcode"],
                               "divert": decision.bad})
        self.assertEqual(decided_sequences, expected_crossings,
                         "Every physical line crossing needs exactly one decision")
        self.assertEqual(len(events), len(decision_ids))
        self.assertEqual(len({event["barcode"] for event in events}), len(events))
        return events

    def test_sixty_seconds_both_directions_every_pass_color(self):
        for direction in ("ltr", "rtl"):
            for pass_color in ("orange", "yellow", "green", "blue", "red", "purple", "white", "clear"):
                with self.subTest(direction=direction, pass_color=pass_color):
                    events = self.run_conveyor(direction=direction, pass_color=pass_color)
                    self.assertGreater(len(events), 35)
                    self.assertTrue(any(event["divert"] for event in events))
                    matching = [event for event in events if event["color"] == pass_color]
                    self.assertTrue(all(not event["divert"] for event in matching))
                    self.assertTrue(matching)

    def test_all_none_and_every_n_rules_use_same_tracked_id_and_code(self):
        for direction in ("ltr", "rtl"):
            for rule in ("all", "none", "every_n"):
                with self.subTest(direction=direction, rule=rule):
                    events = self.run_conveyor(direction=direction, rule=rule, seconds=20)
                    self.assertGreater(len(events), 8)
                    if rule == "none":
                        self.assertTrue(all(not event["divert"] for event in events))
                    elif rule == "all":
                        self.assertTrue(all(event["divert"] for event in events))

    def test_injected_bottle_diverts_even_when_pass_color_is_blue(self):
        for direction in ("ltr", "rtl"):
            with self.subTest(direction=direction):
                events = self.run_conveyor(direction=direction, pass_color="blue",
                                           seconds=12, force_first_divert=True)
                first = next(event for event in events if event["sequence"] == 1)
                self.assertEqual(first["color"], "red")
                self.assertEqual(first["barcode"], demo_barcode(1))
                self.assertTrue(first["divert"])


if __name__ == "__main__":
    unittest.main()
