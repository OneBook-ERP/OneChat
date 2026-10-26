import json
from unittest.mock import patch

import frappe

from onechat.automation import engine, flows
from onechat.campaigns.chat_links import build_instagram_url
from onechat.instagram import webhook
from onechat.tests.compat import IntegrationTestCase, UnitTestCase

ACCOUNT = "OneChat Instagram Features Test"
IG_ID = "17841400000000002"
CUSTOMER = "17841400000055555"


def graph(trigger_config, *steps):
	nodes = [
		{
			"id": "t",
			"type": "message_received",
			"data": {"nodeType": "message_received", "config": trigger_config},
		}
	]
	edges = []
	for index, kind in enumerate(steps):
		node_id = f"s{index}"
		nodes.append({"id": node_id, "type": kind, "data": {"nodeType": kind, "config": {}}})
		edges.append({"id": f"e{index}", "source": "t" if index == 0 else f"s{index - 1}", "target": node_id})
	return json.dumps({"nodes": nodes, "edges": edges})


class TestTriggerChannel(UnitTestCase):
	def test_unset_channel_means_whatsapp_only(self):
		self.assertTrue(engine.channel_fits({}, "WhatsApp"))
		self.assertFalse(engine.channel_fits({}, "Instagram"))

	def test_instagram_and_any(self):
		self.assertTrue(engine.channel_fits({"channel": "Instagram"}, "Instagram"))
		self.assertFalse(engine.channel_fits({"channel": "Instagram"}, "WhatsApp"))
		self.assertTrue(engine.channel_fits({"channel": "Any"}, "Instagram"))
		self.assertTrue(engine.channel_fits({"channel": "Any"}, "WhatsApp"))


class TestInstagramFlowValidation(UnitTestCase):
	@patch.object(flows, "require_admin")
	def test_whatsapp_only_steps_fail_on_instagram_flows(self, _admin):
		result = flows.validate_flow(graph({"channel": "Instagram", "match": "any"}, "send_template"))
		self.assertTrue(any("send_template" in error for error in result["errors"]))

	@patch.object(flows, "require_admin")
	def test_whatsapp_flows_may_use_templates(self, _admin):
		result = flows.validate_flow(graph({"match": "any"}, "send_template"))
		self.assertFalse(any("only work on WhatsApp" in error for error in result["errors"]))


class TestInstagramChatLinkUrl(UnitTestCase):
	def test_url_carries_the_ref_when_tracked(self):
		self.assertEqual(build_instagram_url("mybrand", "SUMMER", 1), "https://ig.me/m/mybrand?ref=SUMMER")
		self.assertEqual(build_instagram_url("mybrand", "SUMMER", 0), "https://ig.me/m/mybrand")
		self.assertIsNone(build_instagram_url(None, "SUMMER"))


class TestInstagramReferral(IntegrationTestCase):
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
					"ig_username": "mybrand",
				}
			).db_insert()
		self.account = frappe.get_doc("OneChat Account", ACCOUNT)
		self.code = f"IG{frappe.generate_hash(length=6).upper()}"
		self.link = frappe.get_doc(
			{
				"doctype": "OneChat Chat Link",
				"title": "Bio link",
				"whatsapp_account": ACCOUNT,
				"ref_code": self.code,
				"track": 1,
			}
		).insert(ignore_permissions=True)
		lookup = patch.object(webhook, "lookup", return_value={"username": "fan"})
		lookup.start()
		self.addCleanup(lookup.stop)

	def test_link_url_is_ig_me(self):
		self.assertEqual(self.link.link_url, f"https://ig.me/m/mybrand?ref={self.code}")

	def test_referral_event_then_message_is_attributed(self):
		party = {"sender": {"id": CUSTOMER}, "recipient": {"id": IG_ID}}
		webhook.handle({**party, "referral": {"ref": self.code.lower(), "source": "IG.ME"}}, self.account)
		mid = f"m.{frappe.generate_hash(length=8)}"
		webhook.handle({**party, "message": {"mid": mid, "text": "Hi"}}, self.account)

		self.assertEqual(
			frappe.db.get_value("OneChat Message", {"message_id": mid}, "chat_link"), self.link.name
		)


class TestInstagramOAuth(IntegrationTestCase):
	def setUp(self):
		from onechat.instagram import oauth

		self.oauth = oauth
		self.name = f"OneChat IG OAuth {frappe.generate_hash(length=6)}"
		frappe.get_doc(
			{
				"doctype": "OneChat Account",
				"account_name": self.name,
				"status": "Active",
				"channel": "Instagram",
				"app_id": "1234",
				"app_secret": "s3cret",
			}
		).insert(ignore_permissions=True)
		admin = patch.object(oauth, "admin_only")
		admin.start()
		self.addCleanup(admin.stop)

	def location(self):
		return frappe.local.response.get("location") or ""

	def test_start_builds_the_authorize_url_and_remembers_the_state(self):
		url = self.oauth.start(self.name)
		self.assertTrue(url.startswith("https://www.instagram.com/oauth/authorize?"))
		self.assertIn("instagram_business_manage_messages", url)
		state = url.split("state=")[1].split("&")[0]
		self.assertEqual(frappe.cache().get_value(self.oauth.state_key(state))["account"], self.name)

	def test_unknown_state_is_refused(self):
		self.oauth.callback(code="abc", state="forged")
		self.assertIn("instagram=error", self.location())

	def test_cancelled_sign_in_reports_an_error(self):
		state = self.oauth.start(self.name).split("state=")[1].split("&")[0]
		self.oauth.callback(state=state, error="access_denied", error_description="User denied")
		self.assertIn("instagram=error", self.location())
		self.assertIsNone(frappe.cache().get_value(self.oauth.state_key(state)))

	def test_successful_sign_in_saves_a_long_lived_token(self):
		state = self.oauth.start(self.name).split("state=")[1].split("&")[0]
		short = type(
			"R",
			(),
			{
				"status_code": 200,
				"reason": "OK",
				"json": lambda self: {"access_token": "short", "user_id": 1},
			},
		)()
		long = type(
			"R",
			(),
			{
				"status_code": 200,
				"reason": "OK",
				"json": lambda self: {"access_token": "long", "expires_in": 5184000},
			},
		)()
		with (
			patch.object(self.oauth.requests, "post", return_value=short),
			patch.object(self.oauth.requests, "get", return_value=long),
			patch.object(self.oauth.accounts, "run_check") as check,
		):
			self.oauth.callback(code="abc#_", state=state)

		self.assertIn("instagram=connected", self.location())
		account = frappe.get_doc("OneChat Account", self.name)
		self.assertEqual(account.get_password("token"), "long")
		self.assertIsNotNone(account.token_expires_at)
		check.assert_called_once()
