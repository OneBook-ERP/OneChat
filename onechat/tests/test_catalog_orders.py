import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from onechat.insights import orders
from onechat.integrations import erpnext_commerce

ORDER = {
	"catalog_id": "cat-1",
	"product_items": [
		{"product_retailer_id": "CHAIR", "quantity": 2, "item_price": 1180, "currency": "INR"},
		{"product_retailer_id": "TABLE", "quantity": 1, "item_price": 500, "currency": "INR"},
		{"product_retailer_id": "GHOST", "quantity": 1, "item_price": 10, "currency": "INR"},
	],
}


def order_message(**values):
	return frappe._dict(
		{
			"name": "MSG-1",
			"message_id": "wamid.order-1",
			"whatsapp_contact": "WC-1",
			"whatsapp_account": "Test Account",
			"from": "919999900003",
			"products": json.dumps(ORDER),
			**values,
		}
	)


class TestCreateSalesOrder(UnitTestCase):
	def create(self, message, source=None, known=None):
		saved = MagicMock()
		saved.name = "SAL-ORD-T-0001"
		captured = {}

		def fake_get_doc(*args, **kwargs):
			if args and isinstance(args[0], dict):
				captured.update(args[0])
				return saved
			return frappe._dict(name=args[1] if len(args) > 1 else None)

		source = source or MagicMock(remote=False)
		source.exists.return_value = True
		with (
			patch.object(erpnext_commerce.ERP, "source", return_value=source),
			patch.object(
				erpnext_commerce,
				"item_names",
				return_value=known if known is not None else {"CHAIR": "Chair", "TABLE": "Table"},
			),
			patch.object(erpnext_commerce, "customer_for", return_value="Leo Daniel A"),
			patch.object(erpnext_commerce, "gst_rates", return_value={"CHAIR": 18}),
			patch.object(erpnext_commerce, "price_list_for", return_value="Standard Selling"),
			patch.object(erpnext_commerce, "company", return_value="OneBook"),
			patch.object(frappe, "get_doc", side_effect=fake_get_doc),
		):
			name = erpnext_commerce.create_sales_order(message)
		return name, captured, saved

	def test_order_becomes_a_sales_order_for_the_customer(self):
		name, values, saved = self.create(order_message())

		self.assertEqual(name, "SAL-ORD-T-0001")
		self.assertEqual(values["customer"], "Leo Daniel A")
		self.assertEqual(values["company"], "OneBook")
		self.assertEqual(values["po_no"], "wamid.order-1")
		self.assertEqual(values["selling_price_list"], "Standard Selling")
		self.assertEqual(values["currency"], "INR")
		saved.insert.assert_called_once_with(ignore_permissions=True)

	def test_unknown_items_are_left_out(self):
		_name, values, _saved = self.create(order_message())

		self.assertEqual([item["item_code"] for item in values["items"]], ["CHAIR", "TABLE"])

	def test_gst_is_taken_off_the_whatsapp_price(self):
		_name, values, _saved = self.create(order_message())
		rates = {item["item_code"]: (item["qty"], item["rate"]) for item in values["items"]}

		self.assertEqual(rates["CHAIR"], (2, 1000))
		self.assertEqual(rates["TABLE"], (1, 500))

	def test_order_with_no_known_items_is_skipped(self):
		name, values, saved = self.create(order_message(), known={})

		self.assertIsNone(name)
		self.assertEqual(values, {})
		saved.insert.assert_not_called()

	def test_remote_erpnext_gets_the_order_over_the_api(self):
		source = MagicMock(remote=True)
		source.insert.return_value = frappe._dict(name="SAL-ORD-R-0001")

		name, _values, _saved = self.create(order_message(), source=source)

		self.assertEqual(name, "SAL-ORD-R-0001")
		self.assertEqual(source.insert.call_args.args[0]["po_no"], "wamid.order-1")


class TestOrderHelpers(UnitTestCase):
	def test_lines_ignore_bad_json_and_blank_items(self):
		self.assertEqual(orders.lines_of("not json"), [])
		self.assertEqual(
			len(
				orders.lines_of(
					json.dumps({"product_items": [{"product_retailer_id": ""}, {"product_retailer_id": "A"}]})
				)
			),
			1,
		)

	def test_line_value_uses_quantity(self):
		self.assertEqual(orders.line_value({"item_price": 250, "quantity": 3}), 750)
		self.assertEqual(orders.line_value({"item_price": 250}), 250)

	def test_payment_state(self):
		cases = [
			({"docstatus": 0, "grand_total": 100}, 0, "Draft"),
			({"docstatus": 2, "grand_total": 100}, 0, "Cancelled"),
			({"docstatus": 1, "grand_total": 100}, 100, "Paid"),
			({"docstatus": 1, "grand_total": 100}, 40, "Part paid"),
			({"docstatus": 1, "grand_total": 100}, 0, "Unpaid"),
		]
		for order, paid, expected in cases:
			self.assertEqual(orders.payment_state(order, paid), expected)


class TestOrdersReport(IntegrationTestCase):
	def report(self, messages, linked):
		span = frappe._dict(since=datetime(2026, 10, 1), until=datetime(2026, 10, 2, 23, 0), hourly=False)
		with (
			patch.object(orders, "whatsapp_orders", return_value=messages),
			patch.object(orders, "sales_orders", return_value=linked),
			patch.object(erpnext_commerce, "enabled", return_value=True),
			patch.object(erpnext_commerce.ERP, "ready", return_value=True),
			patch.object(erpnext_commerce.ERP, "source", return_value=MagicMock(remote=True)),
			patch.object(erpnext_commerce, "item_names", return_value={"CHAIR": "Chair", "TABLE": "Table"}),
		):
			return orders.report(span)

	def test_counts_orders_sales_orders_and_payments(self):
		messages = [
			order_message(
				name="M-1", message_id="wamid.1", whatsapp_contact=None, creation=datetime(2026, 10, 1, 10)
			),
			order_message(
				name="M-2", message_id="wamid.2", whatsapp_contact=None, creation=datetime(2026, 10, 2, 11)
			),
		]
		linked = {
			"wamid.1": {
				"name": "SO-1",
				"docstatus": 1,
				"grand_total": 2500,
				"advance_paid": 2500,
				"per_billed": 0,
				"currency": "INR",
				"status": "To Deliver and Bill",
			},
		}

		result = self.report(messages, linked)

		self.assertEqual(result["summary"]["orders"], 2)
		self.assertEqual(result["summary"]["sales_orders"], 1)
		self.assertEqual(result["summary"]["paid"], 1)
		self.assertEqual([row["count"] for row in result["funnel"]], [2, 1, 1, 1])
		self.assertEqual({row["state"] for row in result["recent"]}, {"Paid", "No order"})

	def test_products_are_ranked_by_value(self):
		messages = [
			order_message(
				name="M-1", message_id="wamid.1", whatsapp_contact=None, creation=datetime(2026, 10, 1, 10)
			)
		]

		result = self.report(messages, {})

		self.assertEqual([row["code"] for row in result["products"]][:2], ["CHAIR", "TABLE"])
		self.assertEqual(result["products"][0]["name"], "Chair")
		self.assertEqual(result["products"][0]["qty"], 2)

	def test_empty_period(self):
		result = self.report([], {})

		self.assertEqual(result["summary"]["orders"], 0)
		self.assertIsNone(result["summary"]["conversion"])
		self.assertEqual(result["products"], [])
