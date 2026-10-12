import json
import re

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, cint, flt, fmt_money, get_url, now_datetime, nowdate

from onechat.inbox.conversations import CONTACT, MESSAGE, guard, publish
from onechat.inbox.visibility import check as check_visible
from onechat.integrations.erpnext_commerce import ERP, account_for, company, enabled
from onechat.whatsapp.accounts import admin_only, token
from onechat.workspace.session import is_admin, require

ACCOUNT = "OneChat Account"
PAYMENT = "OneChat WhatsApp Payment"
PAYABLE = ("Sales Invoice", "Sales Order")
PROVIDERS = ("razorpay", "payu", "zaakpay", "upi_vpa")
OFFSET = 100
TIMEOUT = 60
OPTIONS_CACHE = "onechat:pay:options"
RETRY_HOURS = 24
RETRY_LIMIT = 200
FLOW = {
	"pending": ("processing", "canceled"),
	"processing": ("partially_shipped", "shipped", "completed", "canceled"),
	"partially_shipped": ("shipped", "completed", "canceled"),
	"shipped": ("completed",),
	"completed": (),
	"canceled": (),
}
STATUS_TEXT = {
	"processing": "We are preparing your order {0}.",
	"partially_shipped": "Part of your order {0} is on its way.",
	"shipped": "Your order {0} is on its way.",
	"completed": "Your order {0} is complete. Thank you!",
	"canceled": "Your order {0} has been canceled.",
}
STATES = {
	"andaman and nicobar islands": "AN",
	"andhra pradesh": "AP",
	"arunachal pradesh": "AR",
	"assam": "AS",
	"bihar": "BR",
	"chandigarh": "CH",
	"chhattisgarh": "CT",
	"dadra and nagar haveli and daman and diu": "DH",
	"delhi": "DL",
	"goa": "GA",
	"gujarat": "GJ",
	"haryana": "HR",
	"himachal pradesh": "HP",
	"jammu and kashmir": "JK",
	"jharkhand": "JH",
	"karnataka": "KA",
	"kerala": "KL",
	"ladakh": "LA",
	"lakshadweep": "LD",
	"madhya pradesh": "MP",
	"maharashtra": "MH",
	"manipur": "MN",
	"meghalaya": "ML",
	"mizoram": "MZ",
	"nagaland": "NL",
	"odisha": "OR",
	"puducherry": "PY",
	"punjab": "PB",
	"rajasthan": "RJ",
	"sikkim": "SK",
	"tamil nadu": "TN",
	"telangana": "TG",
	"tripura": "TR",
	"uttar pradesh": "UP",
	"uttarakhand": "UT",
	"west bengal": "WB",
}


class PayError(frappe.ValidationError):
	def __init__(self, message=None, code=None):
		super().__init__(message)
		self.code = code


def graph(account, method, path, params=None, data=None, payload=None, quiet=False):
	response = requests.request(
		method,
		f"{account.url}/{account.version}/{path}",
		params=params,
		data=data,
		json=payload,
		headers={"Authorization": f"Bearer {token(account)}"},
		timeout=TIMEOUT,
	)
	try:
		body = response.json()
	except ValueError:
		body = {}
	if not response.ok:
		error = body.get("error") or {}
		message = error.get("error_user_msg") or error.get("message") or response.text[:300]
		if error.get("code") == 1:
			message = _(
				"{0}. Meta gives this when WhatsApp payments aren't enabled for this WhatsApp Business Account yet. Check WhatsApp Manager → Account tools → Payment configurations."
			).format(message.rstrip("."))
		if quiet:
			raise PayError(message, error.get("code"))
		frappe.throw(message, PayError, title=_("Meta"))
	return body


def keep(row):
	row.flags.ignore_links = ERP.is_remote()
	row.save(ignore_permissions=True)


def paise(value):
	return round(flt(value) * OFFSET)


def money(value, currency="INR"):
	return fmt_money(value, currency=currency)


