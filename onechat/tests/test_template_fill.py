from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import fmt_money

from onechat.inbox import template_fill

KNOWN = {
	key: {"key": key, "label": key, "value": key.upper(), "source": "test"}
	for key in ("first_name", "amount_due", "document", "date")
}


class Chat(frappe._dict):
	def as_dict(self):
		return dict(self)


class TestTemplateHelpers(UnitTestCase):
	def test_variable_count_uses_the_highest_index(self):
		self.assertEqual(template_fill.variable_count("Hi {{1}}, pay {{3}} for {{2}}"), 3)
		self.assertEqual(template_fill.variable_count("No variables"), 0)
		self.assertEqual(template_fill.variable_count(None), 0)

	def test_guesses_from_the_words_before_each_variable(self):
		text = "Hi {{1}}, your order {{2}} of ₹{{3}} is due on {{4}}. Thanks, {{5}}"

		guessed = [(template_fill.guess(text, index, KNOWN) or {}).get("value") for index in range(1, 6)]

		self.assertEqual(guessed, ["FIRST_NAME", "DOCUMENT", "AMOUNT_DUE", "DATE", None])

	def test_no_guess_without_a_matching_value(self):
		self.assertIsNone(template_fill.guess("Hi {{1}}", 1, {}))

	def test_money_fields_are_formatted_with_currency(self):
		record = {"grand_total": 1888.0, "currency": "INR"}

		self.assertEqual(template_fill.display(record, "grand_total"), fmt_money(1888.0, currency="INR"))

	def test_empty_values_display_blank(self):
		self.assertEqual(template_fill.display({"customer_name": None}, "customer_name"), "")


class TestFill(UnitTestCase):
	def fill(self, template, record):
		chat = Chat(name="WC-1", contact_name="Leo Daniel", mobile_no="919999900004")
		documents = [{"doctype": "Sales Order", "name": "SO-1", "label": "Sales Order SO-1", "hint": ""}]

		def fake_get_doc(doctype, name=None):
			return template if doctype == template_fill.TEMPLATE else chat

		with (
			patch.object(template_fill, "guard"),
			patch.object(template_fill, "check_visible"),
			patch.object(frappe, "get_doc", side_effect=fake_get_doc),
			patch.object(template_fill, "documents", return_value=documents),
			patch.object(template_fill, "load", return_value=record),
			patch.object(template_fill.links, "of", return_value=[]),
		):
			return template_fill.fill("WC-1", "tpl")

	def test_mapped_fields_fill_from_the_chosen_order(self):
		template = frappe._dict(
			template="Hi {{1}}, order {{2}} total {{3}}",
			for_doctype="Sales Order",
			field_names="customer_name,name,grand_total",
		)
		record = {
			"doctype": "Sales Order",
			"name": "SO-1",
			"customer_name": "Leo Daniel",
			"grand_total": 1888.0,
			"currency": "INR",
		}

		result = self.fill(template, record)

		self.assertEqual(
			[row["value"] for row in result["values"]],
			["Leo Daniel", "SO-1", fmt_money(1888.0, currency="INR")],
		)
		self.assertEqual(result["document"], {"doctype": "Sales Order", "name": "SO-1"})
		self.assertIn("Sales Order SO-1", result["values"][1]["source"])

	def test_unmapped_variables_are_guessed(self):
		template = frappe._dict(template="Hi {{1}}, your order {{2}}", for_doctype=None, field_names="")
		record = {"doctype": "Sales Order", "name": "SO-1", "grand_total": 1888.0, "currency": "INR"}

		result = self.fill(template, record)

		self.assertEqual([row["value"] for row in result["values"]], ["Leo", "SO-1"])
		self.assertIn("guessed", result["values"][0]["source"])

	def test_suggestions_include_contact_and_order_values(self):
		template = frappe._dict(template="{{1}}", for_doctype=None, field_names="")
		record = {
			"doctype": "Sales Order",
			"name": "SO-1",
			"grand_total": 1888.0,
			"currency": "INR",
			"advance_paid": 888.0,
		}

		keys = {row["key"] for row in self.fill(template, record)["suggestions"]}

		self.assertTrue({"first_name", "full_name", "mobile", "document", "total", "amount_due"} <= keys)
