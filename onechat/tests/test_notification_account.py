from unittest.mock import patch

import frappe

from onechat.onechat.doctype.whatsapp_notification.whatsapp_notification import WhatsAppNotification
from onechat.tests.compat import UnitTestCase


def rule(**values):
	doc = WhatsAppNotification.__new__(WhatsAppNotification)
	doc.__dict__.update({"send_from": "Default outgoing", "send_account": None, **values})
	return doc


class TestSendingAccount(UnitTestCase):
	def test_default_keeps_the_template_account(self):
		self.assertEqual(rule().sending_account("919999", "Brand"), "Brand")
		self.assertIsNone(rule().sending_account("919999"))

	def test_specific_account_wins(self):
		self.assertEqual(
			rule(send_from="Specific account", send_account="Support").sending_account("1", "Brand"),
			"Support",
		)

	def test_customer_account_follows_the_contact(self):
		values = {
			("OneChat Contact", "WC-1", "whatsapp_account"): "Support",
			("OneChat Account", "Support", "status"): "Active",
		}
		with (
			patch("onechat.inbox.conversations.find_contact", return_value="WC-1"),
			patch.object(frappe.db, "get_value", side_effect=lambda *args, **kwargs: values.get(args[:3])),
		):
			self.assertEqual(
				rule(send_from="Customer's account").sending_account("919999", "Brand"), "Support"
			)

	def test_customer_account_falls_back_when_inactive_or_unknown(self):
		values = {
			("OneChat Contact", "WC-1", "whatsapp_account"): "Old",
			("OneChat Account", "Old", "status"): "Inactive",
		}
		with (
			patch("onechat.inbox.conversations.find_contact", return_value="WC-1"),
			patch.object(frappe.db, "get_value", side_effect=lambda *args, **kwargs: values.get(args[:3])),
		):
			self.assertEqual(rule(send_from="Customer's account").sending_account("919999", "Brand"), "Brand")
		with patch("onechat.inbox.conversations.find_contact", return_value=None):
			self.assertEqual(rule(send_from="Customer's account").sending_account("919999", "Brand"), "Brand")