def admin_account(name):
	admin_only()
	doc = frappe.get_doc(ACCOUNT, name)
	if not doc.business_id or not token(doc):
		frappe.throw(_("Add the WhatsApp Business Account ID and access token to this number first."))
	return doc


def config_row(row):
	return {
		"name": row.get("configuration_name"),
		"provider": row.get("provider_name"),
		"status": row.get("status"),
		"vpa": row.get("merchant_vpa"),
		"mcc": (row.get("merchant_category_code") or {}).get("code"),
		"purpose": (row.get("purpose_code") or {}).get("code"),
	}


def fetch_configurations(doc, quiet=False):
	rows = graph(doc, "GET", f"{doc.business_id}/payment_configurations", quiet=quiet).get("data") or []
	if rows and "payment_configurations" in rows[0]:
		rows = rows[0].get("payment_configurations") or []
	return [config_row(row) for row in rows if row.get("configuration_name")]


def overview(doc, quiet=False):
	rows = fetch_configurations(doc, quiet)
	selected = doc.get("pay_configuration")
	match = next((row for row in rows if row["name"] == selected), None)
	if match and match["provider"] != doc.get("pay_provider"):
		frappe.db.set_value(ACCOUNT, doc.name, "pay_provider", match["provider"])
	return {
		"configurations": rows,
		"selected": selected or "",
		"active": bool(match and match["status"] == "Active"),
	}


def unavailable(error):
	if error.code == 190:
		kind = "token"
	elif error.code in (10, 200, 3) or "permission" in str(error).lower():
		kind = "permission"
	else:
		kind = "not_enabled"
	return {"kind": kind, "detail": str(error)}


@frappe.whitelist()
def configurations(account: str):
	doc = admin_account(account)
	try:
		return {**overview(doc, quiet=True), "unavailable": None}
	except PayError as error:
		return {
			"configurations": [],
			"selected": doc.get("pay_configuration") or "",
			"active": False,
			"unavailable": unavailable(error),
		}


def redirect():
	return get_url("/onechat/inbox")


@frappe.whitelist(methods=["POST"])
def create_configuration(
	account: str,
	name: str,
	provider: str,
	vpa: str | None = None,
	mcc: str | int | None = None,
	purpose_code: str | None = None,
):
	doc = admin_account(account)
	name = (name or "").strip()
	if not re.fullmatch(r"[A-Za-z0-9_-]{3,60}", name):
		frappe.throw(_("Use 3 to 60 letters, digits, dashes or underscores for the name."))
	if provider not in PROVIDERS:
		frappe.throw(_("Pick a payment provider."))
	data = {"configuration_name": name, "provider_name": provider, "redirect_url": redirect()}
	if provider == "upi_vpa":
		if not (vpa or "").strip():
			frappe.throw(_("Enter the UPI ID payments go to, for example shop@okhdfc."))
		data["merchant_vpa"] = vpa.strip()
		data.pop("redirect_url")
	if (mcc or "").strip():
		data["merchant_category_code"] = mcc.strip()
	if (purpose_code or "").strip():
		data["purpose_code"] = purpose_code.strip()
	result = graph(doc, "POST", f"{doc.business_id}/payment_configuration", payload=data)
	if not doc.get("pay_configuration"):
		frappe.db.set_value(ACCOUNT, doc.name, {"pay_configuration": name, "pay_provider": provider})
		doc.reload()
	return {**overview(doc), "oauth_url": result.get("oauth_url")}


@frappe.whitelist(methods=["POST"])
def connect_link(account: str, name: str):
	doc = admin_account(account)
	result = graph(
		doc,
		"POST",
		f"{doc.business_id}/generate_payment_configuration_oauth_link",
		payload={"configuration_name": name, "redirect_url": redirect()},
	)
	if not result.get("oauth_url"):
		frappe.throw(_("Meta did not return a sign-in link. Try again in a minute."))
	return result["oauth_url"]


