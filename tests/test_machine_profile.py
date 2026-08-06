import unittest
from unittest.mock import patch

import app
from app import detect_machine_profile, recommend_machine_settings


class RecommendMachineSettingsTests(unittest.TestCase):
    def test_recommends_high_accuracy_for_large_modern_gpu(self):
        recommendation = recommend_machine_settings(16, 32.0, True, 16.0, 8)

        self.assertEqual(recommendation["model_name"], "large-v3")
        self.assertEqual(recommendation["device"], "cuda")
        self.assertEqual(recommendation["diarization_device"], "cuda")

    def test_treats_reported_eleven_point_nine_gib_as_twelve_gib_class(self):
        recommendation = recommend_machine_settings(20, 64.0, True, 11.9, 12)

        self.assertEqual(recommendation["model_name"], "large-v3")
        self.assertEqual(recommendation["diarization_device"], "cuda")

    def test_keeps_diarization_on_cpu_for_six_gib_gpu(self):
        recommendation = recommend_machine_settings(12, 16.0, True, 6.0, 7)

        self.assertEqual(recommendation["model_name"], "small")
        self.assertEqual(recommendation["device"], "cuda")
        self.assertEqual(recommendation["diarization_device"], "cpu")

    def test_limits_old_gpu_to_base(self):
        recommendation = recommend_machine_settings(8, 16.0, True, 4.0, 6)

        self.assertEqual(recommendation["model_name"], "base")
        self.assertEqual(recommendation["device"], "cuda")
        self.assertEqual(recommendation["diarization_device"], "cpu")

    def test_recommends_small_for_capable_cpu_only_machine(self):
        recommendation = recommend_machine_settings(12, 32.0, False)

        self.assertEqual(recommendation["model_name"], "small")
        self.assertEqual(recommendation["device"], "cpu")
        self.assertEqual(recommendation["diarization_device"], "cpu")

    def test_recommends_tiny_for_low_spec_cpu_only_machine(self):
        recommendation = recommend_machine_settings(2, 4.0, False)

        self.assertEqual(recommendation["model_name"], "tiny")
        self.assertEqual(recommendation["device"], "cpu")


class DetectMachineProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = detect_machine_profile()

    def test_reports_cpu_and_recommendation(self):
        self.assertTrue(self.profile["cpu"]["available"])
        self.assertGreaterEqual(self.profile["cpu"]["logical_threads"], 1)
        self.assertIn(self.profile["recommended"]["model_name"], {
            "tiny", "base", "small", "medium", "large-v3",
        })
        self.assertIn(self.profile["recommended"]["device"], {"cpu", "cuda"})

    def test_cuda_recommendation_matches_cuda_availability(self):
        expected_device = "cuda" if self.profile["gpu"]["cuda_available"] else "cpu"
        self.assertEqual(self.profile["recommended"]["device"], expected_device)

    def test_cpu_and_gpu_lights_are_visible_in_header_and_settings(self):
        page = app.app.test_client().get("/").data.decode("utf-8")

        self.assertEqual(page.count('data-hardware="cpu"'), 3)
        self.assertEqual(page.count('data-hardware="gpu"'), 3)
        self.assertIn("PROCESSOR STATUS", page)

    def test_live_system_activity_endpoint_has_resource_and_io_metrics(self):
        response = app.app.test_client().get("/api/system/activity")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("utilization_percent", payload["cpu"])
        self.assertIn("utilization_percent", payload["memory"])
        self.assertIn("utilization_percent", payload["gpu"])
        self.assertIn("read_active", payload["disk"])
        self.assertIn("write_active", payload["disk"])
        self.assertIn("read_mib_per_second", payload["disk"])
        self.assertIn("write_mib_per_second", payload["disk"])

    def test_cpu_activity_uses_a_thread_independent_sample(self):
        with patch("psutil.cpu_percent", return_value=37.5) as cpu_percent:
            snapshot = app.system_activity_snapshot()

        cpu_percent.assert_called_once_with(interval=0.1)
        self.assertTrue(snapshot["cpu"]["available"])
        self.assertEqual(snapshot["cpu"]["utilization_percent"], 37.5)


if __name__ == "__main__":
    unittest.main()
