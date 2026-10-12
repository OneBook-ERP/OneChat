import frappe
from frappe.tests import IntegrationTestCase

from onechat.automation import flows as automation
from onechat.campaigns import bulk_messaging
from onechat.setup import install
from onechat.whatsapp import message
from onechat.workspace import session


class TestPermissions(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_install_hooks_are_not_callable_over_http(self):
		self.assertNotIn(install.before_install, frappe.whitelisted)
		self.assertNotIn(install.before_uninstall, frappe.whitelisted)

	def test_scheduler_job_is_not_callable_over_http(self):
		self.assertNotIn(bulk_messaging.schedule_bulk_messages, frappe.whitelisted)

	def test_guest_cannot_use_admin_endpoints(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			automation.get_flows()
		with self.assertRaises(frappe.PermissionError):
			session.require_admin()

	def test_guest_cannot_send_templates(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			message.send_whatsapp_template("OneChat Contact", "x", "any-template", "919999999999")

	def test_administrator_passes_guards(self):
		session.require_admin()
		session.require_app_user()
