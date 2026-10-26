from unittest.mock import patch

import frappe

from onechat.integrations import crm_bridge
from onechat.tests.compat import UnitTestCase


def row(**values):
	base = {
		"name": "M1",
		"type": "Incoming",
		"to": "",
		"from": "919000000001",
		"content_type": "text",
		"message_type": "Manual",
		"attach": None,
		"template": None,
		"use_template": 0,
		"message_id": "wamid.1",
		"is_reply": 0,
		"reply_to_message_id": None,
		"creation": "2026-10-01 10:00:00",
		"message": "Hello",
		"status": "",
		"reference_doctype": "OneChat Contact",
		"reference_name": "WC-26-1",
		"template_parameters": None,
		"template_header_parameters": None,
		"profile_name": "Asha",
		"error_message": None,
		"whatsapp_contact": "WC-26-1",
	}
	base.update(values)
	return frappe._dict(base)


class TestCrmBridgeOverrides(UnitTestCase):
	def test_every_override_points_to_a_whitelisted_bridge_method(self):
		overrides = frappe.get_hooks("override_whitelisted_methods") or {}
		bridged = {source: target[-1] for source, target in overrides.items() if "crm_bridge" in target[-1]}

		self.assertIn("crm.api.whatsapp.get_whatsapp_messages", bridged)
		self.assertIn("whatsapp.whatsapp.api.messages.get_messages", bridged)
		for target in bridged.values():
			method = frappe.get_attr(target)
			self.assertIn(method, frappe.whitelisted, target)


class TestClassicShape(UnitTestCase):
	def test_reaction_folds_onto_target_and_is_dropped(self):
		rows = [
			row(),
			row(
				name="M2",
				type="Outgoing",
				content_type="reaction",
				message="👍",
				reply_to_message_id="wamid.1",
			),
		]

		result = crm_bridge.classic(rows, "CRM Lead", "LEAD-1")

		self.assertEqual([r.name for r in result], ["M1"])
		self.assertEqual(result[0].reaction, "👍")
		self.assertEqual(result[0].reference_doctype, "CRM Lead")
		self.assertEqual(result[0].from_name, "Asha")

	def test_reply_quotes_the_replied_message(self):
		rows = [
			row(),
			row(
				name="M2",
				type="Outgoing",
				message_id="wamid.2",
				is_reply=1,
				reply_to_message_id="wamid.1",
				message="Hi Asha",
			),
		]

		result = crm_bridge.classic(rows, "CRM Lead", "LEAD-1")

		self.assertEqual(result[1].reply_message, "Hello")
		self.assertEqual(result[1].reply_to, "M1")
		self.assertEqual(result[1].reply_to_type, "Incoming")
		self.assertEqual(result[1].from_name, "You")


class TestModernShape(UnitTestCase):
	@patch.object(crm_bridge, "attach_files")
	def test_maps_fields_and_status(self, _attach):
		rows = [row(type="Outgoing", to="919000000001", status="delivered", message_id="wamid.9")]

		result = crm_bridge.modern(rows, "CRM Deal", "DEAL-1")

		message = result[0]
		self.assertEqual(message.direction, "Outgoing")
		self.assertEqual(message.status, "Delivered")
		self.assertEqual(message["from"], "")
		self.assertEqual(message.to, "919000000001")
		self.assertEqual(message.reference_docname, "DEAL-1")
		self.assertEqual(message.reactions, [])

	@patch.object(crm_bridge, "attach_files")
	def test_reactions_fold_per_direction_and_retraction_removes(self, _attach):
		rows = [
			row(),
			row(
				name="R1",
				type="Outgoing",
				content_type="reaction",
				message="❤️",
				reply_to_message_id="wamid.1",
			),
			row(
				name="R2",
				type="Incoming",
				content_type="reaction",
				message="😀",
				reply_to_message_id="wamid.1",
			),
			row(
				name="R3", type="Incoming", content_type="reaction", message="", reply_to_message_id="wamid.1"
			),
		]

		result = crm_bridge.modern(rows, "CRM Lead", "LEAD-1")

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0].reactions, [{"emoji": "❤️", "direction": "Outgoing"}])

	@patch.object(crm_bridge, "attach_files")
	def test_media_gets_mime_and_url(self, _attach):
		rows = [row(content_type="image", attach="/files/photo.png", message="")]

		message = crm_bridge.modern(rows, "CRM Lead", "LEAD-1")[0]

		self.assertEqual(message.mime_type, "image/png")
		self.assertEqual(message.media_url, "/files/photo.png")

	def test_unknown_status_is_pending(self):
		self.assertEqual(crm_bridge.STATUS.get("", "Pending"), "Pending")


class TestInactive(UnitTestCase):
	@patch.object(crm_bridge, "active", return_value=False)
	def test_reads_are_empty_and_flags_false_when_crm_is_not_shared(self, _active):
		self.assertFalse(crm_bridge.is_whatsapp_installed())
		self.assertFalse(crm_bridge.is_whatsapp_enabled())
		self.assertEqual(crm_bridge.get_whatsapp_messages("CRM Lead", "LEAD-1"), [])
		self.assertEqual(crm_bridge.get_messages('[["CRM Lead", "LEAD-1"]]'), [])
		self.assertEqual(crm_bridge.get_sendable_templates("CRM Lead"), [])

	@patch.object(crm_bridge, "active", return_value=False)
	def test_sends_are_refused_when_crm_is_not_shared(self, _active):
		with self.assertRaises(frappe.ValidationError):
			crm_bridge.send_message(
				"919000000001", "Hi", reference_doctype="CRM Lead", reference_docname="L1"
			)
