import hashlib
import hmac
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from onechat.whatsapp import webhook


class TestWebhookParsing(UnitTestCase):
	def test_changes_yields_every_event_with_entry_id(self):
		payload = {
			"entry": [
				{"id": "waba-1", "changes": [{"field": "messages"}, {"field": "messages"}]},
				{"id": "waba-2", "changes": [{"field": "account_update"}]},
			]
		}

		result = list(webhook.changes(payload))

		self.assertEqual(len(result), 3)
		self.assertEqual(result[2], ("waba-2", {"field": "account_update"}))

	def test_changes_accepts_single_entry_object(self):
		payload = {"entry": {"id": "waba-1", "changes": [{"field": "messages"}]}}

		self.assertEqual(len(list(webhook.changes(payload))), 1)

	def test_failure_reason_includes_code_and_details(self):
		status = {
			"errors": [
				{
					"code": 131047,
					"title": "Re-engagement message",
					"error_data": {"details": "More than 24 hours have passed."},
				}
			]
		}

		self.assertEqual(
			webhook.failure_reason(status),
			"Re-engagement message (131047): More than 24 hours have passed.",
		)

	def test_failure_reason_without_errors(self):
		self.assertIsNone(webhook.failure_reason({"status": "failed"}))


class TestWebhookSignature(UnitTestCase):
	body = b'{"entry": []}'

	def sign(self, secret):
		return "sha256=" + hmac.new(secret.encode(), self.body, hashlib.sha256).hexdigest()

	def check(self, secrets, header):
		request = MagicMock()
		request.get_data.return_value = self.body
		with (
			patch.object(webhook, "app_secrets", return_value=secrets),
			patch.object(webhook.frappe, "get_request_header", return_value=header),
			patch.object(webhook.frappe, "request", request, create=True),
		):
			return webhook.signed()

	def test_rejects_without_configured_secret(self):
		with patch.object(webhook.frappe, "log_error"):
			self.assertFalse(self.check(set(), self.sign("s3cret")))

	def test_accepts_valid_signature(self):
		self.assertTrue(self.check({"s3cret"}, self.sign("s3cret")))

	def test_rejects_wrong_signature(self):
		self.assertFalse(self.check({"s3cret"}, self.sign("other")))

	def test_rejects_missing_signature(self):
		self.assertFalse(self.check({"s3cret"}, None))


class TestMessageStatus(IntegrationTestCase):
	account = "OneChat Test Account"

	def setUp(self):
		if not frappe.db.exists("OneChat Account", self.account):
			frappe.get_doc(
				{
					"doctype": "OneChat Account",
					"name": self.account,
					"account_name": self.account,
					"status": "Active",
				}
			).db_insert()

	def make_message(self, status):
		doc = frappe.get_doc(
			{
				"doctype": "OneChat Message",
				"type": "Outgoing",
				"whatsapp_account": self.account,
				"to": "919999999999",
				"message": "Test",
				"content_type": "text",
				"message_type": "Manual",
				"name": frappe.generate_hash(length=10),
				"message_id": f"wamid.{frappe.generate_hash(length=12)}",
				"status": status,
			}
		)
		doc.db_insert()
		return doc

	def status_of(self, doc):
		return frappe.db.get_value("OneChat Message", doc.name, ["status", "error_message"], as_dict=True)

	def test_status_moves_forward(self):
		doc = self.make_message("sent")

		webhook.update_message_status({"id": doc.message_id, "status": "read"})

		self.assertEqual(self.status_of(doc).status, "read")

	def test_status_never_moves_backward(self):
		doc = self.make_message("read")

		webhook.update_message_status({"id": doc.message_id, "status": "delivered"})

		self.assertEqual(self.status_of(doc).status, "read")

	def test_failed_status_stores_reason(self):
		doc = self.make_message("sent")

		webhook.update_message_status(
			{
				"id": doc.message_id,
				"status": "failed",
				"errors": [{"code": 131026, "title": "Message undeliverable"}],
			}
		)

		row = self.status_of(doc)
		self.assertEqual(row.status, "failed")
		self.assertEqual(row.error_message, "Message undeliverable (131026)")

	def test_unknown_message_is_ignored(self):
		webhook.update_message_status({"id": "wamid.unknown", "status": "read"})
