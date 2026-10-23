import unittest

from app.model_classes import (build_color_map, class_names_from_metadata,
                               color_from_class_name, color_map_error,
                               parse_class_names, parse_color_map)


class ClassNamesTests(unittest.TestCase):
    def test_label_formats_keep_export_order(self):
        expected = ["orange_bottle", "blue_bottle"]
        for value in (expected, {"1": "blue_bottle", "0": "orange_bottle"},
                      '["orange_bottle", "blue_bottle"]',
                      "{0: 'orange_bottle', 1: 'blue_bottle'}",
                      "orange_bottle, blue_bottle", "orange_bottle\nblue_bottle"):
            with self.subTest(value=value):
                self.assertEqual(parse_class_names(value), expected)

    def test_invalid_ids_and_empty_names_never_shift_labels(self):
        for value in ({"1": "blue"}, {"0": "red", "2": "blue"},
                      {"-1": "red"}, {"0": "red", "00": "blue"},
                      ["red", ""], "red,,blue", [None], 7):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_class_names(value)

    def test_onnx_metadata_and_absent_labels(self):
        self.assertEqual(class_names_from_metadata({"names": "{0: 'red', 1: 'blue'}"}), ["red", "blue"])
        self.assertEqual(class_names_from_metadata({"class_names": '["red", "blue"]'}), ["red", "blue"])
        self.assertEqual(class_names_from_metadata({"other": "ignored"}), [])
        self.assertEqual(class_names_from_metadata(None), [])

    def test_color_tokens_are_unambiguous(self):
        for name in ("orange", "Gatorade_ORANGE", "orange-bottle", "bottle orange"):
            self.assertEqual(color_from_class_name(name), "orange")
        for name in ("bottle", "traffic light", "red_blue", "redish", "orangeade", "cyan"):
            self.assertIsNone(color_from_class_name(name))

    def test_white_and_clear_are_distinct_trained_color_tokens(self):
        self.assertEqual(color_from_class_name("white_bottle"), "white")
        self.assertEqual(color_from_class_name("GATORADE-WHITE"), "white")
        self.assertEqual(color_from_class_name("clear_bottle"), "clear")
        self.assertIsNone(color_from_class_name("white_clear_bottle"))
        self.assertIsNone(color_from_class_name("whitish_bottle"))

    def test_gray_and_grey_tokens_preserve_raw_model_labels_before_sort_grouping(self):
        self.assertEqual(color_from_class_name('gray_bottle'), 'gray')
        self.assertEqual(color_from_class_name('bottle_GREY'), 'grey')
        self.assertEqual(build_color_map(['gray_bottle', 'blue_bottle']), {0: 'gray', 1: 'blue'})