@frappe.whitelist(methods=["POST"])
def remove_configuration(account: str, name: str):
	doc = admin_account(account)
	graph(doc, "DELETE", f"{doc.business_id}/payment_configuration", payload={"configuration_name": name})
	if doc.get("pay_configuration") == name:
		frappe.db.set_value(ACCOUNT, doc.name, {"pay_configuration": None, "pay_provider": None})
		doc.reload()
	return overview(doc)


@frappe.whitelist(methods=["POST"])
def use_configuration(account: str, name: str):
	doc = admin_account(account)
	match = next((row for row in fetch_configurations(doc) if row["name"] == name), None)
	if not match:
		frappe.throw(_("Meta has no payment configuration called {0}.").format(name))
	frappe.db.set_value(ACCOUNT, doc.name, {"pay_configuration": name, "pay_provider": match["provider"]})
	doc.reload()
	return overview(doc)


@frappe.whitelist()
def erp_options():
	admin_only()
	cached = frappe.cache().get_value(OPTIONS_CACHE)
	if cached:
		return cached
	source = ERP.source()
	result = {
		"accounts": [
			row.get("name")
			for row in source.get_all(
				"Account",
				filters={
					"account_type": ["in", ["Bank", "Cash"]],
					"is_group": 0,
					"disabled": 0,
					"company": company(),
				},
				fields=["name"],
				order_by="name asc",
			)
		],
		"modes": [
			row.get("name")
			for row in source.get_all(
				"Mode of Payment", filters={"enabled": 1}, fields=["name"], order_by="name asc"
			)
		],
	}
	frappe.cache().set_value(OPTIONS_CACHE, result, expires_in_sec=600)
	return result


def on_configuration_update(value, entry_id=None):
	frappe.publish_realtime(
		"onechat_pay_configuration",
		{"business_id": entry_id, "value": value},
		room="doctype:OneChat Contact",
	)


def settings_of(account):
	if not account or not frappe.get_meta(ACCOUNT).has_field("pay_configuration"):
		return None
	row = frappe.db.get_value(
		ACCOUNT,
		account,
		[
			"name",
			"pay_configuration",
			"pay_provider",
			"pay_goods_type",
			"pay_auto_entry",
			"pay_deposit_account",
			"pay_mode_of_payment",
		],
		as_dict=True,
	)
	return row if row and row.pay_configuration else None


def available(contact):
	return bool(enabled() and settings_of(account_for(contact)))


def window(contact):
	from onechat.inbox.service import window_open

	return window_open(contact)


def reference_for(name):
	stem = re.sub(r"[^A-Za-z0-9_.-]", "-", name)[:27]
	return f"{stem}-{frappe.generate_hash(length=7)}"


def company_address():
	rows = ERP.source().get_all(
		"Address",
		filters={"is_your_company_address": 1, "disabled": 0},
		fields=["address_line1", "address_line2", "city", "state", "pincode"],
		limit=1,
	)
	if not rows:
		raise PayError(
			_(
				"Add your company address in ERPNext and tick Your Company Address. WhatsApp shows it on the order."
			)
		)
	row = rows[0]
	address = {
		"address_line1": (row.get("address_line1") or "")[:100],
		"city": row.get("city") or "",
		"zone_code": STATES.get((row.get("state") or "").strip().lower(), ""),
		"postal_code": row.get("pincode") or "",
		"country_code": "IN",
	}
	if row.get("address_line2"):
		address["address_line2"] = row["address_line2"][:100]
	return address


def origins(codes):
	if not codes:
		return {}
	rows = ERP.source().get_all("Item", filters={"name": ["in", codes]}, fields=["name", "country_of_origin"])
	return {row.get("name"): row.get("country_of_origin") for row in rows}


