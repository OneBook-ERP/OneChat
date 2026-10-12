from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import now_datetime

from onechat.automation import engine
from onechat.instagram import comments, send

ACCOUNT = "OneChat Instagram Comments Test"
IG_ID = "17841400000000003"


def config(**values):
	return frappe._dict({**comments.DEFAULTS, **values})


class TestCommentHiding(UnitTestCase):
	def test_hide_words_and_links(self):
		self.assertTrue(
			comments.should_hide("Buy cheap followers", config(ig_comment_hide_words="followers\nspam"))
		)
		self.assertFalse(comments.should_hide("Price?", config(ig_comment_hide_words="followers")))
		self.assertTrue(comments.should_hide("see www.spam.io", config(ig_comment_hide_links=1)))
		self.assertFalse(comments.should_hide("see www.spam.io", config(ig_comment_hide_links=0)))


class TestCommentTriggerMatching(UnitTestCase):
	def doc(self, **values):
		return frappe._dict(
			name="C1",
			content_type="comment",
			media_id="111",
			link_url="https://www.instagram.com/p/ABC/",
			**values,
		)

	def test_post_filter_accepts_ids_and_links(self):
		self.assertTrue(engine.post_matches({}, self.doc()))
		self.assertTrue(engine.post_matches({"posts": [{"value": "111"}]}, self.doc()))
		self.assertTrue(
			engine.post_matches({"posts": [{"value": "https://www.instagram.com/p/ABC/?igsh=x"}]}, self.doc())
		)
		self.assertFalse(engine.post_matches({"posts": [{"value": "999"}]}, self.doc()))

	@patch.object(engine, "replied_before", return_value=False)
	def test_comment_triggers_never_match_messages_and_vice_versa(self, _before):
		comment = self.doc()
		message = frappe._dict(name="M1", content_type="text")
		row = {"kind": "comment_received", "config": {"match": "any"}}
		self.assertEqual(engine.trigger_score(row, comment, {"text": "hi"}, "WC-1"), 55)
		self.assertEqual(engine.trigger_score(row, message, {"text": "hi"}, "WC-1"), 0)
		self.assertEqual(
			engine.trigger_score(
				{"kind": "message_received", "config": {"match": "any"}}, comment, {"text": "hi"}, "WC-1"
			),
			0,
		)

	@patch.object(engine, "replied_before", return_value=True)
	def test_once_per_person_per_post(self, _before):
		row = {"kind": "comment_received", "config": {"match": "any", "once_per_person": True}}
		self.assertEqual(engine.trigger_score(row, self.doc(), {"text": "hi"}, "WC-1"), 0)


class TestCommentReceiving(IntegrationTestCase):
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
		for target, value in ((comments, "post_link"), (comments.graph, "hide_comment")):
			patcher = patch.object(target, value, return_value="https://www.instagram.com/p/ABC/")
			patcher.start()
			self.addCleanup(patcher.stop)

	def value(self, **extra):
		return {
			"id": f"c.{frappe.generate_hash(length=8)}",
			"text": "price?",
			"from": {"id": "17841400000044444", "username": "fan.one"},
			"media": {"id": "111"},
			**extra,
		}

	def test_comment_is_stored_quietly_by_default(self):
		with patch.object(comments, "settings", return_value=config()):
			doc = comments.receive(self.value(), self.account)
		self.assertEqual((doc.content_type, doc.message, doc.media_id), ("comment", "price?", "111"))
		self.assertEqual(
			frappe.db.get_value("OneChat Contact", doc.whatsapp_contact, "instagram_username"), "fan.one"
		)
		self.assertFalse(frappe.db.get_value("OneChat Contact", doc.whatsapp_contact, "last_message_at"))

	def test_own_comments_and_thread_replies_are_skipped(self):
		with patch.object(comments, "settings", return_value=config()):
			self.assertIsNone(comments.receive(self.value(**{"from": {"id": IG_ID}}), self.account))
			self.assertIsNone(comments.receive(self.value(parent_id="c.parent"), self.account))

	def test_private_reply_once_and_within_seven_days(self):
		with patch.object(comments, "settings", return_value=config()):
			doc = comments.receive(self.value(), self.account)
		comments.check_private_reply(doc)
		frappe.db.set_value("OneChat Message", doc.name, "comment_replied", 1)
		with self.assertRaises(frappe.ValidationError):
			comments.check_private_reply(frappe.get_doc("OneChat Message", doc.name))

		old = frappe._dict(comment_replied=0, creation=now_datetime() - timedelta(days=8))
		with self.assertRaises(frappe.ValidationError):
			comments.check_private_reply(old)

	def test_private_reply_goes_to_the_comment(self):
		with patch.object(comments, "settings", return_value=config()):
			doc = comments.receive(self.value(), self.account)
		outgoing = frappe._dict(
			reply_to_comment=doc.message_id, content_type="text", message="Here you go", attach=None
		)
		outgoing.message_type, outgoing.use_template = "Manual", 0
		with patch.object(send.graph, "send", return_value={"message_id": "m.1"}) as sent:
			send.private_reply(outgoing, self.account)
		self.assertEqual(sent.call_args[0][1]["recipient"], {"comment_id": doc.message_id})
		self.assertEqual(frappe.db.get_value("OneChat Message", doc.name, "comment_replied"), 1)
