import json
from unittest.mock import MagicMock, patch

import frappe

from onechat.integrations import erpnext_commerce, payments
from onechat.tests.compat import IntegrationTestCase, UnitTestCase

REQUEST = "Payment Request"
INTEGRATION = "Integration Request"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
NUMBER = "919999900001"


def local():
	return MagicMock(remote=False)


def make_contact(**values):
	name = f"WC-T-{frappe.generate_hash(length=8)}"
	frappe.get_doc(
		{"doctype": CONTACT, "name": name, "contact_name": "Leo Daniel", "mobile_no": NUMBER, **values}
	).db_insert()
	return name


def make_link_message(contact, request):
	doc = frappe.get_doc(
		{
			"doctype": MESSAGE,
			"name": frappe.generate_hash(length=10),
			"type": "Outgoing",
			"whatsapp_contact": contact,
			"to": NUMBER,
			"message": "Here is your payment request",
			"content_type": "interactive",
			"message_type": "Manual",
			"message_id": f"wamid.{frappe.generate_hash(length=12)}",
			"buttons": json.dumps(
				{
					"type": "cta_url",
					"button": "Pay",
					"url": "https://example.com/razorpay_checkout?token=abc",
					"payment_request": request,
				}
			),
		}
	)
	doc.db_insert()
	return doc


def new_request():
	return f"ACC-PRQ-T-{frappe.generate_hash(length=8)}"


def paid_request(name, **values):
	return frappe._dict(
		{
			"doctype": REQUEST,
			"name": name,
			"status": "Paid",
			"party_type": "Customer",
			"party": "Leo Daniel A",
			"grand_total": 11,
			"currency": "INR",
			"reference_doctype": "Sales Order",
			"reference_name": "SAL-ORD-T-0001",
			**values,
		}
	)


class TestRequestNeeds(UnitTestCase):
	def test_listing_only_needs_message_create(self):
		self.assertEqual(payments.request_needs(None), [("OneChat Message", "create")])

	def test_whatsapp_pay_needs_payment_create(self):
		self.assertIn(("OneChat WhatsApp Payment", "create"), payments.request_needs({"method": "whatsapp"}))

	def test_payment_link_needs_payment_request_create(self):
		self.assertIn((REQUEST, "create"), payments.request_needs({"method": "link"}))


class TestLinkMessages(IntegrationTestCase):
	def test_finds_only_messages_for_the_request(self):
		contact = make_contact()
		first, second = new_request(), new_request()
		mine = make_link_message(contact, first)
		make_link_message(contact, second)

		self.assertEqual([row.name for row in payments.link_messages(first)], [mine.name])

	def test_message_id_comes_from_the_contacts_own_chat(self):
		request = new_request()
		leo, other = make_contact(), make_contact()
		make_link_message(other, request)
		mine = make_link_message(leo, request)

		self.assertEqual(payments.link_message_id(leo, request), mine.message_id)

	def test_no_message_id_without_request(self):
		self.assertIsNone(payments.link_message_id(make_contact(), None))