def line(name, value, quantity, physical, importer, origin=None):
	row = {"name": name[:60], "amount": {"value": value, "offset": OFFSET}, "quantity": quantity}
	if physical:
		row.update(
			{
				"country_of_origin": origin or "India",
				"importer_name": importer["name"],
				"importer_address": importer["address"],
			}
		)
	return row


def order_lines(doc, due, physical, importer):
	due_paise = paise(due)
	items = doc.get("items") or []
	whole = items and all(
		flt(row.get("qty")) == int(flt(row.get("qty"))) and flt(row.get("qty")) > 0 for row in items
	)
	if whole:
		countries = (
			origins([row.get("item_code") for row in items if row.get("item_code")]) if physical else {}
		)
		rows = [
			line(
				row.get("item_name") or row.get("item_code"),
				paise(row.get("rate")),
				int(flt(row.get("qty"))),
				physical,
				importer,
				countries.get(row.get("item_code")),
			)
			for row in items
		]
		subtotal = sum(row["amount"]["value"] * row["quantity"] for row in rows)
		tax = paise(doc.get("total_taxes_and_charges"))
		discount = paise(doc.get("discount_amount"))
		if subtotal + tax - discount == due_paise:
			order = {"items": rows, "subtotal": {"value": subtotal, "offset": OFFSET}}
			if tax:
				order["tax"] = {"value": tax, "offset": OFFSET, "description": _("GST")}
			if discount:
				order["discount"] = {"value": discount, "offset": OFFSET}
			return order
	title = " ".join([_(doc.get("doctype")), doc.get("name")])
	return {
		"items": [line(title, due_paise, 1, physical, importer)],
		"subtotal": {"value": due_paise, "offset": OFFSET},
	}


def payment_settings(settings, reference_id, name):
	if settings.pay_provider == "upi_vpa":
		return {"payment_type": "upi", "payment_configuration": settings.pay_configuration}
	gateway = {"type": settings.pay_provider, "configuration_name": settings.pay_configuration}
	if settings.pay_provider == "razorpay":
		gateway["razorpay"] = {"receipt": reference_id, "notes": {"reference": name}}
	elif settings.pay_provider == "payu":
		gateway["payu"] = {"udf1": name}
	elif settings.pay_provider == "zaakpay":
		gateway["zaakpay"] = {"udf1": name}
	return {"payment_settings": [{"type": "payment_gateway", "payment_gateway": gateway}]}


def interactive_body(settings, doc, due, reference_id, text):
	physical = (settings.pay_goods_type or "physical-goods") == "physical-goods"
	importer = {"name": (company() or "")[:60], "address": company_address()} if physical else None
	order = {"status": "pending", **order_lines(doc, due, physical, importer)}
	parameters = {
		"reference_id": reference_id,
		"type": "physical-goods" if physical else "digital-goods",
		"currency": "INR",
		"total_amount": {"value": paise(due), "offset": OFFSET},
		"order": order,
		**payment_settings(settings, reference_id, doc.get("name")),
	}
	body = {
		"type": "order_details",
		"body": {"text": text[:1024]},
		"action": {"name": "review_and_pay", "parameters": parameters},
	}
	footer = (company() or "")[:60]
	if footer:
		body["footer"] = {"text": footer}
	return body


def send_interactive(contact, account, content_type, text, interactive):
	return frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Manual",
			"to": contact.mobile_no,
			"message": text,
			"content_type": content_type,
			"source": "Agent",
			"products": json.dumps(interactive),
			"whatsapp_account": account,
			"reference_doctype": CONTACT,
			"reference_name": contact.name,
		}
	).insert(ignore_permissions=True)