class ColorMapTests(unittest.TestCase):
    def test_explicit_mapping_formats(self):
        expected = {0: "orange", 3: "blue"}
        for value in ({0: "Orange", 3: "BLUE"}, '{"0":"orange", "3":"blue"}',
                      "0:orange,3:blue", "0=orange;3=blue"):
            with self.subTest(value=value):
                self.assertEqual(parse_color_map(value), expected)

    def test_invalid_maps_fail_closed(self):
        for value in ("0:orange,0:blue", "00:orange,0:blue", "-1:red", "x:blue",
                      "0:cyan", "orange,blue", ["orange", "blue"], {False: "red"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_color_map(value)

    def test_joint_color_classes_are_mapped_without_pixels(self):
        self.assertEqual(build_color_map(["orange_bottle", "bottle", "bottle_blue"], class_count=3),
                         {0: "orange", 2: "blue"})
        self.assertEqual(build_color_map(["orange_bottle", "blue_bottle"], {0: "green"}, 2),
                         {0: "green", 1: "blue"})
        self.assertEqual(build_color_map(explicit_map="3:orange,4:blue", class_count=5),
                         {3: "orange", 4: "blue"})

    def test_white_and_clear_classes_remain_separate_in_names_and_manual_maps(self):
        self.assertEqual(build_color_map(["white_bottle", "clear_bottle"], class_count=2),
                         {0: "white", 1: "clear"})
        self.assertEqual(parse_color_map("0:white,1:clear"), {0: "white", 1: "clear"})
        self.assertEqual(color_map_error(["white", "clear"], class_count=2, pass_color="white"), "")
        self.assertIn("pass color", color_map_error(["white", "blue"], class_count=2, pass_color="clear"))

    def test_generic_coco_model_does_not_gain_colors(self):
        with self.assertRaisesRegex(ValueError, "generic bottles"):
            build_color_map(["bottle"])
        with self.assertRaises(ValueError):
            build_color_map(["orange_bottle", "orange_cap"])

    def test_actual_output_class_count_is_required_to_match(self):
        for names, mapping, count in ((["red", "blue"], None, 80),
                                     (None, "0:red,4:blue", 4),
                                     (None, "0:red,1:blue", 0)):
            with self.subTest(count=count), self.assertRaises(ValueError):
                build_color_map(names, mapping, count)

    def test_pass_color_must_exist_in_the_model(self):
        self.assertEqual(color_map_error(["red", "blue"], class_count=2, pass_color="red"), "")
        self.assertIn("pass color", color_map_error(["red", "blue"], class_count=2, pass_color="orange"))
        self.assertTrue(color_map_error(["bottle"], class_count=1, pass_color="red"))


class AutomaticCategoryTests(unittest.TestCase):
    def test_opt_in_accepts_one_trained_category_and_keeps_known_color_names(self):
        self.assertEqual(build_color_map(["PINK"], class_count=1, allow_class_labels=True), {0: "pink"})
        self.assertEqual(build_color_map(["Gatorade_BLUE"], class_count=1, allow_class_labels=True), {0: "blue"})
        self.assertEqual(build_color_map(["Pink Bottle", "BLACK", "Lot A"], class_count=3, allow_class_labels=True),
                         {0: "pink bottle", 1: "black", 2: "lot a"})
        with self.assertRaises(ValueError):
            build_color_map(["PINK"], class_count=1)

    def test_explicit_custom_routes_require_opt_in(self):
        self.assertEqual(parse_color_map('0:Pink,1:BLACK', allow_class_labels=True), {0: "pink", 1: "black"})
        self.assertEqual(build_color_map(["pink", "black"], {1: "Secondary Lane"}, 2, allow_class_labels=True),
                         {0: "pink", 1: "secondary lane"})
        with self.assertRaises(ValueError):
            parse_color_map('0:pink,1:black')

    def test_unknown_generic_and_ambiguous_labels_never_become_auto_routes(self):
        names = ["bottle", "other", "background", "unknown", "red_blue", "class_5", "pink"]
        self.assertEqual(build_color_map(names, class_count=len(names), allow_class_labels=True), {6: "pink"})
        for name in ("bottle", "unknown", "red_blue", "other_red", "background-blue", "class_0"):
            with self.subTest(label=name), self.assertRaises(ValueError):
                build_color_map([name], class_count=1, allow_class_labels=True)
        for name in ("bottle", "unknown", "red_blue", "", None):
            with self.subTest(explicit_label=name), self.assertRaises(ValueError):
                parse_color_map({0: name}, allow_class_labels=True)

    def test_custom_routes_still_validate_actual_class_count_and_pass_category(self):
        with self.assertRaises(ValueError):
            build_color_map(["pink"], class_count=2, allow_class_labels=True)
        with self.assertRaises(ValueError):
            build_color_map(explicit_map={3: "pink"}, class_count=1, allow_class_labels=True)
        self.assertEqual(color_map_error(["pink"], class_count=1, pass_color="PINK", allow_class_labels=True), "")
        self.assertIn("pass color", color_map_error(["pink"], class_count=1, pass_color="black", allow_class_labels=True))


if __name__ == "__main__":
    unittest.main()