class TestReceipt(IntegrationTestCase):
	def run_receipt(self, settings, window, request=None):
		contact = make_contact()
		request = request or new_request()
		link = make_link_message(contact, request)
		with (
			patch.object(payments, "config", return_value=frappe._dict(settings)),
			patch.object(payments, "window", return_value=window),
			patch.object(payments.ERP, "is_remote", return_value=False),
			patch.object(payments, "send_text") as send_text,
			patch.object(payments, "send_template") as send_template,
		):
			result = payments.receipt(frappe.get_doc(CONTACT, contact), paid_request(request))
		return result, send_text, send_template, link

	def test_reply_quotes_the_payment_link_message(self):
		result, send_text, send_template, link = self.run_receipt({"payment_receipts": 1}, window=True)

		self.assertTrue(result)
		send_template.assert_not_called()
		args = send_text.call_args.args
		self.assertIn("✅ Paid", args[1])
		self.assertIn("SAL-ORD-T-0001", args[1])
		self.assertEqual(args[3], link.message_id)

	def test_template_is_used_when_window_is_closed(self):
		result, send_text, send_template, _link = self.run_receipt(
			{"payment_receipts": 1, "receipt_template": "receipt_tpl"}, window=False
		)

		self.assertTrue(result)
		send_text.assert_not_called()
		self.assertEqual(send_template.call_args.args[1], "receipt_tpl")

	def test_skipped_when_window_is_closed_and_no_template(self):
		result, send_text, send_template, _link = self.run_receipt({"payment_receipts": 1}, window=False)

		self.assertFalse(result)
		send_text.assert_not_called()
		send_template.assert_not_called()

	def test_skipped_when_receipts_are_off(self):
		result, send_text, _send_template, _link = self.run_receipt({"payment_receipts": 0}, window=True)

		self.assertFalse(result)
		send_text.assert_not_called()


class TestPaymentReceived(IntegrationTestCase):
	def receive(self, request):
		with (
			patch.object(erpnext_commerce.ERP, "is_remote", return_value=False),
			patch.object(payments, "receipt") as receipt,
		):
			erpnext_commerce.payment_received(request)
		return receipt

	def test_uses_the_chat_where_the_link_was_sent(self):
		contact = make_contact(reference_doctype="Customer", reference_docname="Leo Daniel A - 1")
		request = new_request()
		make_link_message(contact, request)

		receipt = self.receive(paid_request(request))

		self.assertEqual(receipt.call_args.args[0].name, contact)

	def test_falls_back_to_the_customers_chat(self):
		contact = make_contact(reference_doctype="Customer", reference_docname="Leo Daniel A")

		receipt = self.receive(paid_request(new_request()))

		self.assertEqual(receipt.call_args.args[0].name, contact)

	def test_ignores_payments_that_are_not_from_customers(self):
		receipt = self.receive(paid_request(new_request(), party_type="Supplier"))

		receipt.assert_not_called()

	def test_sends_only_one_receipt(self):
		contact = make_contact()
		request = new_request()
		make_link_message(contact, request)
		frappe.get_doc(
			{
				"doctype": MESSAGE,
				"name": frappe.generate_hash(length=10),
				"type": "Outgoing",
				"whatsapp_contact": contact,
				"to": NUMBER,
				"message": "✅ Paid",
				"content_type": "text",
				"message_type": "Manual",
				"reference_doctype": REQUEST,
				"reference_name": request,
			}
		).db_insert()

		receipt = self.receive(paid_request(request))

		receipt.assert_not_called()