def send_order(contact, payload):
	payload = frappe._dict(payload or {})
	doctype, name = payload.get("doctype"), payload.get("name")
	if doctype not in PAYABLE or not name:
		raise PayError(_("Pick an invoice or an order."))
	account = account_for(contact)
	settings = settings_of(account)
	if not settings:
		raise PayError(_("Set up WhatsApp payments on this number first (Settings → WhatsApp → Payments)."))
	if not window(contact.name):
		raise PayError(_("The customer hasn't written in the last 24 hours. Send a payment link instead."))

	from onechat.integrations.payments import cancel_requests, customers_of, due_of

	doc = ERP.source().get_doc(doctype, name)
	customers = customers_of(contact)
	if customers and doc.get("customer") not in customers:
		raise PayError(_("{0} belongs to a customer that isn't linked to this chat.").format(name))
	if cint(doc.get("docstatus")) != 1:
		raise PayError(_("{0} must be submitted before asking for payment.").format(name))
	if (doc.get("currency") or "INR") != "INR":
		raise PayError(_("WhatsApp payments only support INR. Send a payment link instead."))
	due = due_of(doctype, doc)
	amount = flt(payload.get("amount")) or due
	if due <= 0:
		raise PayError(_("Nothing is due on {0}.").format(name))
	if amount <= 0 or amount - due > 0.01:
		raise PayError(_("Enter an amount between 1 and {0}.").format(money(due)))
	if amount >= 500000 and settings.pay_provider == "upi_vpa":
		raise PayError(_("UPI payments are limited to ₹5,00,000. Use a payment gateway or split the amount."))

	cancel_requests(doctype, name)
	cancel_open(doctype, name)
	reference_id = reference_for(name)
	first = (contact.get("contact_name") or "").split(" ")[0] or _("there")
	text = (payload.get("message") or "").strip() or _("Hi {0}, please review and pay {1} for {2}.").format(
		first, money(amount), name
	)
	message = send_interactive(
		contact, account, "order_details", text, interactive_body(settings, doc, amount, reference_id, text)
	)
	record = frappe.get_doc(
		{
			"doctype": PAYMENT,
			"reference_id": reference_id,
			"status": "Pending",
			"order_status": "pending",
			"amount": amount,
			"currency": "INR",
			"contact": contact.name,
			"whatsapp_account": account,
			"whatsapp_message": message.name,
			"reference_doctype": doctype,
			"reference_name": name,
			"configuration": settings.pay_configuration,
			"provider": settings.pay_provider,
		}
	)
	record.flags.ignore_links = ERP.is_remote()
	record.insert(ignore_permissions=True)
	publish(contact.name, message.name)
	return _("Payment request for {0} sent").format(money(amount))


def summary(row):
	return {
		"name": row.name,
		"status": row.status,
		"order_status": row.order_status,
		"amount": flt(row.amount),
		"amount_label": money(row.amount, row.currency or "INR"),
		"refunded": flt(row.refunded_amount),
		"method": row.method,
		"provider": row.provider,
		"reference_doctype": row.reference_doctype,
		"reference_name": row.reference_name,
		"payment_entry": row.payment_entry,
		"error": row.error,
		"next": list(FLOW.get(row.order_status or "pending", ())),
	}


def for_messages(names):
	if not names or not frappe.db.table_exists(PAYMENT):
		return {}
	rows = frappe.get_all(
		PAYMENT,
		filters={"whatsapp_message": ["in", names]},
		fields=[
			"name",
			"whatsapp_message",
			"status",
			"order_status",
			"amount",
			"currency",
			"refunded_amount",
			"method",
			"provider",
			"reference_doctype",
			"reference_name",
			"payment_entry",
			"error",
		],
	)
	return {row.whatsapp_message: summary(row) for row in rows}


def load(name):
	guard()
	row = frappe.get_doc(PAYMENT, name)
	check_visible(row.contact)
	return row


def announce(row):
	if row.contact and row.whatsapp_message:
		publish(row.contact, row.whatsapp_message)


def lookup(row):
	account = frappe.get_doc(ACCOUNT, row.whatsapp_account)
	result = graph(account, "GET", f"{account.phone_id}/payments/{row.configuration}/{row.reference_id}")
	payments = result.get("payments") or []
	return payments[0] if payments else {}


