from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_to_date, now_datetime

from onechat.whatsapp import pay

PAYMENT = "OneChat WhatsApp Payment"


def row(**values):
	return frappe._dict(
		{"name": "PAY-1", "status": "Pending", "amount": 1000, "refunded_amount": 0, **values}
	)


class TestSucceeded(UnitTestCase):
	def test_captured_payment_succeeds(self):
		self.assertTrue(pay.succeeded({"status": "captured"})[0])

	def test_successful_transaction_succeeds(self):
		paid, transaction = pay.succeeded(
			{"transactions": [{"id": "t1", "status": "failed"}, {"id": "t2", "status": "success"}]}
		)

		self.assertTrue(paid)
		self.assertEqual(transaction["id"], "t2")

	def test_failed_transaction_does_not_succeed(self):
		paid, transaction = pay.succeeded({"transaction": {"id": "t1", "status": "failed"}})

		self.assertFalse(paid)
		self.assertEqual(transaction["id"], "t1")


class TestApply(UnitTestCase):
	def apply(self, payment, info):
		with patch.object(pay, "keep"), patch.object(pay, "paid_now") as paid_now:
			pay.apply(payment, info)
		return paid_now

	def test_captured_payment_is_marked_paid_once(self):
		payment = row()

		paid_now = self.apply(
			payment, {"status": "captured", "transaction": {"id": "t1", "method": {"type": "upi"}}}
		)

		self.assertEqual(payment.status, "Paid")
		self.assertEqual(payment.method, "upi")
		paid_now.assert_called_once_with(payment)

	def test_already_paid_payment_is_not_settled_again(self):
		paid_now = self.apply(row(status="Paid"), {"status": "captured"})

		paid_now.assert_not_called()

	def test_failed_attempt_stores_the_reason(self):
		payment = row()

		self.apply(payment, {"transaction": {"status": "failed", "error": {"reason": "Bank declined"}}})

		self.assertEqual(payment.status, "Failed")
		self.assertEqual(payment.error, "Bank declined")

	def test_refunds_update_the_status(self):
		payment = row(status="Paid")

		self.apply(
			payment, {"status": "captured", "refunds": [{"status": "completed", "amount": {"value": 40000}}]}
		)

		self.assertEqual(payment.refunded_amount, 400)
		self.assertEqual(payment.status, "Partly Refunded")


class TestRetryPending(IntegrationTestCase):
	def make_payment(self, status="Pending", provider="razorpay", hours_ago=1):
		name = f"OC-T-{frappe.generate_hash(length=8)}"
		frappe.get_doc(
			{
				"doctype": PAYMENT,
				"name": name,
				"reference_id": name,
				"status": status,
				"provider": provider,
				"amount": 1000,
				"creation": add_to_date(now_datetime(), hours=-hours_ago),
				"modified": add_to_date(now_datetime(), hours=-hours_ago),
			}
		).db_insert()
		return name

	def retry(self, lookup=None, apply=None):
		checked = []

		def fake_lookup(payment):
			checked.append(payment.name)
			return lookup(payment) if lookup else {"status": "captured"}

		def fake_apply(payment, info):
			payment.status = "Paid"
			return payment

		with (
			patch.object(pay, "lookup", side_effect=fake_lookup),
			patch.object(pay, "apply", side_effect=apply or fake_apply),
			patch.object(pay, "announce") as announce,
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback") as rollback,
			patch.object(frappe, "log_error") as log_error,
		):
			pay.retry_pending()
		return checked, announce, rollback, log_error

	def test_recent_open_orders_are_checked_again(self):
		pending = self.make_payment()
		failed = self.make_payment(status="Failed")
		old = self.make_payment(hours_ago=30)
		upi = self.make_payment(provider="upi_vpa")
		paid = self.make_payment(status="Paid")

		checked, announce, _rollback, _log_error = self.retry()

		self.assertIn(pending, checked)
		self.assertIn(failed, checked)
		for skipped in (old, upi, paid):
			self.assertNotIn(skipped, checked)
		self.assertGreaterEqual(announce.call_count, 2)

	def test_unchanged_orders_are_not_announced(self):
		self.make_payment()

		_checked, announce, _rollback, _log_error = self.retry(apply=lambda payment, info: payment)

		announce.assert_not_called()

	def test_meta_with_no_answer_is_skipped(self):
		self.make_payment()

		_checked, announce, _rollback, _log_error = self.retry(lookup=lambda payment: {})

		announce.assert_not_called()

	def test_one_failure_does_not_stop_the_others(self):
		self.make_payment()
		self.make_payment()

		def flaky(payment):
			raise pay.PayError("Meta is down")

		checked, _announce, rollback, log_error = self.retry(lookup=flaky)

		self.assertGreaterEqual(len(checked), 2)
		self.assertTrue(rollback.called)
		self.assertTrue(log_error.called)
