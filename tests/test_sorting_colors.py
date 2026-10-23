import unittest

from app.sorting_colors import canonical_sort_color


class SortingColorsTests(unittest.TestCase):
    def test_operational_aliases(self):
        for label, expected in (('red', 'red'), ('Yellow', 'red'), ('blue', 'blue'),
                                ('WHITE', 'white'), ('gray', 'white'), (' Grey ', 'white')):
            with self.subTest(label=label):
                self.assertEqual(canonical_sort_color(label), expected)

    def test_other_trained_categories_and_unknown_are_preserved(self):
        for label in ('orange', 'clear', 'plum', 'lemon', 'unknown'):
            self.assertEqual(canonical_sort_color(label), label)