def succeeded(info):
	transactions = info.get("transactions") or ([info["transaction"]] if info.get("transaction") else [])
	good = next((tx for tx in transactions if tx.get("status") == "success"), None)
	return info.get("status") == "captured" or bool(good), good or (transactions[-1] if transactions else {})


def apply(row, info):
	paid, transaction = succeeded(info)
	if transaction:
		row.transaction_id = transaction.get("id") or row.transaction_id
		row.pg_transaction_id = transaction.get("pg_transaction_id") or row.pg_transaction_id
		row.method = (transaction.get("method") or {}).get("type") or row.method
	refunds = info.get("refunds") or []
	refunded = sum(
		flt((refund.get("amount") or {}).get("value")) / OFFSET
		for refund in refunds
		if refund.get("status") != "failed"
	)
	if refunded:
		row.refunded_amount = refunded
	fresh = False
	if paid and row.status in ("Pending", "Failed"):
		row.status = "Paid"
		row.paid_at = now_datetime()
		row.error = None
		fresh = True
	elif not paid and transaction.get("status") == "failed" and row.status == "Pending":
		row.status = "Failed"
		row.error = (transaction.get("error") or {}).get("reason") or _("The payment attempt failed.")
	if refunded and row.status in ("Paid", "Partly Refunded", "Refunded"):
		row.status = "Refunded" if refunded >= flt(row.amount) - 0.01 else "Partly Refunded"
	keep(row)
	if fresh:
		paid_now(row)
	return row


def on_status(status):
	payment = status.get("payment") or {}
	name = payment.get("reference_id")
	if not name or not frappe.db.exists(PAYMENT, name):
		return
	row = frappe.get_doc(PAYMENT, name)
	info = {"status": status.get("status"), "transaction": payment.get("transaction") or {}}
	if succeeded(info)[0]:
		try:
			confirmed = lookup(row)
			if confirmed:
				info = confirmed
		except Exception:
			frappe.log_error(title="OneChat WhatsApp payment lookup")
			return
	apply(row, info)
	announce(row)


def paid_now(row):
	try:
		from onechat.workspace.notifications import payment_alert

		payment_alert(
			row.name,
			row.contact,
			money(row.amount, row.currency or "INR"),
			row.reference_name or row.name,
			[row.owner],
		)
	except Exception:
		frappe.log_error(title="OneChat WhatsApp payment alert")
	try:
		entry(row)
	except Exception as error:
		frappe.db.set_value(
			PAYMENT,
			row.name,
			"error",
			_("Paid, but the Payment Entry was not created: {0}").format(str(error)),
		)
		frappe.log_error(title="OneChat WhatsApp payment entry")
	try:
		from onechat.integrations.payments import cancel_requests

		cancel_requests(row.reference_doctype, row.reference_name)
		cancel_open(row.reference_doctype, row.reference_name, keep=row.name)
	except Exception:
		frappe.log_error(title="OneChat payment clean-up")
	contact = frappe.get_doc(CONTACT, row.contact)
	if window(contact.name):
		try:
			status_message(
				row, contact, "processing", _("Payment of {0} received. Thank you!").format(money(row.amount))
			)
			frappe.db.set_value(PAYMENT, row.name, "order_status", "processing")
		except Exception:
			frappe.log_error(title="OneChat WhatsApp order status")


def clean(value):
	if isinstance(value, dict):
		return {
			key: clean(item)
			for key, item in value.items()
			if key not in ("name", "__islocal", "__unsaved", "owner", "creation", "modified", "modified_by")
		}
	if isinstance(value, list):
		return [clean(item) for item in value]
	return value


