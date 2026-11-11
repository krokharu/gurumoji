import re
import unittest

import app


class ApplicationVersionTests(unittest.TestCase):
    def test_feature_release_version_is_exposed_in_ui(self):
        self.assertEqual(app.APP_VERSION, "β0.46.1")
        self.assertRegex(app.APP_VERSION, r"^β?\d+\.\d+\.\d+$")

        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertTrue(re.search(r"\bVERSION " + re.escape(app.APP_VERSION) + r"\b", page))
        self.assertIn("v" + app.APP_VERSION, page)


if __name__ == "__main__":
    unittest.main()
