"""Deterministic geometry tests; generated rectangles only, no photographs."""
from __future__ import annotations

import math
import random
import unittest

from negative_space import MAX_BOXES, measure_bbox_empty_area


def box(x0=0, y0=0, x1=20, y1=100):
    return dict(x_min=x0, y_min=y0, x_max=x1, y_max=y1)


class NegativeSpaceTests(unittest.TestCase):
    def test_empty_frame(self):
        result = measure_bbox_empty_area([], 100, 100)
        for key in ('left_ratio', 'right_ratio', 'top_ratio', 'bottom_ratio', 'total_negative_ratio'):
            self.assertEqual(result[key], 1.0)

    def test_left_subject_leaves_more_room_on_right(self):
        result = measure_bbox_empty_area([box()], 100, 100)
        self.assertEqual([result[k] for k in ('left_ratio', 'right_ratio', 'top_ratio', 'bottom_ratio', 'total_negative_ratio')],
                         [0.6, 1.0, 0.8, 0.8, 0.8])
        # Frozen N2B2 returns all four directional values as 0.2 / 4 = 0.05.
        self.assertNotEqual(result['left_ratio'], result['right_ratio'])

    def test_top_subject(self):
        result = measure_bbox_empty_area([box(0, 0, 100, 20)], 100, 100)
        self.assertEqual((result['top_ratio'], result['bottom_ratio']), (0.6, 1.0))

    def test_full_frame(self):
        result = measure_bbox_empty_area([box(0, 0, 100, 100)], 100, 100)
        self.assertEqual(result['total_negative_ratio'], 0)

    def test_overlap_is_counted_once(self):
        result = measure_bbox_empty_area([box(0, 0, 40, 100), box(20, 0, 60, 100)], 100, 100)
        self.assertEqual(result['total_negative_ratio'], 0.4)

    def test_duplicate_boxes_do_not_change_measurement(self):
        self.assertEqual(measure_bbox_empty_area([box()], 100, 100), measure_bbox_empty_area([box(), box()], 100, 100))

    def test_clips_at_frame(self):
        self.assertEqual(measure_bbox_empty_area([box(-10, -10, 20, 200)], 100, 100),
                         measure_bbox_empty_area([box()], 100, 100))

    def test_offscreen_and_zero_area(self):
        self.assertEqual(measure_bbox_empty_area([box(200, 0, 300, 10), box(0, 0, 0, 5)], 100, 100),
                         measure_bbox_empty_area([], 100, 100))

    def test_inverted_coordinates(self):
        with self.assertRaisesRegex(ValueError, 'INVERTED'):
            measure_bbox_empty_area([box(20, 0, 0, 100)], 100, 100)

    def test_nonfinite_and_invalid_numbers(self):
        for value in (math.nan, math.inf, -math.inf, True, '12', None, 10 ** 1000):
            with self.subTest(value=str(value)[:12]):
                with self.assertRaises(ValueError):
                    measure_bbox_empty_area([box(x1=value)], 100, 100)

    def test_invalid_frame(self):
        for width, height in ((0, 100), (-1, 100), (True, 100), (1e308, 1e308)):
            with self.assertRaises(ValueError):
                measure_bbox_empty_area([], width, height)

    def test_box_limit(self):
        with self.assertRaisesRegex(ValueError, 'BOX_LIMIT'):
            measure_bbox_empty_area([box()] * (MAX_BOXES + 1), 100, 100)

    def test_missing_coordinate(self):
        with self.assertRaisesRegex(ValueError, 'INVALID_BOX'):
            measure_bbox_empty_area([{}], 100, 100)

    def test_scale_invariance_and_half_frame_identity(self):
        a = measure_bbox_empty_area([box(5, 10, 35, 80)], 100, 100)
        b = measure_bbox_empty_area([box(10, 20, 70, 160)], 200, 200)
        self.assertEqual(a, b)
        self.assertAlmostEqual((a['left_ratio'] + a['right_ratio']) / 2, a['total_negative_ratio'])
        self.assertAlmostEqual((a['top_ratio'] + a['bottom_ratio']) / 2, a['total_negative_ratio'])

    def test_random_union_against_independent_pixel_oracle(self):
        rng = random.Random(20260913)
        for _ in range(100):
            boxes = []
            for _ in range(rng.randint(0, 8)):
                x0, x1 = sorted((rng.randint(-3, 13), rng.randint(-3, 13)))
                y0, y1 = sorted((rng.randint(-3, 13), rng.randint(-3, 13)))
                boxes.append(box(x0, y0, x1, y1))
            result = measure_bbox_empty_area(boxes, 10, 10)
            free = {(x, y) for x in range(10) for y in range(10)
                    if not any(b['x_min'] <= x < b['x_max'] and b['y_min'] <= y < b['y_max'] for b in boxes)}
            self.assertEqual(result['total_negative_ratio'], len(free) / 100)
            self.assertEqual(result['left_ratio'], sum(x < 5 for x, y in free) / 50)
            self.assertEqual(result['right_ratio'], sum(x >= 5 for x, y in free) / 50)
            self.assertEqual(result['top_ratio'], sum(y < 5 for x, y in free) / 50)
            self.assertEqual(result['bottom_ratio'], sum(y >= 5 for x, y in free) / 50)


if __name__ == '__main__':
    unittest.main()
