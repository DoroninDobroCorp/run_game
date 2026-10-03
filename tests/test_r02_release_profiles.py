import unittest

from tools.r02_release_profiles import PINNED_MASTERS, expected_master


class ReleaseProfileTests(unittest.TestCase):
    def test_each_known_route_uses_its_independently_pinned_master(self):
        legacy = "a" * 64
        binding = "el_bolson_patagonia_argentina_m01_v1"
        self.assertEqual(expected_master(binding, legacy), PINNED_MASTERS[binding])
        self.assertNotEqual(expected_master(binding, legacy), legacy)

    def test_unknown_or_malformed_binding_does_not_accept_arbitrary_manifest(self):
        legacy = "a" * 64
        for binding in [None, [], {}, 42, "new_unreviewed_route"]:
            with self.subTest(binding=binding):
                self.assertEqual(expected_master(binding, legacy), legacy)


if __name__ == "__main__":
    unittest.main()
