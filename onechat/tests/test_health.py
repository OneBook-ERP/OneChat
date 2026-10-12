from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from onechat.workspace import health


class TestTemplateCheck(IntegrationTestCase):
	def check(self, name, value=None):
		with patch.object(frappe.db, "get_value", return_value=value):
			return health.template_row(
				"receipt_template", "Payments", "Receipt template", name, health.WARN, "Not set."
			)

	def test_missing_template_uses_the_given_status(self):
		self.assertEqual(self.check(None)["status"], health.WARN)

	def test_deleted_template_is_broken(self):
		self.assertEqual(self.check("receipt_tpl")["status"], health.FAIL)

	def test_pending_template_is_broken(self):
		row = self.check("receipt_tpl", frappe._dict(template_name="Receipt", status="PENDING"))

		self.assertEqual(row["status"], health.FAIL)
		self.assertIn("pending", row["detail"])

	def test_approved_template_is_working(self):
		self.assertEqual(
			self.check("receipt_tpl", frappe._dict(template_name="Receipt", status="APPROVED"))["status"],
			health.OK,
		)


class TestHealthReport(IntegrationTestCase):
	def test_every_check_has_a_known_status(self):
		def working():
			return [health.row("one", "System", "One", health.OK, "Fine")]

		with patch.object(health, "SECTIONS", (working,)):
			result = health.report()

		self.assertEqual([check["status"] for check in result["checks"]], [health.OK])
		self.assertTrue(result["generated_at"])

	def test_a_failing_check_does_not_hide_the_others(self):
		def broken():
			raise ValueError("boom")

		def working():
			return [health.row("one", "System", "One", health.OK, "Fine")]

		with (
			patch.object(health, "SECTIONS", (broken, working)),
			patch.object(frappe, "log_error") as log_error,
		):
			result = health.report()

		statuses = [check["status"] for check in result["checks"]]
		self.assertEqual(statuses, [health.WARN, health.OK])
		self.assertIn("boom", result["checks"][0]["detail"])
		log_error.assert_called_once()

	def test_only_admins_can_open_health(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				health.report()
		finally:
			frappe.set_user("Administrator")
