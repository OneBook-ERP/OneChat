from unittest.mock import patch

import frappe

from onechat.tests.compat import IntegrationTestCase
from onechat.workspace import notifications

CONTACT = "OneChat Contact"


def make_contact(**values):
	name = f"WC-T-{frappe.generate_hash(length=8)}"
	frappe.get_doc(
		{
			"doctype": CONTACT,
			"name": name,
			"contact_name": "Leo Daniel",
			"mobile_no": "919999900002",
			**values,
		}
	).db_insert()
	return name


class TestPaymentAlert(IntegrationTestCase):
	def alert(self, contact, senders=(), settings=None, key=None):
		key = key or frappe.generate_hash(length=10)
		with (
			patch.object(notifications, "stored", return_value=settings or {}),
			patch.object(notifications, "notify") as notify,
			patch.object(frappe, "publish_realtime") as realtime,
		):
			told = notifications.payment_alert(key, contact, "₹ 1,200.00", "SINV-T-0012", senders)
		return told, notify, realtime

	def test_assigned_agent_is_told(self):
		contact = make_contact(assigned_to="agent@example.com")

		told, notify, realtime = self.alert(contact, senders=["sender@example.com"])

		self.assertEqual(told, ["agent@example.com"])
		self.assertEqual(notify.call_args.args[0], "agent@example.com")
		self.assertIn("₹ 1,200.00 paid by Leo Daniel for SINV-T-0012", notify.call_args.args[1])
		self.assertEqual(realtime.call_args.args[0], "onechat_payment")

	def test_sender_is_told_when_nobody_is_assigned(self):
		contact = make_contact()

		told, _notify, _realtime = self.alert(
			contact, senders=["sender@example.com", "sender@example.com", "Guest"]
		)

		self.assertEqual(told, ["sender@example.com"])

	def test_each_payment_alerts_once(self):
		contact = make_contact(assigned_to="agent@example.com")
		key = frappe.generate_hash(length=10)

		first, _notify, _realtime = self.alert(contact, key=key)
		second, notify, _realtime = self.alert(contact, key=key)

		self.assertEqual(first, ["agent@example.com"])
		self.assertEqual(second, [])
		notify.assert_not_called()

	def test_agents_who_turned_payment_alerts_off_are_skipped(self):
		contact = make_contact(assigned_to="agent@example.com")

		told, notify, _realtime = self.alert(contact, settings={"events": {"payments": 0}})

		self.assertEqual(told, [])
		notify.assert_not_called()

	def test_unknown_chat_is_ignored(self):
		told, notify, _realtime = self.alert("WC-T-missing")

		self.assertEqual(told, [])
		notify.assert_not_called()
