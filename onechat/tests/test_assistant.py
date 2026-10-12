from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from onechat.assistant import api

ORDER = {
	"name": "create_document",
	"input": {
		"doctype": "Sales Order",
		"data": {
			"customer": "Leo Daniel A",
			"delivery_date": "2026-10-10",
			"items": [
				{"item_code": "CHAIR", "qty": 2, "rate": 1500},
				{"item_code": "TABLE", "qty": 1, "rate": 4000},
				{"item_code": "LAMP", "qty": 3},
			],
		},
	},
}


class TestConfirmCard(UnitTestCase):
	def test_create_card_summarises_items_and_total(self):
		card = api.card(ORDER)

		self.assertEqual(card["kind"], "create")
		self.assertEqual(card["title"], "Create Sales Order for 3 items?")
		self.assertEqual([line["item"] for line in card["lines"]], ["CHAIR", "TABLE", "LAMP"])
		self.assertEqual(card["total"], 7000)
		self.assertIn("Leo Daniel A", [field["value"] for field in card["fields"]])
		self.assertIsNone(card["warning"])

	def test_submit_card_warns_it_cannot_be_undone(self):
		card = api.card(
			{"name": "erp__submit_document", "input": {"doctype": "Sales Invoice", "name": "SINV-0012"}}
		)

		self.assertEqual(card["title"], "Submit Sales Invoice SINV-0012?")
		self.assertTrue(card["warning"])

	def test_values_sent_as_text_are_read(self):
		card = api.card(
			{
				"name": "update_document",
				"input": {"doctype": "Customer", "name": "C-1", "data": '{"mobile_no": "999"}'},
			}
		)

		self.assertEqual([field["value"] for field in card["fields"]], ["999"])

	def test_long_tables_are_cut_with_a_count(self):
		rows = [{"item_code": f"ITEM-{index}", "qty": 1, "rate": 1} for index in range(api.CARD_LINES + 5)]
		card = api.card(
			{"name": "create_document", "input": {"doctype": "Sales Order", "data": {"items": rows}}}
		)

		self.assertEqual(len(card["lines"]), api.CARD_LINES)
		self.assertEqual(card["more_lines"], 5)

	def test_other_tools_get_a_plain_title(self):
		self.assertEqual(api.card({"name": "create_dashboard", "input": {}})["title"], "Create dashboard?")


class TestChatMemory(UnitTestCase):
	def test_stored_turns_accept_text_lists_and_bad_values(self):
		self.assertEqual(api.stored_turns(frappe._dict(turns='[{"question": "hi"}]')), [{"question": "hi"}])
		self.assertEqual(api.stored_turns(frappe._dict(turns=[{"question": "hi"}])), [{"question": "hi"}])
		self.assertEqual(api.stored_turns(frappe._dict(turns="not json")), [])
		self.assertEqual(api.stored_turns(None), [])

	def test_recall_keeps_the_latest_turns_only(self):
		turns = [{"question": f"Question {index}", "reply": f"Answer {index}"} for index in range(6)]

		with patch.object(api, "memory", return_value=frappe._dict(turns=turns)):
			text = api.recall("WC-1")

		self.assertNotIn("Question 1", text)
		self.assertIn("Question 2", text)
		self.assertIn("Answer 5", text)

	def test_recall_is_empty_without_history(self):
		with patch.object(api, "memory", return_value=None):
			self.assertEqual(api.recall("WC-1"), "")