def entry(row):
	settings = (
		frappe.db.get_value(
			ACCOUNT,
			row.whatsapp_account,
			["pay_auto_entry", "pay_deposit_account", "pay_mode_of_payment"],
			as_dict=True,
		)
		or {}
	)
	if row.payment_entry or not cint(settings.get("pay_auto_entry")) or not enabled():
		return
	source = ERP.source()
	reference = row.pg_transaction_id or row.transaction_id or row.reference_id
	values = {
		"reference_no": reference,
		"reference_date": nowdate(),
		"remarks": _("WhatsApp payment {0} ({1})").format(row.reference_id, row.method or row.provider or ""),
	}
	if settings.get("pay_mode_of_payment"):
		values["mode_of_payment"] = settings["pay_mode_of_payment"]
	method = "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry"
	if source.remote:
		draft = source.call(
			method,
			dt=row.reference_doctype,
			dn=row.reference_name,
			party_amount=flt(row.amount),
			bank_account=settings.get("pay_deposit_account") or None,
		)
		draft = {**clean(draft), **values, "docstatus": 0}
		saved = source.submit(source.insert(draft))
		name = (saved or {}).get("name")
	else:
		user = frappe.session.user
		try:
			frappe.set_user("Administrator")
			draft = frappe.get_attr(method)(
				row.reference_doctype,
				row.reference_name,
				party_amount=flt(row.amount),
				bank_account=settings.get("pay_deposit_account") or None,
			)
			draft.update(values)
			draft.insert()
			draft.submit()
			name = draft.name
		finally:
			frappe.set_user(user)
	if name:
		frappe.db.set_value(PAYMENT, row.name, {"payment_entry": name, "error": None})


def status_message(row, contact, status, text=None):
	body = text or _(STATUS_TEXT[status]).format(row.reference_name)
	interactive = {
		"type": "order_status",
		"body": {"text": body[:1024]},
		"action": {
			"name": "review_order",
			"parameters": {"reference_id": row.reference_id, "order": {"status": status}},
		},
	}
	return send_interactive(contact, row.whatsapp_account, "order_status", body, interactive)


def retry_pending():
	if not frappe.db.table_exists(PAYMENT):
		return
	since = add_to_date(now_datetime(), hours=-RETRY_HOURS)
	names = frappe.get_all(
		PAYMENT,
		filters={
			"status": ["in", ["Pending", "Failed"]],
			"provider": ["!=", "upi_vpa"],
			"creation": [">=", since],
		},
		pluck="name",
		order_by="creation asc",
		limit=RETRY_LIMIT,
	)
	for name in names:
		try:
			row = frappe.get_doc(PAYMENT, name)
			info = lookup(row)
			if not info:
				continue
			before = row.status
			apply(row, info)
			if row.status != before:
				announce(row)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"OneChat WhatsApp payment retry: {name}")


@frappe.whitelist(methods=["POST"])
def refresh(name: str):
	row = load(name)
	apply(row, lookup(row))
	announce(row)
	return summary(row)


@frappe.whitelist(methods=["POST"])
def update_status(name: str, status: str, note: str | None = None):
	row = load(name)
	require(PAYMENT, "write", row.name)
	if status not in FLOW.get(row.order_status or "pending", ()):
		frappe.throw(_("The order can't move from {0} to {1}.").format(_(row.order_status), _(status)))
	if status != "canceled" and row.status not in ("Paid", "Partly Refunded"):
		frappe.throw(_("Wait for the payment before updating the order."))
	contact = frappe.get_doc(CONTACT, row.contact)
	if not window(contact.name):
		frappe.throw(
			_("The customer hasn't written in the last 24 hours, so WhatsApp won't deliver order updates.")
		)
	status_message(row, contact, status, (note or "").strip() or None)
	row.order_status = status
	if status == "canceled" and row.status in ("Pending", "Failed"):
		row.status = "Canceled"
	keep(row)
	announce(row)
	return summary(row)


