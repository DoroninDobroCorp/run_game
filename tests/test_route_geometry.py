import copy
import unittest

from tools import route_geometry as geometry


class RouteGeometryTests(unittest.TestCase):
    def setUp(self):
        self.points = [
            dict(latitude=10.0001, longitude=20.0001),
            dict(latitude=10.0011, longitude=20.0001),
            dict(latitude=10.0011, longitude=20.0011),
            dict(latitude=10.0001, longitude=20.0011),
            dict(latitude=10.0001, longitude=20.0001),
        ]
        self.route = dict(coordinates=self.points, waypointIndices=[0, 1, 2, 3, 4],
                          source="OSM", attribution="OpenStreetMap contributors", note="Synthetic fixture")

    def test_valid_loop_and_midpoint_are_measured_along_geometry(self):
        self.assertEqual(geometry.validate_route(self.route, self.points), self.route)
        total = geometry.lengths(self.points)[-1]
        self.assertAlmostEqual(total, 441.4, delta=1)
        midpoint = geometry.point_at(self.points, total / 2)
        self.assertLess(geometry.distance(midpoint, self.points[2]), 0.1)

    def test_rejects_bad_coordinates(self):
        for value in [float("nan"), float("inf"), True, "10", 91]:
            route = copy.deepcopy(self.route)
            route["coordinates"][1]["latitude"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                geometry.validate_route(route, self.points)

    def test_rejects_invalid_or_reordered_waypoint_indices(self):
        with self.assertRaises(ValueError):
            geometry.validate_route({**self.route, "waypointIndices": []}, [])
        for indices in [[0, 1, 3, 2, 4], [0, 1, 2, 3, 99], [0, 1, 2, 3], [0, 1, 2, 3, True]]:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                geometry.validate_route({**self.route, "waypointIndices": indices}, self.points)

    def test_rejects_waypoints_not_on_route(self):
        points = copy.deepcopy(self.points)
        points[2]["latitude"] += 0.01
        with self.assertRaisesRegex(ValueError, "visit"):
            geometry.validate_route(self.route, points)

    def test_rejects_open_loop_and_shortcuts(self):
        route = copy.deepcopy(self.route)
        route["coordinates"][-1]["latitude"] += .001
        with self.assertRaises(ValueError):
            geometry.validate_route(route, route["coordinates"])
        route = copy.deepcopy(self.route)
        route["coordinates"][2]["latitude"] += .1
        with self.assertRaisesRegex(ValueError, "gap"):
            geometry.validate_route(route, route["coordinates"])

    def test_interpolation_rejects_invalid_distance_and_empty_route(self):
        for value in [-1, float("nan"), float("inf"), 5000]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                geometry.point_at(self.points, value)
        with self.assertRaises(ValueError):
            geometry.point_at([], 0)


if __name__ == "__main__":
    unittest.main()
