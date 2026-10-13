"""
Unit and integration tests for the mock company application.
Tests all HTML routes, REST API endpoints, filtering, and data mutations.
"""

import unittest
from fastapi.testclient import TestClient

from mock_app.server import app
from mock_app.routes import store


class TestMockApp(unittest.TestCase):
    """Test suite for Mock Company Portal."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        # Reset in-memory store before each test
        store.reset()

    def test_health_check(self):
        """Verify health check endpoint returns 200."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["status"], ("ok", "healthy"))

    def test_dashboard_html(self):
        """Verify dashboard HTML page renders with stats."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("CentrAlign", response.text)
        self.assertIn("stat-invoices", response.text)

    def test_invoices_html(self):
        """Verify invoices page renders with invoice list."""
        response = self.client.get("/invoices")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Acme Corp", response.text)
        self.assertIn("invoice-search", response.text)

    def test_invoice_detail_html(self):
        """Verify invoice detail page renders."""
        response = self.client.get("/invoices/inv-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Acme Corp", response.text)

    def test_expenses_html(self):
        """Verify expense ledger renders."""
        response = self.client.get("/expenses")
        self.assertEqual(response.status_code, 200)
        self.assertIn("expenses-table", response.text)

    def test_expense_create_form_and_submit(self):
        """Test submitting the expense form via HTML POST."""
        form_data = {
            "description": "Enterprise Cloud Hosting Q3",
            "amount": "14500.00",
            "category": "Software",
            "invoice_ref": "inv-001",
            "created_by": "Autonomous Agent",
        }
        response = self.client.post("/expenses/new", data=form_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Enterprise Cloud Hosting Q3", response.text)

    def test_api_list_invoices(self):
        """Test GET /api/invoices and vendor filtering."""
        response = self.client.get("/api/invoices")
        self.assertEqual(response.status_code, 200)
        invoices = response.json()
        self.assertGreaterEqual(len(invoices), 8)

        # Filter by vendor
        filtered = self.client.get("/api/invoices?vendor=Acme Corp").json()
        self.assertTrue(all("Acme" in inv["vendor_name"] for inv in filtered))

    def test_api_get_invoice(self):
        """Test GET /api/invoices/{id}."""
        response = self.client.get("/api/invoices/inv-001")
        self.assertEqual(response.status_code, 200)
        inv = response.json()
        self.assertEqual(inv["id"], "inv-001")
        self.assertEqual(inv["vendor_name"], "Acme Corp")

    def test_api_create_and_list_expenses(self):
        """Test creating an expense via API and retrieving it."""
        payload = {
            "description": "Security Audit Fee",
            "amount": 8500.0,
            "category": "Security",
            "invoice_ref": "inv-002",
            "created_by": "Agent Worker",
        }
        res = self.client.post("/api/expenses", json=payload)
        self.assertEqual(res.status_code, 201)
        created = res.json()
        self.assertEqual(created["description"], "Security Audit Fee")
        self.assertEqual(created["amount"], 8500.0)

        # Verify listed in expenses
        list_res = self.client.get("/api/expenses")
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(any(e["id"] == created["id"] for e in list_res.json()))

    def test_api_contacts_and_tasks(self):
        """Test contacts directory and task list/patching."""
        # Contacts
        contacts = self.client.get("/api/contacts").json()
        self.assertGreaterEqual(len(contacts), 5)

        # Tasks
        tasks = self.client.get("/api/tasks").json()
        self.assertGreaterEqual(len(tasks), 5)
        task_id = tasks[0]["id"]

        # Patch task status
        patch_res = self.client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["status"], "done")


if __name__ == "__main__":
    unittest.main()
