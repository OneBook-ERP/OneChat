import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import now_datetime

from onechat.instagram import send, webhook

ACCOUNT = "OneChat Instagram Test"
IG_ID = "17841400000000001"
CUSTOMER = "17841400000077777"


def message(**values):
	base = {
		"message_type": "Manual",
		"use_template": 0,
		"content_type": "text",
		"message": "Hello",
		"attach": None,
		"buttons": None,
		"source": "Agent",
	}
	base.update(values)
	return frappe._dict(base)


class TestInstagramSignature(UnitTestCase):
	def check(self, secrets, header, body=b"{}"):
		with (
			patch.object(webhook, "app_secrets", return_value=secrets),
			patch.object(frappe, "request", create=True) as request,
			patch.object(frappe, "get_request_header", return_value=header),
		):
			request.get_data.return_value = body
			return webhook.signed()

	def test_accepts_a_valid_signature(self):
		digest = hmac.new(b"s3cret", b"{}", hashlib.sha256).hexdigest()
		self.assertTrue(self.check({"s3cret"}, f"sha256={digest}"))

	def test_rejects_when_no_secret_is_configured(self):
		digest = hmac.new(b"s3cret", b"{}", hashlib.sha256).hexdigest()
		self.assertFalse(self.check(set(), f"sha256={digest}"))

	def test_rejects_missing_or_wrong_signature(self):
		self.assertFalse(self.check({"s3cret"}, None))
		self.assertFalse(self.check({"s3cret"}, "sha256=deadbeef"))


class TestInstagramRules(UnitTestCase):
	def rules(self, hours_ago, source="Agent"):
		last = now_datetime() - timedelta(hours=hours_ago) if hours_ago is not None else None
		with patch.object(send, "last_incoming", return_value=last):
			return send.rules(message(source=source), "WC-1")

	def test_reply_within_24_hours_is_a_response(self):
		self.assertEqual(self.rules(2), {"messaging_type": "RESPONSE"})

	def test_agent_after_24_hours_uses_human_agent_tag(self):
		self.assertEqual(self.rules(72), {"messaging_type": "MESSAGE_TAG", "tag": "HUMAN_AGENT"})

	def test_bot_after_24_hours_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.rules(72, source="Bot")

	def test_after_7_days_or_never_messaged_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.rules(24 * 8)
		with self.assertRaises(frappe.ValidationError):
			self.rules(None)


class TestInstagramBodies(UnitTestCase):
	def test_text(self):
		self.assertEqual(send.message_body(message(message="<p>Hi&nbsp;there</p>")), {"text": "Hi there"})

	def test_media_uses_a_public_url(self):
		with patch.object(send, "public_url", return_value="https://site/files/a.png"):
			body = send.message_body(message(content_type="image", attach="/private/files/a.png"))
		self.assertEqual(
			body, {"attachment": {"type": "image", "payload": {"url": "https://site/files/a.png"}}}
		)

	def test_buttons_become_quick_replies(self):
		spec = {"type": "button", "options": [{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}]}
		body = send.message_body(message(content_type="interactive", buttons=json.dumps(spec), message="Ok?"))
		self.assertEqual([reply["payload"] for reply in body["quick_replies"]], ["yes", "no"])

	def test_link_button_becomes_text_with_url(self):
		spec = {"type": "cta_url", "button": "Pay", "url": "https://pay.example/x"}
		body = send.message_body(
			message(content_type="interactive", buttons=json.dumps(spec), message="Pay here")
		)
		self.assertEqual(body, {"text": "Pay here\nhttps://pay.example/x"})

	def test_templates_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			send.message_body(message(message_type="Template", use_template=1))

	def test_reaction_and_unreaction(self):
		self.assertEqual(
			send.reaction_body(message(message="👍", reply_to_message_id="mid.1")),
			{"sender_action": "react", "payload": {"message_id": "mid.1", "reaction": "love"}},
		)
		self.assertEqual(
			send.reaction_body(message(message="", reply_to_message_id="mid.1"))["sender_action"], "unreact"
		)