@frappe.whitelist(methods=["POST"])
def mark_paid(name: str, reference: str | None = None):
	row = load(name)
	require(PAYMENT, "write", row.name)
	if row.provider != "upi_vpa":
		frappe.throw(_("Gateway payments are confirmed by WhatsApp. Use Check status instead."))
	if row.status not in ("Pending", "Failed"):
		frappe.throw(_("This request is already {0}.").format(_(row.status)))
	if not (reference or "").strip():
		frappe.throw(_("Enter the UPI reference (UTR) from your bank app."))
	row.status = "Paid"
	row.method = "upi"
	row.pg_transaction_id = reference.strip()
	row.paid_at = now_datetime()
	row.error = None
	keep(row)
	paid_now(row)
	announce(row)
	return summary(frappe.get_doc(PAYMENT, row.name))


@frappe.whitelist(methods=["POST"])
def refund(name: str, amount: float | int | str | None = None, speed: str = "normal"):
	row = load(name)
	require(PAYMENT, "write", row.name)
	if not is_admin():
		frappe.throw(_("Only OneChat admins can refund payments."), frappe.PermissionError)
	if row.provider == "upi_vpa":
		frappe.throw(_("UPI payments to your own UPI ID are refunded from your bank app."))
	if row.status not in ("Paid", "Partly Refunded"):
		frappe.throw(_("Only paid requests can be refunded."))
	left = flt(row.amount) - flt(row.refunded_amount)
	value = flt(amount) or left
	if value <= 0 or value - left > 0.01:
		frappe.throw(_("Enter an amount between 1 and {0}.").format(money(left)))
	account = frappe.get_doc(ACCOUNT, row.whatsapp_account)
	result = graph(
		account,
		"POST",
		f"{account.phone_id}/payments_refund",
		payload={
			"reference_id": row.reference_id,
			"speed": "instant" if speed == "instant" else "normal",
			"payment_config_id": row.configuration,
			"amount": {"currency": "INR", "value": paise(value), "offset": OFFSET},
		},
	)
	row.refund_id = result.get("id") or row.refund_id
	row.refunded_amount = flt(row.refunded_amount) + value
	row.status = "Refunded" if row.refunded_amount >= flt(row.amount) - 0.01 else "Partly Refunded"
	keep(row)
	announce(row)
	return summary(row)


def withdraw(row):
	contact = frappe.get_doc(CONTACT, row.contact)
	if window(contact.name):
		try:
			status_message(
				row,
				contact,
				"canceled",
				_("This payment request for {0} has been withdrawn.").format(row.reference_name),
			)
		except Exception:
			frappe.log_error(title="OneChat withdraw WhatsApp payment")
	row.status = "Canceled"
	row.order_status = "canceled"
	keep(row)
	announce(row)


def cancel_open(doctype, name, keep=None):
	if not frappe.db.table_exists(PAYMENT):
		return []
	done = []
	for payment in frappe.get_all(
		PAYMENT,
		filters={"reference_doctype": doctype, "reference_name": name, "status": "Pending"},
		pluck="name",
	):
		if payment == keep:
			continue
		try:
			withdraw(frappe.get_doc(PAYMENT, payment))
			done.append(payment)
		except Exception:
			frappe.log_error(title="OneChat cancel WhatsApp payment")
	return done


def delivered(doc, method=None):
	orders = {
		row.get("against_sales_order") for row in doc.get("items") or [] if row.get("against_sales_order")
	}
	if not orders or not frappe.db.table_exists(PAYMENT):
		return
	for name in frappe.get_all(
		PAYMENT,
		filters={
			"reference_doctype": "Sales Order",
			"reference_name": ["in", list(orders)],
			"status": "Paid",
			"order_status": ["in", ["pending", "processing", "partially_shipped"]],
		},
		pluck="name",
	):
		try:
			row = frappe.get_doc(PAYMENT, name)
			contact = frappe.get_doc(CONTACT, row.contact)
			if not window(contact.name):
				continue
			status_message(row, contact, "shipped")
			row.order_status = "shipped"
			keep(row)
			announce(row)
		except Exception:
			frappe.log_error(title="OneChat WhatsApp order shipped")
