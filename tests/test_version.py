import re
import unittest

import app


class ApplicationVersionTests(unittest.TestCase):
    def test_feature_release_version_is_exposed_in_ui(self):
        self.assertEqual(app.APP_VERSION, "1.1.0")
        self.assertRegex(app.APP_VERSION, r"^\d+\.\d+\.\d+$")

        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertTrue(re.search(r"\bVERSION 1\.1\.0\b", page))
        self.assertIn("v1.1.0", page)


if __name__ == "__main__":
    unittest.main()