class TestInstagramWebhook(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("OneChat Account", ACCOUNT):
			frappe.get_doc(
				{
					"doctype": "OneChat Account",
					"name": ACCOUNT,
					"account_name": ACCOUNT,
					"status": "Active",
					"channel": "Instagram",
					"ig_user_id": IG_ID,
				}
			).db_insert()
		self.account = frappe.get_doc("OneChat Account", ACCOUNT)
		lookup = patch.object(webhook, "lookup", return_value={"name": "Asha", "username": "asha.k"})
		lookup.start()
		self.addCleanup(lookup.stop)

	def event(self, mid, **message):
		return {
			"sender": {"id": CUSTOMER},
			"recipient": {"id": IG_ID},
			"timestamp": 1760000000000,
			"message": {"mid": mid, **message},
		}

	def stored(self, mid):
		return frappe.get_doc("OneChat Message", {"message_id": mid})

	def test_entries_resolve_to_the_account_by_instagram_id(self):
		payload = {
			"object": "instagram",
			"entry": [{"id": IG_ID, "messaging": [self.event("m.0", text="x")]}],
		}
		found = list(webhook.events(payload))
		self.assertEqual([account.name for account, _event in found], [ACCOUNT])

	def test_text_creates_an_instagram_contact_and_message(self):
		mid = f"m.{frappe.generate_hash(length=8)}"
		webhook.handle(self.event(mid, text="Price?"), self.account)

		doc = self.stored(mid)
		self.assertEqual((doc.type, doc.content_type, doc.message), ("Incoming", "text", "Price?"))
		self.assertEqual(doc.channel, "Instagram")
		contact = frappe.get_doc("OneChat Contact", doc.whatsapp_contact)
		self.assertEqual((contact.instagram_id, contact.instagram_username), (CUSTOMER, "asha.k"))

	def test_duplicate_events_are_ignored(self):
		mid = f"m.{frappe.generate_hash(length=8)}"
		webhook.handle(self.event(mid, text="Hi"), self.account)
		webhook.handle(self.event(mid, text="Hi"), self.account)
		self.assertEqual(frappe.db.count("OneChat Message", {"message_id": mid}), 1)

	def test_story_reply_and_quick_reply(self):
		story = f"m.{frappe.generate_hash(length=8)}"
		webhook.handle(
			self.event(story, text="Nice!", reply_to={"story": {"url": "https://cdn/s.jpg", "id": "s1"}}),
			self.account,
		)
		self.assertEqual(self.stored(story).content_type, "story_reply")
		self.assertEqual(self.stored(story).link_url, "https://cdn/s.jpg")

		quick = f"m.{frappe.generate_hash(length=8)}"
		webhook.handle(self.event(quick, text="Yes", quick_reply={"payload": "yes"}), self.account)
		self.assertEqual(json.loads(self.stored(quick).buttons), {"reply_id": "yes"})

	def test_echo_is_stored_as_an_outgoing_agent_message_without_sending(self):
		mid = f"m.{frappe.generate_hash(length=8)}"
		event = {
			"sender": {"id": IG_ID},
			"recipient": {"id": CUSTOMER},
			"message": {"mid": mid, "text": "Sent from the app", "is_echo": True},
		}
		with patch.object(send, "deliver") as deliver:
			webhook.receive_echo(event, ACCOUNT)
		deliver.assert_not_called()
		doc = self.stored(mid)
		self.assertEqual((doc.type, doc.source, doc.is_echo, doc.to), ("Outgoing", "Agent", 1, CUSTOMER))

	def test_read_marks_outgoing_messages_read(self):
		incoming = f"m.{frappe.generate_hash(length=8)}"
		webhook.handle(self.event(incoming, text="Hi"), self.account)
		outgoing = f"m.{frappe.generate_hash(length=8)}"
		webhook.receive_echo(
			{
				"sender": {"id": IG_ID},
				"recipient": {"id": CUSTOMER},
				"message": {"mid": outgoing, "text": "Hello"},
			},
			ACCOUNT,
		)
		webhook.handle({"sender": {"id": CUSTOMER}, "read": {"mid": outgoing}}, self.account)
		self.assertEqual(self.stored(outgoing).status, "read")
