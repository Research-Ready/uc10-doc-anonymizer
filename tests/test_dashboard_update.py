"""Tests for Web Dashboard and One-Click Update endpoints."""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.web_dashboard import app, get_version_info


class TestDashboardEndpoints(unittest.TestCase):
    """Test dashboard APIs and update functions."""

    def setUp(self):
        self.client = TestClient(app)

    def test_version_info(self):
        info = get_version_info()
        self.assertIn("version", info)
        self.assertIn("commit", info)
        self.assertIn("branch", info)
        self.assertEqual(info["version"], "1.0.0")

    def test_update_status_endpoint(self):
        response = self.client.get("/api/update/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["version"], "1.0.0")
        self.assertIn("can_pull", data)
        self.assertIn("status_message", data)

    def test_dashboard_html_rendering(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Windesheim", response.text)
        self.assertIn("Systeem & Versiebeheer", response.text)
        self.assertIn("Nu Bijwerken", response.text)

    def test_inputs_and_outputs_api(self):
        r_in = self.client.get("/api/inputs")
        self.assertEqual(r_in.status_code, 200)
        self.assertIn("files", r_in.json())

        r_out = self.client.get("/api/outputs")
        self.assertEqual(r_out.status_code, 200)
        self.assertIn("files", r_out.json())


if __name__ == "__main__":
    unittest.main()
