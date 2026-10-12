import json

from frappe.tests import UnitTestCase

from onechat.automation import engine


def node(node_id, kind, **config):
	return {
		"id": node_id,
		"type": "custom",
		"position": {"x": 0, "y": 0},
		"data": {"nodeType": kind, "config": config},
	}


def edge(source, target, handle=None):
	return {"id": f"{source}-{target}-{handle}", "source": source, "target": target, "sourceHandle": handle}


MENU = {
	"nodes": [
		node("start", "manual_trigger"),
		node("hello", "send_message", text="Hi {{first_name}}!"),
		node(
			"menu",
			"send_buttons",
			text="How can we help?",
			buttons=[{"id": "order", "title": "Track order"}, {"id": "human", "title": "Talk to us"}],
		),
		node(
			"ask", "ask_question", text="What is your order number?", save_as="order_no", answer_type="number"
		),
		node("thanks", "send_message", text="Looking up order {{answers.order_no}}"),
		node("handover", "handover", text="Connecting you to the team"),
	],
	"edges": [
		edge("start", "hello"),
		edge("hello", "menu"),
		edge("menu", "ask", "order"),
		edge("menu", "handover", "human"),
		edge("ask", "thanks", "answered"),
	],
}


class TestGraph(UnitTestCase):
	def test_trigger_and_handles(self):
		graph = engine.Graph(json.dumps(MENU))

		self.assertEqual(graph.trigger(), "start")
		self.assertEqual(graph.following("menu", "order", None), ["ask"])
		self.assertEqual(graph.following("menu", "other", None), [])
		self.assertTrue(graph.has_output("menu", "human"))


class TestSimulation(UnitTestCase):
	def run_chat(self, *replies):
		result = engine.simulate(json.dumps(MENU))
		transcript = [result]
		for reply in replies:
			result = engine.simulate(json.dumps(MENU), result["state"], reply)
			transcript.append(result)
		return transcript

	def texts(self, result):
		return [message["text"] for message in result["messages"]]

	def test_greets_and_waits_on_buttons(self):
		first = self.run_chat()[0]

		self.assertEqual(self.texts(first), ["Hi Test!", "How can we help?"])
		self.assertEqual(first["waiting"], {"node": "menu", "kind": "Reply"})
		self.assertEqual(
			[option["title"] for option in first["messages"][1]["options"]], ["Track order", "Talk to us"]
		)

	def test_button_branch_question_and_answer(self):
		chat = self.run_chat({"type": "button", "text": "Track order", "reply_id": "order"}, {"text": "4521"})

		self.assertEqual(self.texts(chat[1]), ["What is your order number?"])
		self.assertEqual(self.texts(chat[2]), ["Looking up order 4521"])
		self.assertTrue(chat[2]["done"])

	def test_typed_title_picks_the_button(self):
		chat = self.run_chat({"text": "talk to us"})

		self.assertEqual(self.texts(chat[1])[0], "Connecting you to the team")
		self.assertTrue(chat[1]["done"])

	def test_invalid_answer_is_retried(self):
		chat = self.run_chat(
			{"reply_id": "order", "type": "button", "text": "Track order"}, {"text": "not a number"}
		)

		self.assertFalse(chat[2]["done"])
		self.assertEqual(chat[2]["waiting"]["node"], "ask")

	def test_unknown_reply_nudges_then_waits(self):
		chat = self.run_chat({"text": "hello?"})

		self.assertFalse(chat[1]["done"])
		self.assertEqual(chat[1]["messages"][-1]["text"], "How can we help?")

	def test_loop_guard(self):
		graph = {
			"nodes": [
				node("start", "manual_trigger"),
				node("a", "set_variable", variables={}),
				node("b", "set_variable", variables={}),
			],
			"edges": [edge("start", "a"), edge("a", "b"), edge("b", "a")],
		}

		result = engine.simulate(json.dumps(graph))

		self.assertTrue(result["done"])
		self.assertEqual(result["messages"][-1]["from"], "error")

	def test_side_effects_are_described_not_run(self):
		graph = {
			"nodes": [node("start", "manual_trigger"), node("label", "add_label", label="VIP")],
			"edges": [edge("start", "label")],
		}
		result = engine.simulate(json.dumps(graph))

		self.assertEqual(result["messages"], [{"from": "system", "text": "Add the label VIP"}])
		self.assertTrue(result["done"])


class TestSchedule(UnitTestCase):
	def test_cron_from_friendly_settings(self):
		self.assertEqual(engine.cron_of({"frequency": "daily", "time": "09:30"}), "30 9 * * *")
		self.assertEqual(
			engine.cron_of({"frequency": "weekly", "time": "18:00", "weekday": "1"}), "0 18 * * 1"
		)
		self.assertEqual(engine.cron_of({"frequency": "monthly", "time": "08:00", "day": "31"}), "0 8 28 * *")
		self.assertEqual(engine.cron_of({"frequency": "hourly", "time": "00:15"}), "15 * * * *")
		self.assertEqual(engine.cron_of({"frequency": "cron", "schedule": "*/5 * * * *"}), "*/5 * * * *")
