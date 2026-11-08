from types import SimpleNamespace
from unittest.mock import patch

import frappe

from onechat.assistant import bot, llm, providers
from onechat.automation import ai_agent, run_as
from onechat.inbox import read_receipts
from onechat.tests.compat import IntegrationTestCase, UnitTestCase


def turn(text="", calls=()):
	return providers.Turn(text, [{"id": f"c{i}", "name": n, "input": a} for i, (n, a) in enumerate(calls)])


def fake_target():
	return frappe._dict(name="m", label="M", model="anthropic/claude-haiku-5-5", api_key="k", api_base=None)


class TestBotLoop(UnitTestCase):
	def respond(self, turns, history=None, config=None):
		seen = []

		def step(provider, messages):
			seen.append([dict(row) for row in messages])
			return turns.pop(0)

		ctx = bot.Context("C-1", config or {}, simulate=True)
		with (
			patch.object(llm, "resolve", return_value=fake_target()),
			patch.object(providers.Provider, "step", step),
			patch.object(
				bot,
				"specs",
				return_value=[
					{"name": n, "description": n, "schema": {}} for n in ("handover", "find_products")
				],
			),
			patch.object(bot, "system_prompt", return_value="rules"),
		):
			return bot.respond(
				ctx, history if history is not None else [{"role": "user", "content": "hi"}]
			), seen

	def test_plain_reply(self):
		outcome, _seen = self.respond([turn("Hi! How can I help?")])
		self.assertEqual(outcome.text, "Hi! How can I help?")
		self.assertFalse(outcome.handover)

	def test_handover_stops_without_running_tools(self):
		outcome, _seen = self.respond([turn("One moment", [("handover", {"reason": "wants a person"})])])
		self.assertTrue(outcome.handover)
		self.assertEqual(outcome.reason, "wants a person")
		self.assertEqual(outcome.text, "One moment")

	def test_tool_results_feed_the_next_round(self):
		with patch.dict(
			bot.HANDLERS, {"find_products": lambda ctx, args: {"products": [{"item_code": "SOFA"}]}}
		):
			outcome, seen = self.respond(
				[turn(calls=[("find_products", {"text": "sofa"})]), turn("We have SOFA.")]
			)
		self.assertEqual(outcome.text, "We have SOFA.")
		self.assertIn("SOFA", seen[1][-1]["content"])

	def test_tools_outside_the_list_are_refused(self):
		outcome, seen = self.respond([turn(calls=[("create_order", {"items": []})]), turn("Sorry.")])
		self.assertIn("not available", seen[1][-1]["content"])

	def test_an_empty_chat_gets_an_opener(self):
		_outcome, seen = self.respond([turn("Hello!")], history=[])
		self.assertEqual(seen[0][-1]["content"], bot.OPENER)

	def test_endless_tool_use_hands_over(self):
		with patch.dict(bot.HANDLERS, {"find_products": lambda ctx, args: {}}):
			outcome, _seen = self.respond([turn(calls=[("find_products", {"text": "x"})])] * bot.MAX_ROUNDS)
		self.assertTrue(outcome.handover)

	def test_history_starts_with_the_customer_and_merges_turns(self):
		rows = [("assistant", "Welcome"), ("user", "hi"), ("user", "price?"), ("assistant", "Sure")]
		self.assertEqual(
			bot.merged(rows),
			[{"role": "user", "content": "hi\nprice?"}, {"role": "assistant", "content": "Sure"}],
		)

	def test_order_lines_are_checked(self):
		self.assertEqual(
			bot.order_rows({"items": [{"item_code": "A", "qty": 2}]}), [{"item_code": "A", "qty": 2.0}]
		)
		for bad in (
			{"items": []},
			{"items": [{"item_code": "A", "qty": 0}]},
			{"items": [{"item_code": "A", "qty": 5000}]},
		):
			self.assertRaises(frappe.ValidationError, bot.order_rows, bad)


class TestScope(UnitTestCase):
	def test_assistant_prompts_keep_to_the_business(self):
		from onechat.assistant import api

		for prompt in (api.SYSTEM, api.GLOBAL):
			self.assertIn(api.SCOPE, prompt)
			self.assertNotIn("{SCOPE}", prompt)

	def test_bot_prompt_keeps_to_the_business(self):
		with patch.object(bot, "business_name", return_value="Furniture Street"):
			prompt = bot.system_prompt(bot.Context(None, {}))
		self.assertIn("Only help with Furniture Street", prompt)


class TestTypingIndicator(UnitTestCase):
	def typing(self, mode, channel="WhatsApp", enabled=True):
		row = frappe._dict(message_id="wamid.1", whatsapp_account="WB")
		with (
			patch.object(read_receipts, "latest_incoming", return_value=row),
			patch.object(read_receipts, "mode", return_value=mode),
			patch.object(read_receipts, "typing_on", return_value=enabled),
			patch.object(frappe, "get_doc", return_value=frappe._dict(channel=channel)),
			patch.object(read_receipts, "post") as post,
			patch.object(read_receipts, "act") as act,
		):
			read_receipts.typing("C-1")
		return post, act

	def test_whatsapp_shows_typing_on_the_last_customer_message(self):
		post, _act = self.typing(read_receipts.ON_OPEN)
		payload = post.call_args.args[1]
		self.assertEqual(payload["message_id"], "wamid.1")
		self.assertEqual(payload["typing_indicator"], {"type": "text"})

	def test_instagram_uses_typing_on(self):
		_post, act = self.typing(read_receipts.ON_ARRIVAL, "Instagram")
		self.assertEqual(act.call_args.args[2], "typing_on")

	def test_no_typing_when_read_receipts_are_off(self):
		post, act = self.typing(read_receipts.NEVER)
		post.assert_not_called()
		act.assert_not_called()

	def test_no_typing_when_the_number_turns_it_off(self):
		post, act = self.typing(read_receipts.ON_OPEN, enabled=False)
		post.assert_not_called()
		act.assert_not_called()


