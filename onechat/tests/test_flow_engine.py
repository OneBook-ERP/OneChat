import json

import frappe

from onechat.automation import engine, steps
from onechat.tests.compat import UnitTestCase


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

	def test_order_flow_sees_the_order_and_routes_on_the_result(self):
		graph = {
			"nodes": [
				node("start", "order_placed"),
				node("order", "create_sales_order", save_as="order"),
				node("ok", "send_message", text="{{order.count}} items, total {{records.order.grand_total}}"),
				node("none", "send_message", text="No items"),
				node("submit", "submit_record", doctype="Sales Order", name="{{records.order.name}}"),
			],
			"edges": [
				edge("start", "order"),
				edge("order", "ok", "done"),
				edge("order", "none", "no_items"),
				edge("ok", "submit"),
			],
		}
		result = engine.simulate(json.dumps(graph))

		self.assertEqual(
			self.texts(result),
			[
				"Create a Sales Order for this WhatsApp order",
				"2 items, total 900",
				"Submit Sales Order (test)",
			],
		)
		self.assertTrue(result["done"])

	def test_record_steps_follow_the_type_saved_by_an_earlier_step(self):
		graph = {
			"nodes": [
				node("start", "order_placed"),
				node("quote", "create_from_order", doctype="Quotation", save_as="order"),
				node("submit", "submit_record", same_as_record=1, name="{{records.order.name}}"),
				node(
					"make",
					"make_record",
					same_as_record=1,
					doctype="Sales Order",
					name="{{records.order.name}}",
				),
			],
			"edges": [
				edge("start", "quote"),
				edge("quote", "submit", "done"),
				edge("submit", "make", "done"),
			],
		}
		result = engine.simulate(json.dumps(graph))

		self.assertEqual(
			self.texts(result),
			[
				"Create a Quotation for this WhatsApp order",
				"Submit Quotation (test)",
				"Make a Sales Order from Quotation (test)",
			],
		)


class TestAdvancedSteps(UnitTestCase):
	def test_values_emails_and_deletes_are_described_in_test_chat(self):
		graph = {
			"nodes": [
				node("start", "manual_trigger"),
				node(
					"keep", "set_variable", variables={"slot": "Evening", "who": "context.contact.first_name"}
				),
				node("say", "send_message", text="{{vars.who}}, delivery in the {{vars.slot}}"),
				node("mail", "send_email", to="team@example.com", subject="Slot {{vars.slot}}", message="Hi"),
				node("drop", "submit_record", action="delete", doctype="Sales Order", name="SO-1"),
			],
			"edges": [edge("start", "keep"), edge("keep", "say"), edge("say", "mail"), edge("mail", "drop")],
		}
		result = engine.simulate(json.dumps(graph))

		self.assertEqual(
			[message["text"] for message in result["messages"]],
			[
				"Test, delivery in the Evening",
				"Email team@example.com: Slot Evening",
				"Delete Sales Order SO-1",
			],
		)
		self.assertTrue(result["done"])

	def test_addresses_split_on_commas_and_spaces(self):
		self.assertEqual(steps.addresses("a@x.com, b@x.com;c@x.com"), ["a@x.com", "b@x.com", "c@x.com"])


class TestSummaries(UnitTestCase):
	def test_filter_values_understand_operators(self):
		self.assertEqual(steps.filter_value("> 0"), [">", "0"])
		self.assertEqual(steps.filter_value("!= Paid"), ["!=", "Paid"])
		self.assertEqual(steps.filter_value("in Overdue, Unpaid"), ["in", ["Overdue", "Unpaid"]])
		self.assertEqual(steps.filter_value("like %acme%"), ["like", "%acme%"])
		self.assertEqual(steps.filter_value("is not set"), ["is", "not set"])
		self.assertEqual(steps.filter_value("Paid"), "Paid")
		self.assertEqual(steps.filter_value(5), 5)

	def test_summary_lines_count_total_and_overflow(self):
		rows = [{"name": f"INV-{n}", "customer_name": "Acme", "outstanding_amount": 100} for n in range(4)]
		graph = {
			"nodes": [
				node("start", "manual_trigger"),
				node(
					"sum",
					"summarize_list",
					list="{{records.unpaid}}",
					line="{{row.customer_name}} {{row.outstanding_amount}} ({{row.name}})",
					separator="semicolon",
					total_field="outstanding_amount",
					limit=2,
				),
				node(
					"say",
					"send_message",
					text="{{vars.summary.count}} unpaid, {{vars.summary.total}}: {{vars.summary.text}}",
				),
			],
			"edges": [edge("start", "sum"), edge("sum", "say", "found")],
		}
		context = {
			"records": {"unpaid": rows},
			"contact": {"first_name": "T", "mobile_no": "1"},
			"answers": {},
			"vars": {},
		}
		run = engine.Run(frappe._dict(name="t"), engine.Graph(json.dumps(graph)), context, simulate=True)
		run.execute(["start"])

		self.assertEqual(
			run.outbox[-1]["text"], "4 unpaid, 400: Acme 100 (INV-0); Acme 100 (INV-1); + 2 more"
		)

	def test_template_values_have_no_line_breaks(self):
		self.assertEqual(steps.param_text("a\n b\n\nc"), "a · b · c")


class TestTableRows(UnitTestCase):
	def rows(self, context, **config):
		return steps.table_rows(frappe._dict(context=context), {"rows_field": "items", **config})

	def test_one_row_per_entry_with_row_values(self):
		context = {"order": engine.sample_order()}
		result = self.rows(
			context,
			rows_from="{{order.items}}",
			row_fields={"item_code": "{{row.item_code}}", "qty": "{{row.qty}}", "warehouse": ""},
		)

		self.assertEqual(
			result, {"items": [{"item_code": "SAMPLE-1", "qty": 2}, {"item_code": "SAMPLE-2", "qty": 1}]}
		)

	def test_no_table_means_no_rows(self):
		self.assertEqual(steps.table_rows(frappe._dict(context={}), {}), {})

	def test_a_value_that_is_not_a_list_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.rows({"order": {"total": 900}}, rows_from="{{order.total}}", row_fields={"qty": "1"})


class TestSchedule(UnitTestCase):
	def test_cron_from_friendly_settings(self):
		self.assertEqual(engine.cron_of({"frequency": "daily", "time": "09:30"}), "30 9 * * *")
		self.assertEqual(
			engine.cron_of({"frequency": "weekly", "time": "18:00", "weekday": "1"}), "0 18 * * 1"
		)
		self.assertEqual(engine.cron_of({"frequency": "monthly", "time": "08:00", "day": "31"}), "0 8 28 * *")
		self.assertEqual(engine.cron_of({"frequency": "hourly", "time": "00:15"}), "15 * * * *")
		self.assertEqual(engine.cron_of({"frequency": "cron", "schedule": "*/5 * * * *"}), "*/5 * * * *")
