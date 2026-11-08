from unittest.mock import patch

import frappe

from onechat.automation import engine, run_as
from onechat.integrations import connection
from onechat.tests.compat import IntegrationTestCase

BOT = "onechat-automation-bot@example.com"
VISITOR = "onechat-automation-visitor@example.com"


def make_user(email, roles):
	if frappe.db.exists("User", email):
		return frappe.get_doc("User", email)
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
	)
	for role in roles:
		user.append("roles", {"role": role})
	return user.insert(ignore_permissions=True)


def pick(user):
	frappe.db.set_single_value(run_as.SETTINGS, run_as.FIELD, user)
	frappe.clear_document_cache(run_as.SETTINGS, run_as.SETTINGS)


class TestAutomationUser(IntegrationTestCase):
	def setUp(self):
		make_user(BOT, ["System Manager"])
		make_user(VISITOR, [])
		frappe.set_user("Guest")

	def tearDown(self):
		frappe.set_user("Administrator")
		pick(None)

	def test_only_enabled_system_users_are_usable(self):
		self.assertTrue(run_as.usable(BOT))
		self.assertFalse(run_as.usable(VISITOR))
		self.assertFalse(run_as.usable("Guest"))
		self.assertFalse(run_as.usable(None))

	def test_settings_reject_a_website_user(self):
		frappe.set_user("Administrator")
		settings = frappe.get_doc(run_as.SETTINGS)
		settings.automation_user = VISITOR
		self.assertRaises(frappe.ValidationError, settings.save)

	def test_switch_restores_user_form_and_flag(self):
		frappe.local.form_dict = frappe._dict(keep="me")
		with run_as.switched(BOT) as user:
			self.assertEqual(user, BOT)
			self.assertEqual(frappe.session.user, BOT)
			self.assertTrue(run_as.active())
		self.assertEqual(frappe.session.user, "Guest")
		self.assertEqual(frappe.local.form_dict.get("keep"), "me")
		self.assertFalse(run_as.active())

	def test_switch_restores_after_an_error(self):
		with self.assertRaises(RuntimeError), run_as.switched(BOT):
			raise RuntimeError("step failed")
		self.assertEqual(frappe.session.user, "Guest")
		self.assertFalse(run_as.active())

	def test_without_a_user_flows_keep_the_caller(self):
		with run_as.as_automation_user():
			self.assertEqual(frappe.session.user, "Guest")
			self.assertTrue(run_as.active())

	def test_without_a_user_elevated_steps_use_administrator(self):
		with run_as.elevated():
			self.assertEqual(frappe.session.user, "Administrator")
		with run_as.elevated(local=False):
			self.assertEqual(frappe.session.user, "Guest")

	def test_picked_user_runs_flows_and_elevated_steps(self):
		pick(BOT)
		with run_as.as_automation_user():
			self.assertEqual(frappe.session.user, BOT)
		with run_as.elevated():
			self.assertEqual(frappe.session.user, BOT)

	def test_a_disabled_user_falls_back(self):
		pick(BOT)
		frappe.db.set_value("User", BOT, "enabled", 0)
		with run_as.elevated():
			self.assertEqual(frappe.session.user, "Administrator")
		frappe.db.set_value("User", BOT, "enabled", 1)

	def test_flow_start_and_resume_run_as_the_picked_user(self):
		pick(BOT)
		with patch.object(engine, "start_run", side_effect=lambda *args: frappe.session.user):
			self.assertEqual(engine.start("Any Flow", {}), BOT)
		with patch.object(engine, "resume_run", side_effect=lambda *args: frappe.session.user):
			self.assertEqual(engine.resume(frappe._dict(), {}), BOT)
		self.assertEqual(frappe.session.user, "Guest")


class TestAutomationLogin(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.existed = frappe.db.exists(connection.CONNECTION, "erpnext")
		self.site = connection.site("erpnext")
		self.site.update({"automation_api_key": "bot-key", "automation_api_secret": "bot-secret"})

	def tearDown(self):
		if self.existed:
			self.site.update({"automation_api_key": None, "automation_api_secret": None})
		else:
			frappe.delete_doc(connection.CONNECTION, "erpnext", ignore_permissions=True, force=True)
			self.site.forget()

	def test_login_is_used_only_while_automating(self):
		self.assertIsNone(self.site.automation_login())
		with run_as.switched(None):
			self.assertEqual(self.site.automation_login(), "token bot-key:bot-secret")
		self.assertIsNone(self.site.automation_login())

	def test_empty_login_falls_back_to_the_connection(self):
		self.site.update({"automation_api_key": None, "automation_api_secret": None})
		with run_as.switched(None):
			self.assertIsNone(self.site.automation_login())