class TestModelChoice(UnitTestCase):
	def test_the_step_model_wins_over_settings(self):
		settings = frappe._dict(bot_model="Bot", assistant_model="Assistant")
		with patch.object(frappe, "get_cached_doc", return_value=settings):
			self.assertEqual(bot.model_name({"model": "Step"}), "Step")
			self.assertEqual(bot.model_name({}), "Bot")
			settings.bot_model = None
			self.assertEqual(bot.model_name(), "Assistant")


class TestAgentStep(IntegrationTestCase):
	def run_obj(self, simulate=False):
		sent, notes = [], []
		return SimpleNamespace(
			simulate=simulate,
			state={},
			context={},
			contact=None,
			session=frappe._dict(name="SESSION-1"),
			send=lambda **values: sent.append(values),
			note=notes.append,
			sent=sent,
			notes=notes,
		)

	def test_begin_queues_a_turn_and_waits(self):
		with patch.object(frappe, "enqueue") as enqueue:
			result = ai_agent.begin(self.run_obj(), "agent", {})
		self.assertEqual(result.wait, "Reply")
		self.assertEqual(enqueue.call_args.kwargs["session"], "SESSION-1")
		self.assertEqual(
			frappe.cache().get_value(ai_agent.token_key("SESSION-1")), enqueue.call_args.kwargs["token"]
		)

	def test_live_test_chat_uses_real_records_but_sends_nothing(self):
		run = self.run_obj(simulate=True)
		run.contact = "WC-MISSING"
		run.context = {"test": {"live": True}}
		with patch.object(bot, "respond", return_value=bot.Outcome(text="ok")) as respond:
			ai_agent.begin(run, "agent", {})
		ctx = respond.call_args.args[0]
		self.assertFalse(ctx.simulate)
		self.assertTrue(ctx.test)
		self.assertEqual(run.sent[0]["message"], "ok")

	def test_resume_outcomes(self):
		run = self.run_obj()
		self.assertEqual(ai_agent.resume(run, "agent", {}, {"kind": "timeout"}).handle, "no_reply")
		result = ai_agent.resume(run, "agent", {}, {"kind": "ai", "reason": "limit"})
		self.assertEqual(result.handle, "handover")
		self.assertEqual(run.context["ai"]["handover_reason"], "limit")
		with patch.object(frappe, "enqueue"):
			self.assertEqual(
				ai_agent.resume(run, "agent", {}, {"kind": "reply", "message": {"text": "hi"}}).wait, "Reply"
			)

	def test_test_chat_replies_right_away(self):
		run = self.run_obj(simulate=True)
		with patch.object(bot, "respond", return_value=bot.Outcome(text="Hello there")):
			result = ai_agent.begin(run, "agent", {})
		self.assertEqual(result.wait, "Reply")
		self.assertEqual(run.sent[0]["message"], "Hello there")
		with patch.object(
			bot, "respond", return_value=bot.Outcome(text="Bye", handover=True, reason="person")
		):
			result = ai_agent.resume(
				run, "agent", {}, {"kind": "reply", "message": {"text": "a person please"}}
			)
		self.assertEqual(result.handle, "handover")
		self.assertEqual(
			[row["role"] for row in run.state["ai"]["agent"]], ["assistant", "user", "assistant"]
		)


class TestTakeTurn(IntegrationTestCase):
	def setUp(self):
		self.session = frappe._dict(
			name="SESSION-2", contact="C-2", whatsapp_account=None, phone="91", flow="F"
		)
		frappe.cache().delete_value(ai_agent.count_key("SESSION-2"))

	def take(self, user="Administrator", current=True, outcome=None, limit=None):
		calls = {"sent": [], "handover": []}
		with (
			patch.object(ai_agent.time, "sleep"),
			patch.object(ai_agent, "current", return_value=current),
			patch.object(ai_agent, "load_session", return_value=self.session),
			patch.object(ai_agent, "node_config", return_value={}),
			patch.object(ai_agent, "limit_reason", return_value=limit),
			patch.object(ai_agent, "send", side_effect=lambda doc, text: calls["sent"].append(text)),
			patch.object(
				ai_agent, "hand_over", side_effect=lambda doc, reason: calls["handover"].append(reason)
			),
			patch.object(run_as, "automation_user", return_value=user),
			patch.object(bot, "history_of", return_value=[{"role": "user", "content": "hi"}]),
			patch.object(bot, "respond", return_value=outcome or bot.Outcome(text="Hi!")),
		):
			ai_agent.take_turn("SESSION-2", "agent", "token")
		return calls

	def test_a_newer_message_or_agent_skips_the_turn(self):
		self.assertEqual(self.take(current=False), {"sent": [], "handover": []})

	def test_without_an_automation_user_it_hands_over(self):
		calls = self.take(user=None)
		self.assertEqual(calls["sent"], [])
		self.assertEqual(len(calls["handover"]), 1)

	def test_limits_hand_over(self):
		self.assertEqual(self.take(limit="too many")["handover"], ["too many"])

	def test_reply_is_sent_and_counted(self):
		calls = self.take()
		self.assertEqual(calls["sent"], ["Hi!"])
		self.assertEqual(frappe.cache().get_value(ai_agent.count_key("SESSION-2")), 1)

	def test_ai_handover_sends_its_last_words_first(self):
		calls = self.take(outcome=bot.Outcome(text="Connecting you", handover=True, reason="angry"))
		self.assertEqual(calls, {"sent": ["Connecting you"], "handover": ["angry"]})