class TestMarkRequestPaid(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_runs_as_administrator_and_restores_the_user(self):
		seen = []
		doc = MagicMock()
		doc.set_as_paid.side_effect = lambda: seen.append(frappe.session.user)
		frappe.set_user("Guest")

		erpnext_commerce.mark_request_paid(doc)

		self.assertEqual(seen, ["Administrator"])
		self.assertTrue(doc.flags.ignore_permissions)
		self.assertEqual(frappe.session.user, "Guest")

	def test_restores_the_user_when_payment_entry_fails(self):
		doc = MagicMock()
		doc.set_as_paid.side_effect = frappe.PermissionError(
			"User don't have permissions to select/read this account."
		)
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			erpnext_commerce.mark_request_paid(doc)

		self.assertEqual(frappe.session.user, "Guest")

	def test_settle_skips_requests_already_paid(self):
		with (
			patch.object(frappe.db, "get_value", return_value="Paid"),
			patch.object(erpnext_commerce, "mark_request_paid") as mark,
		):
			erpnext_commerce.settle(frappe._dict(name="ACC-PRQ-T-1"))

		mark.assert_not_called()

	def test_settle_logs_instead_of_failing(self):
		with (
			patch.object(frappe.db, "get_value", return_value="Requested"),
			patch.object(erpnext_commerce, "mark_request_paid", side_effect=frappe.PermissionError),
			patch.object(frappe, "log_error") as log_error,
		):
			erpnext_commerce.settle(frappe._dict(name="ACC-PRQ-T-1"))

		log_error.assert_called_once()


class TestPaymentUpdate(UnitTestCase):
	def update(self, doc, method, *args):
		with (
			patch.object(frappe, "get_installed_apps", return_value=["frappe", "erpnext"]),
			patch.object(erpnext_commerce, "settle") as settle,
			patch.object(erpnext_commerce, "request_paid") as request_paid,
			patch.object(payments, "request_changed") as request_changed,
		):
			erpnext_commerce.payment_update(doc, method, *args)
		return settle, request_paid, request_changed

	def test_authorized_payment_settles_and_runs_the_paid_flow(self):
		doc = MagicMock(status="Requested")

		settle, request_paid, request_changed = self.update(doc, "on_payment_authorized", "Authorized")

		settle.assert_called_once_with(doc)
		request_paid.assert_called_once_with(doc)
		request_changed.assert_called_once_with(doc)

	def test_failed_authorization_only_refreshes(self):
		settle, request_paid, request_changed = self.update(
			MagicMock(status="Requested"), "on_payment_authorized", "Failed"
		)

		settle.assert_not_called()
		request_paid.assert_not_called()
		request_changed.assert_called_once()

	def test_status_change_to_paid_runs_the_paid_flow(self):
		doc = MagicMock(status="Paid")
		doc.has_value_changed.return_value = True

		_settle, request_paid, _changed = self.update(doc, "on_update_after_submit")

		request_paid.assert_called_once_with(doc)

	def test_other_updates_do_not_run_the_paid_flow(self):
		doc = MagicMock(status="Paid")
		doc.has_value_changed.return_value = False

		_settle, request_paid, _changed = self.update(doc, "on_update_after_submit")

		request_paid.assert_not_called()


class TestEntrySubmitted(UnitTestCase):
	def test_entry_requests_are_unique_and_skip_blank_rows(self):
		doc = frappe._dict(
			references=[
				frappe._dict(payment_request="PR-1"),
				frappe._dict(payment_request=None),
				frappe._dict(payment_request="PR-1"),
				frappe._dict(payment_request="PR-2"),
			]
		)

		self.assertEqual(erpnext_commerce.entry_requests(doc), ["PR-1", "PR-2"])

	def submit(self, status):
		request = MagicMock(status=status)
		entry = frappe._dict(name="ACC-PAY-T-1", references=[frappe._dict(payment_request="PR-1")])
		with (
			patch.object(frappe, "get_installed_apps", return_value=["frappe", "erpnext"]),
			patch.object(frappe, "get_doc", return_value=request),
			patch.object(erpnext_commerce, "request_paid") as request_paid,
			patch.object(payments, "request_changed") as request_changed,
		):
			erpnext_commerce.entry_submitted(entry)
		return request, request_paid, request_changed

	def test_manual_entry_that_pays_the_request_sends_receipt_and_alert(self):
		request, request_paid, request_changed = self.submit("Paid")

		request_paid.assert_called_once_with(request)
		request_changed.assert_called_once_with(request)

	def test_partial_entry_only_refreshes_the_chat(self):
		_request, request_paid, request_changed = self.submit("Partially Paid")

		request_paid.assert_not_called()
		request_changed.assert_called_once()


class TestExpireCheckout(IntegrationTestCase):
	def make_integration(self, status, request=None):
		name = frappe.generate_hash(length=10)
		frappe.get_doc(
			{
				"doctype": INTEGRATION,
				"name": name,
				"status": status,
				"reference_doctype": REQUEST if request else None,
				"reference_docname": request,
				"integration_request_service": "Razorpay",
			}
		).db_insert()
		return name

	def status(self, name):
		return frappe.db.get_value(INTEGRATION, name, "status")

	def test_failed_link_closes_open_checkouts_only(self):
		request = new_request()
		open_checkout = self.make_integration("Queued", request)
		finished = self.make_integration("Completed", request)
		token = self.make_integration("Queued")

		with patch.object(payments.ERP, "source", return_value=local()):
			closed = payments.expire_checkout(request, f"https://example.com/razorpay_checkout?token={token}")

		self.assertEqual(closed, 2)
		self.assertEqual(self.status(open_checkout), "Cancelled")
		self.assertEqual(self.status(token), "Cancelled")
		self.assertEqual(self.status(finished), "Completed")

	def test_closing_twice_changes_nothing(self):
		request = new_request()
		self.make_integration("Queued", request)

		with patch.object(payments.ERP, "source", return_value=local()):
			payments.expire_checkout(request, "")
			self.assertEqual(payments.expire_checkout(request, ""), 0)

	def test_remote_erpnext_is_left_alone(self):
		request = new_request()
		checkout = self.make_integration("Queued", request)

		with patch.object(payments.ERP, "source", return_value=MagicMock(remote=True)):
			self.assertEqual(payments.expire_checkout(request, ""), 0)

		self.assertEqual(self.status(checkout), "Queued")


class TestRequestChanged(UnitTestCase):
	def change(self, **values):
		doc = frappe._dict(
			{"name": "PR-1", "status": "Requested", "docstatus": 1, "payment_url": "", **values}
		)
		with (
			patch.object(payments, "expire_checkout") as expire,
			patch.object(payments, "refresh_links") as refresh,
		):
			payments.request_changed(doc)
		return expire, refresh

	def test_failed_request_closes_its_checkout(self):
		expire, refresh = self.change(status="Failed")

		expire.assert_called_once()
		refresh.assert_called_once_with("PR-1")

	def test_cancelled_request_closes_its_checkout(self):
		expire, _refresh = self.change(docstatus=2, status="Cancelled")

		expire.assert_called_once()

	def test_paid_request_keeps_its_checkout(self):
		expire, refresh = self.change(status="Paid")

		expire.assert_not_called()
		refresh.assert_called_once()


class TestMarkLink(IntegrationTestCase):
	def mark(self, status, request_doc=None, admin=True):
		contact = make_contact()
		link = make_link_message(contact, new_request())
		request_doc = request_doc or MagicMock(docstatus=1, status="Requested")
		with (
			patch.object(payments, "check_visible"),
			patch.object(payments, "require_erp"),
			patch.object(payments, "require_admin", side_effect=None if admin else frappe.PermissionError),
			patch.object(payments.ERP, "source", return_value=local()),
			patch.object(frappe, "get_doc", return_value=request_doc),
			patch.object(payments, "expire_checkout") as expire,
			patch.object(payments, "refresh_links") as refresh,
			patch.object(erpnext_commerce, "mark_request_paid") as mark_paid,
		):
			payments.mark_link(link.name, status)
		return request_doc, expire, refresh, mark_paid

	def test_marking_failed_closes_the_checkout(self):
		request_doc, expire, refresh, mark_paid = self.mark("Failed")

		request_doc.db_set.assert_called_once_with("status", "Failed")
		expire.assert_called_once()
		refresh.assert_called_once()
		mark_paid.assert_not_called()

	def test_marking_paid_creates_the_payment_entry(self):
		request_doc, expire, _refresh, mark_paid = self.mark("Paid")

		mark_paid.assert_called_once_with(request_doc)
		expire.assert_not_called()

	def test_only_admins_can_mark_paid(self):
		with self.assertRaises(frappe.PermissionError):
			self.mark("Paid", admin=False)

	def test_paid_requests_cannot_be_marked_again(self):
		with self.assertRaises(payments.PaymentError):
			self.mark("Failed", request_doc=MagicMock(docstatus=1, status="Paid"))

	def test_unknown_status_is_refused(self):
		with self.assertRaises(payments.PaymentError):
			payments.mark_link("any", "Refunded")
