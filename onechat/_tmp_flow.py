import json

import frappe

FLOW_NAME = "Order an item by name"


def node(i, kind, **config):
	return {
		"id": i,
		"type": "custom",
		"position": {"x": 0, "y": 0},
		"data": {"nodeType": kind, "config": config},
	}


def edge(s, t, h=None):
	return {
		"id": f"e-{s}-{t}-{h or 'next'}",
		"source": s,
		"target": t,
		"sourceHandle": h,
		"targetHandle": None,
	}


def option(i, title):
	return {"id": i, "title": title, "description": ""}


def graph():
	nodes = [
		node("start", "message_received", match="any"),
		node("scan", "find_items", text="{{last_reply}}", doctype="Item", field="item_name", save_as="items"),
		node(
			"typed",
			"condition",
			rules={
				"match": "all",
				"rules": [{"field": "{{vars.items.quantities}}", "operator": "greater_than", "value": "0"}],
			},
		),
		node(
			"asked",
			"condition",
			rules={
				"match": "any",
				"rules": [
					{"field": "{{last_reply}}", "operator": "contains", "value": "order"},
					{"field": "{{last_reply}}", "operator": "contains", "value": "buy"},
				],
			},
		),
		node("quiet", "end"),
		node(
			"ask",
			"ask_question",
			text="What would you like to order? Send each item with its quantity, for example:\n*apple 2, orange 3*",
			save_as="items_text",
		),
		node(
			"find",
			"find_items",
			text="{{answers.items_text}}",
			doctype="Item",
			field="item_name",
			save_as="items",
		),
		node(
			"partial",
			"send_buttons",
			text="We found:\n{{vars.items.text}}\n\nWe could not find: *{{vars.items.unknown_text}}*",
			buttons=[
				option("go", "Order the found items"),
				option("retry", "Change my order"),
				option("human", "Talk to us"),
			],
		),
		node(
			"missing",
			"send_buttons",
			text="Sorry, we could not find *{{vars.items.unknown_text}}*. Please check the name and send it again with the quantity.",
			buttons=[option("retry", "Try again"), option("human", "Talk to us")],
		),
		node("human", "handover", text="Connecting you to our team.", mode="round_robin"),
		node(
			"order",
			"create_from_order",
			doctype="Sales Order",
			items_from="{{vars.items.lines}}",
			save_as="order",
		),
		node(
			"lines",
			"summarize_list",
			list="{{records.order.items}}",
			line="{{row.qty}} × {{row.item_name}} @ {{row.rate}} = {{row.amount}}",
			separator="newline",
			save_as="lines",
		),
		node(
			"confirm",
			"send_buttons",
			text="Your order:\n\n{{vars.lines.text}}\n\nTotal: *{{records.order.grand_total}} {{records.order.currency}}*\n\nShall we place the order?",
			buttons=[option("yes", "Confirm order"), option("no", "Cancel")],
			timeout=24,
		),
		node("submit", "submit_record", name="{{records.order.name}}", same_as_record=True, save_as="order"),
		node("drop", "submit_record", action="delete", name="{{records.order.name}}", same_as_record=True),
		node(
			"placed",
			"send_message",
			text="Order *{{records.order.name}}* is placed ✅\nTotal: {{records.order.grand_total}} {{records.order.currency}}\n\nThank you!",
		),
		node("cancelled", "send_message", text="No problem, the order was not placed."),
	]
	edges = [
		edge("start", "scan"),
		edge("scan", "order", "found"),
		edge("scan", "partial", "partial"),
		edge("scan", "typed", "none"),
		edge("scan", "human", "error"),
		edge("typed", "missing", "true"),
		edge("typed", "asked", "false"),
		edge("asked", "ask", "true"),
		edge("asked", "quiet", "false"),
		edge("ask", "find", "answered"),
		edge("find", "order", "found"),
		edge("find", "partial", "partial"),
		edge("find", "missing", "none"),
		edge("find", "human", "error"),
		edge("partial", "order", "go"),
		edge("partial", "ask", "retry"),
		edge("partial", "human", "human"),
		edge("missing", "ask", "retry"),
		edge("missing", "human", "human"),
		edge("order", "lines", "done"),
		edge("lines", "confirm", "found"),
		edge("lines", "confirm", "empty"),
		edge("order", "human", "no_items"),
		edge("order", "human", "error"),
		edge("confirm", "submit", "yes"),
		edge("confirm", "drop", "no"),
		edge("confirm", "drop", "no_reply"),
		edge("submit", "placed", "done"),
		edge("submit", "human", "error"),
		edge("drop", "cancelled", "done"),
	]
	y = 0
	for n in nodes:
		n["position"] = {"x": 0, "y": y}
		y += 200
	return {"nodes": nodes, "edges": edges}


def run():
	from onechat.automation import engine, flows

	frappe.set_user("Administrator")
	g = json.dumps(graph())
	check = flows.validate_flow(g)
	print(
		"valid:",
		check["valid"],
		check["errors"],
		[i for i in check.get("issues", []) if i.get("level") == "error"],
	)
	flows.save_flow(
		FLOW_NAME,
		{"flow_name": FLOW_NAME, "is_active": 0, "graph_json": g, "trigger_type": "WhatsApp Incoming"},
	)
	frappe.db.commit()

	for first in (
		"abena gloves 2, safety glasses 3",
		"apple 1",
		"hi",
		"I want to order",
		"order abena gloves 2",
	):
		state = {
			"context": {
				"trigger": "test",
				"contact": {
					"name": None,
					"display_name": "Leo Daniel",
					"first_name": "Leo",
					"mobile_no": "917094155303",
				},
				"answers": {},
				"vars": {},
				"message": {"text": first},
			}
		}
		r = engine.simulate(g, state)
		print(f"=== Customer: {first}")
		bot = [m["text"].replace("\n", " / ") for m in r["messages"]]
		for line in bot or ["(no reply, left for the team)"]:
			print("   ", line[:170])
