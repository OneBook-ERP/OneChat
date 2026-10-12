from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from onechat import integrations
from onechat.integrations import connection
from onechat.workspace import session


class TestDeskPermissions(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_administrator_can_do_anything(self):
		for ptype in session.PTYPES:
			self.assertTrue(session.can("OneChat Message", ptype))

	def test_guest_cannot_send_messages(self):
		frappe.set_user("Guest")

		self.assertFalse(session.can("OneChat Message", "create"))
		with self.assertRaises(frappe.PermissionError) as raised:
			session.require("OneChat Message", "create")
		self.assertIn("Role Permission Manager", str(raised.exception))

	def test_unknown_doctype_is_never_allowed(self):
		frappe.set_user("Guest")

		self.assertFalse(session.can("No Such DocType", "read"))

	def test_session_lists_rights_for_each_doctype(self):
		rights = session.me()["can"]

		self.assertIn("OneChat Message", rights)
		self.assertEqual(set(rights["OneChat Message"]), set(session.PTYPES))


class TestActionNeeds(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_actions_follow_desk_permissions(self):
		action = {"needs": [("OneChat Message", "create")]}
		with patch.object(connection, "source_for", return_value=MagicMock(remote=False)):
			self.assertTrue(integrations.permitted(action))
			frappe.set_user("Guest")
			self.assertFalse(integrations.permitted(action))
			with self.assertRaises(frappe.PermissionError):
				integrations.require_needs(action)

	def test_records_on_another_site_use_that_sites_permissions(self):
		frappe.set_user("Guest")
		with patch.object(connection, "source_for", return_value=MagicMock(remote=True)):
			self.assertTrue(integrations.permitted({"needs": [("Lead", "create")]}))

	def test_needs_can_depend_on_the_payload(self):
		action = {"needs": "onechat.integrations.payments.request_needs"}

		self.assertIn(("Payment Request", "create"), integrations.needs(action, {"method": "link"}))
		self.assertEqual(integrations.needs(action), [("OneChat Message", "create")])
