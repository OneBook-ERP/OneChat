import json
from urllib.parse import parse_qs, urlparse

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, formatdate, get_url

from onechat.inbox.conversations import CONTACT, MESSAGE, guard
from onechat.inbox.visibility import check as check_visible
from onechat.integrations.erpnext_commerce import ERP, OPEN_REQUESTS, account_for, send_text
from onechat.workspace.session import require_admin

SETTINGS = "OneChat Settings"
REQUEST = "Payment Request"
PAYABLE = ("Sales Invoice", "Sales Order")
CLOSED_ORDERS = ["Closed", "Completed", "Cancelled", "On Hold"]
LIMIT = 20


class PaymentError(frappe.ValidationError):
	pass


def config():
	return frappe.get_cached_doc(SETTINGS)


GATEWAY_CACHE = "onechat:payments:gateways"
GATEWAY_TTL = 300


def gateway_accounts(fresh=False):
	cached = None if fresh else frappe.cache().get_value(GATEWAY_CACHE)
	if cached is not None:
		return cached
	try:
		rows = [
			dict(row)
			for row in ERP.source().get_all(
				"Payment Gateway Account",
				fields=["name", "payment_gateway", "company", "currency", "is_default"],
				limit=50,
			)
		]
	except Exception:
		rows = []
	frappe.cache().set_value(GATEWAY_CACHE, rows, expires_in_sec=GATEWAY_TTL)
	return rows


def gateway_ready():
	return any(cint(row.get("is_default")) for row in gateway_accounts())


def due_of(doctype, row):
	if doctype == "Sales Invoice":
		return flt(row.get("outstanding_amount"))
	return max(flt(row.get("rounded_total")) or flt(row.get("grand_total")), 0) - flt(row.get("advance_paid"))


def money(amount, currency):
	return fmt_money(amount, currency=currency)


def customers_of(contact):
	found = []
	if contact.get("reference_doctype") == "Customer" and contact.get("reference_docname"):
		found.append(contact.reference_docname)
	name = contact.get("name")
	if name and frappe.db.exists(CONTACT, name):
		from onechat.integrations import links

		found += [row.name for row in links.of(name) if row.doctype == "Customer"]
	return list(dict.fromkeys(found))


def payable(contact):
	customers = customers_of(contact)
	if not customers:
		return []
	source = ERP.source()
	from onechat.workspace.session import can_read

	invoices = source.remote or can_read("Sales Invoice")
	orders = source.remote or can_read("Sales Order")
	out = []
	for row in (
		[]
		if not invoices
		else source.get_all(
			"Sales Invoice",
			filters={"customer": ["in", customers], "docstatus": 1, "outstanding_amount": [">", 0]},
			fields=[
				"name",
				"customer",
				"posting_date",
				"due_date",
				"grand_total",
				"outstanding_amount",
				"currency",
			],
			order_by="posting_date desc",
			limit=LIMIT,
		)
	):
		due = due_of("Sales Invoice", row)
		out.append(
			{
				"doctype": "Sales Invoice",
				"name": row.name,
				"date": formatdate(row.posting_date),
				"hint": _("Due {0}").format(formatdate(row.due_date)) if row.get("due_date") else "",
				"total": money(row.grand_total, row.currency),
				"due": due,
				"due_label": money(due, row.currency),
				"currency": row.currency,
				"customer": row.get("customer"),
			}
		)
	for row in (
		[]
		if not orders
		else source.get_all(
			"Sales Order",
			filters={"customer": ["in", customers], "docstatus": 1, "status": ["not in", CLOSED_ORDERS]},
			fields=[
				"name",
				"customer",
				"transaction_date",
				"delivery_date",
				"grand_total",
				"rounded_total",
				"advance_paid",
				"currency",
				"per_billed",
			],
			order_by="transaction_date desc",
			limit=LIMIT,
		)
	):
		due = due_of("Sales Order", row)
		if due <= 0 or flt(row.get("per_billed")) >= 100:
			continue
		out.append(
			{
				"doctype": "Sales Order",
				"name": row.name,
				"date": formatdate(row.transaction_date),
				"hint": _("Delivery {0}").format(formatdate(row.delivery_date))
				if row.get("delivery_date")
				else "",
				"total": money(row.get("rounded_total") or row.grand_total, row.currency),
				"due": due,
				"due_label": money(due, row.currency),
				"currency": row.currency,
				"customer": row.get("customer"),
			}
		)
	return out


@frappe.whitelist()
def payable_documents(contact: str):
	guard()
	check_visible(contact)
	doc = frappe.get_doc(CONTACT, contact)
	from onechat.whatsapp.pay import available

	return {
		"documents": with_open(payable(doc)),
		"gateway": gateway_ready(),
		"window": window(contact),
		"template": bool(config().get("payment_template")),
		"whatsapp": available(doc),
	}


def window(contact):
	from onechat.inbox.service import window_open

	return window_open(contact)


def open_request(source, doctype, name, amount=None):
	rows = source.get_all(
		REQUEST,
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"docstatus": 1,
			"status": ["in", OPEN_REQUESTS],
			"payment_url": ["is", "set"],
		},
		fields=["name", "payment_url", "grand_total"],
		order_by="creation desc",
		limit=10,
	)
	for row in rows:
		if amount is None or abs(flt(row.grand_total) - flt(amount)) < 0.01:
			return row
	return None


def create_request(source, doc, amount):
	partial = amount is not None and abs(flt(amount) - due_of(doc.doctype, doc)) >= 0.01
	if source.remote:
		request = source.call(
			"erpnext.accounts.doctype.payment_request.payment_request.make_payment_request",
			dt=doc.doctype,
			dn=doc.name,
			party_type="Customer",
			party=doc.customer,
			submit_doc=0,
			mute_email=1,
			return_doc=1,
		)
		name = (request or {}).get("name")
		if not name:
			raise PaymentError(_("ERPNext did not create the payment request."))
		if partial:
			source.update(REQUEST, name, {"grand_total": flt(amount)})
		fresh = source.get_doc(REQUEST, name)
		if cint(fresh.get("docstatus")) == 0:
			fresh = source.submit(fresh)
		return name, (fresh or {}).get("payment_url") or source.get_value(REQUEST, name, "payment_url")

	from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request

	request = make_payment_request(
		dt=doc.doctype,
		dn=doc.name,
		party_type="Customer",
		party=doc.customer,
		submit_doc=0,
		mute_email=1,
		return_doc=1,
	)
	if partial:
		request.grand_total = flt(amount)
	request.flags.mute_email = True
	request.flags.ignore_permissions = bool(frappe.flags.onechat_desk_payment)
	if request.docstatus == 0:
		request.submit()
	return request.name, request.payment_url


def pick_request(source, doc, amount=None):
	existing = open_request(source, doc.doctype, doc.name, amount)
	if existing:
		return existing.name, existing.payment_url
	try:
		return create_request(source, doc, amount)
	except Exception as error:
		fallback = open_request(source, doc.doctype, doc.name)
		if fallback:
			return fallback.name, fallback.payment_url
		raise PaymentError(_("Could not create the payment link: {0}").format(str(error))) from error


def gateway_link(name):
	if "payments" not in frappe.get_installed_apps():
		return None
	request = frappe.get_doc(REQUEST, name)
	if not request.get("payment_gateway"):
		return None
	try:
		from payments.utils import get_payment_gateway_controller

		controller = get_payment_gateway_controller(request.payment_gateway)
		if hasattr(controller, "validate_transaction_currency"):
			controller.validate_transaction_currency(request.currency)
		party = (
			frappe.db.get_value(
				request.reference_doctype, request.reference_name, ["company", "customer_name"], as_dict=True
			)
			or {}
		)
		url = controller.get_payment_url(
			amount=flt(request.grand_total),
			title=party.get("company") or request.get("company") or "",
			description=request.get("subject") or _("Payment for {0}").format(request.reference_name),
			reference_doctype=REQUEST,
			reference_docname=request.name,
			payer_email=request.get("email_to") or frappe.session.user,
			payer_name=party.get("customer_name") or request.get("party") or "",
			currency=request.currency,
			receipt=request.name,
			payment_gateway=request.payment_gateway,
		)
	except Exception:
		frappe.log_error(title=f"OneChat payment link: {request.payment_gateway}")
		return None
	if not url:
		return None
	if not url.startswith("http"):
		url = get_url("/" + url.lstrip("./"))
	frappe.db.set_value(REQUEST, request.name, "payment_url", url, update_modified=False)
	return url


def link_for(doc, amount=None):
	source = ERP.source()
	name, url = pick_request(source, doc, amount)
	if not source.remote:
		url = gateway_link(name) or url
	return name, url


def send_template(contact, template, values, reference=None):
	frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Template",
			"use_template": 1,
			"template": template,
			"message": "Template message",
			"content_type": "text",
			"to": contact.mobile_no,
			"body_param": json.dumps({str(index): str(value) for index, value in enumerate(values, start=1)}),
			"whatsapp_account": account_for(contact),
			"reference_doctype": reference[0] if reference else CONTACT,
			"reference_name": reference[1] if reference else contact.name,
		}
	).insert(ignore_permissions=True)


def send_button(contact, text, url, label, footer=None, reference=None, request=None):
	frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Manual",
			"to": contact.mobile_no,
			"message": text,
			"content_type": "interactive",
			"source": "Agent",
			"buttons": json.dumps(
				{
					"type": "cta_url",
					"button": label[:20],
					"url": url,
					"header": _("Payment request"),
					"footer": footer,
					"payment_request": request,
				}
			),
			"whatsapp_account": account_for(contact),
			"reference_doctype": reference[0] if reference else CONTACT,
			"reference_name": reference[1] if reference else contact.name,
		}
	).insert(ignore_permissions=True)


def deliver(contact, text, template, values, reference=None, quiet=False, link=None, reply_to=None):
	open_chat = window(contact.name)
	if not open_chat and template:
		send_template(contact, template, values, reference)
		return True
	if not open_chat and quiet:
		return False
	if link:
		send_button(
			contact, text, link["url"], link["label"], link.get("footer"), reference, link.get("request")
		)
	else:
		send_text(contact, text, reference, reply_to)
	return True


def first_name(contact):
	return (contact.get("contact_name") or "").split(" ")[0] or _("there")


def request_payment(contact, payload=None):
	payload = frappe._dict(payload or {})
	if payload.get("method") == "whatsapp":
		from onechat.whatsapp.pay import send_order

		return send_order(contact, payload)
	doctype, name = payload.get("doctype"), payload.get("name")
	if doctype not in PAYABLE or not name:
		raise PaymentError(_("Pick an invoice or an order."))
	if not contact.get("mobile_no"):
		raise PaymentError(_("This contact has no WhatsApp number."))
	if not gateway_ready():
		raise PaymentError(_("Set up a default payment gateway in ERPNext first (Payment Gateway Account)."))
	source = ERP.source()
	doc = source.get_doc(doctype, name)
	customers = customers_of(contact)
	if customers and doc.get("customer") not in customers:
		raise PaymentError(_("{0} belongs to a customer that isn't linked to this chat.").format(name))
	if cint(doc.get("docstatus")) != 1:
		raise PaymentError(_("{0} must be submitted before asking for payment.").format(name))

	due = due_of(doctype, doc)
	amount = flt(payload.get("amount")) or None
	if due <= 0:
		raise PaymentError(_("Nothing is due on {0}.").format(name))
	if amount is not None and (amount <= 0 or amount - due > 0.01):
		raise PaymentError(_("Enter an amount between 1 and {0}.").format(money(due, doc.currency)))

	request, url = link_for(doc, amount)
	if not url:
		raise PaymentError(_("ERPNext did not return a payment link. Check the payment gateway settings."))
	cancel_requests(doctype, name, keep=request)
	from onechat.whatsapp.pay import cancel_open

	cancel_open(doctype, name)

	text_amount = money(amount or due, doc.currency)
	message = (payload.get("message") or "").strip() or _(
		"Hi {0}, here is your payment request for {1} {2}."
	).format(first_name(contact), _(doctype), name)
	summary = "\n".join(
		[message, "", _("Amount: {0}").format(text_amount), _("For: {0} {1}").format(_(doctype), name)]
	)
	deliver(
		contact,
		summary,
		config().get("payment_template"),
		[first_name(contact), text_amount, name, url],
		None if source.remote else (doctype, name),
		link={
			"url": url,
			"label": _("Pay {0}").format(text_amount),
			"footer": _("Secure payment link"),
			"request": request,
		},
	)
	return _("Payment request for {0} sent").format(text_amount)


def request_needs(payload=None):
	out = [("OneChat Message", "create")]
	if payload is None:
		return out
	if (payload or {}).get("method") == "whatsapp":
		return [*out, ("OneChat WhatsApp Payment", "create")]
	return [*out, (REQUEST, "create")]


def require_erp(doctype, ptype):
	if not ERP.source().remote:
		from onechat.workspace.session import require

		require(doctype, ptype)


def send_link(contact, doctype, name):
	return request_payment(contact, {"doctype": doctype, "name": name})


def can_link(contact, doctype, name):
	customers = customers_of(contact)
	if doctype not in PAYABLE or not customers or not contact.get("mobile_no"):
		return False
	fields = (
		["customer", "docstatus", "outstanding_amount"]
		if doctype == "Sales Invoice"
		else ["customer", "docstatus", "grand_total", "rounded_total", "advance_paid", "status"]
	)
	row = ERP.source().get_value(doctype, name, fields)
	if not row or row.get("customer") not in customers or cint(row.get("docstatus")) != 1:
		return False
	if doctype == "Sales Order" and row.get("status") in CLOSED_ORDERS:
		return False
	return due_of(doctype, row) > 0


def has_payables(contact):
	return bool(contact.get("mobile_no")) and bool(customers_of(contact))


def receipt(contact, doc):
	settings = config()
	if not cint(settings.get("payment_receipts") if settings.get("payment_receipts") is not None else 1):
		return False
	amount = money(doc.get("grand_total"), doc.get("currency"))
	reference = doc.get("reference_name") or doc.get("name")
	text = _("✅ Paid: we received {0} for {1}. Thank you!").format(amount, reference)
	values = [
		first_name(contact),
		amount,
		reference,
		formatdate(doc.get("transaction_date") or doc.get("modified")),
		doc.get("mode_of_payment") or _("Online"),
	]
	return deliver(
		contact,
		text,
		settings.get("receipt_template"),
		values,
		None if ERP.is_remote() else (doc.get("doctype"), doc.get("name")),
		quiet=True,
		reply_to=link_message_id(contact.name, doc.get("name")),
	)


def link_message_id(contact, request):
	names = [row.name for row in link_messages(request) if row.whatsapp_contact == contact] if request else []
	if not names:
		return None
	return frappe.db.get_value(
		MESSAGE, {"name": ["in", names], "message_id": ["is", "set"]}, "message_id", order_by="creation desc"
	)


@frappe.whitelist()
def get_settings():
	require_admin()
	settings = config()
	return {
		"payment_template": settings.get("payment_template") or "",
		"receipt_template": settings.get("receipt_template") or "",
		"payment_receipts": bool(
			cint(settings.get("payment_receipts") if settings.get("payment_receipts") is not None else 1)
		),
		"desk_payment_links": desk_enabled(),
		"gateways": gateway_accounts(fresh=True),
		"ready": gateway_ready(),
	}


@frappe.whitelist(methods=["POST"])
def save_settings(
	payment_template: str | None = None,
	receipt_template: str | None = None,
	payment_receipts: bool | int | str = 1,
	desk_payment_links: bool | int | str = 1,
):
	require_admin()
	doc = frappe.get_doc(SETTINGS)
	doc.payment_template = payment_template or None
	doc.receipt_template = receipt_template or None
	doc.payment_receipts = cint(payment_receipts)
	if doc.meta.has_field("desk_payment_links"):
		doc.desk_payment_links = cint(desk_payment_links)
	doc.save(ignore_permissions=True)
	return get_settings()


def desk_enabled():
	settings = config()
	value = settings.get("desk_payment_links")
	return bool(cint(value if value is not None else 1))


def desk_available():
	from onechat.integrations.erpnext_commerce import enabled

	return desk_enabled() and enabled() and not ERP.is_remote()


def desk_check(doctype, name):
	if not desk_available():
		raise PaymentError(
			_(
				"Sending payment links from Desk is turned off. Ask an admin to turn it on in OneChat Settings → Payments."
			)
		)
	if doctype not in PAYABLE:
		raise PaymentError(_("Payment links can only be sent for Sales Orders and Sales Invoices."))
	frappe.has_permission(doctype, "read", doc=name, throw=True)
	if not frappe.has_permission(REQUEST, "create"):
		raise frappe.PermissionError(
			_("You need permission to create Payment Requests to send payment links.")
		)
	return frappe.get_doc(doctype, name)


def customer_mobile(doc):
	number = doc.get("contact_mobile") or frappe.db.get_value("Customer", doc.customer, "mobile_no")
	if number:
		return number
	rows = frappe.get_all(
		"Contact",
		filters=[
			["Dynamic Link", "link_doctype", "=", "Customer"],
			["Dynamic Link", "link_name", "=", doc.customer],
		],
		fields=["mobile_no", "phone"],
		order_by="is_primary_contact desc",
		limit=5,
	)
	return next((row.mobile_no or row.phone for row in rows if row.mobile_no or row.phone), "")


@frappe.whitelist()
def desk_link_options(doctype: str, name: str):
	doc = desk_check(doctype, name)
	from onechat.inbox.conversations import find_contact

	number = customer_mobile(doc)
	contact = find_contact(number) if number else None
	due = due_of(doctype, doc)
	from onechat.whatsapp.pay import available

	whatsapp = False
	if contact:
		view = frappe.get_doc(CONTACT, contact)
		whatsapp = available(view) and (doc.get("currency") or "INR") == "INR"
	return {
		"whatsapp": whatsapp,
		"open": with_open([{"name": name}])[0]["open"],
		"mobile_no": number or "",
		"due": due,
		"due_label": money(due, doc.currency),
		"currency": doc.currency,
		"customer": doc.customer,
		"customer_name": doc.get("customer_name") or doc.customer,
		"window": bool(contact and window(contact)),
		"template": bool(config().get("payment_template")),
		"gateway": gateway_ready(),
	}


@frappe.whitelist(methods=["POST"])
def desk_send_link(
	doctype: str,
	name: str,
	mobile_no: str | int | None = None,
	amount: float | int | str | None = None,
	message: str | None = None,
	method: str | None = None,
):
	import copy

	from onechat.inbox.conversations import find_contact
	from onechat.integrations import links

	doc = desk_check(doctype, name)
	number = (mobile_no or "").strip() or customer_mobile(doc)
	if not number:
		raise PaymentError(_("Add the customer's WhatsApp number first."))

	contact = find_contact(number)
	if not contact:
		contact = (
			frappe.get_doc(
				{
					"doctype": CONTACT,
					"contact_name": doc.get("customer_name") or doc.customer,
					"mobile_no": number,
					"reference_doctype": "Customer",
					"reference_docname": doc.customer,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	if not links.has(contact, "Customer", doc.customer):
		links.add(contact, "Customer", doc.customer)

	view = copy.copy(frappe.get_doc(CONTACT, contact))
	view.reference_doctype, view.reference_docname = "Customer", doc.customer
	frappe.flags.onechat_desk_payment = True
	try:
		result = request_payment(
			view,
			{
				"doctype": doctype,
				"name": name,
				"amount": flt(amount) or None,
				"message": message,
				"method": "whatsapp" if method == "whatsapp" else None,
			},
		)
	finally:
		frappe.flags.onechat_desk_payment = False
	return result


def open_requests_for(source, doctype, name):
	return source.get_all(
		REQUEST,
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"docstatus": 1,
			"status": ["in", OPEN_REQUESTS],
		},
		fields=["name", "grand_total", "status"],
		limit=20,
	)


def cancel_request(source, name):
	if source.remote:
		source.call("frappe.client.cancel", doctype=REQUEST, name=name)
		return
	request = frappe.get_doc(REQUEST, name)
	if request.docstatus != 1:
		return
	request.flags.ignore_permissions = True
	request.cancel()


def cancel_requests(doctype, name, keep=None):
	source = ERP.source()
	done = []
	try:
		rows = open_requests_for(source, doctype, name)
	except Exception:
		frappe.log_error(title="OneChat open payment requests")
		return done
	for row in rows:
		if row.get("name") == keep:
			continue
		try:
			cancel_request(source, row.get("name"))
			done.append(row.get("name"))
		except Exception:
			frappe.log_error(title="OneChat cancel payment request")
	return done


def with_open(rows):
	if not rows:
		return rows
	names = [row["name"] for row in rows]
	links = {}
	try:
		for row in ERP.source().get_all(
			REQUEST,
			filters={"reference_name": ["in", names], "docstatus": 1, "status": ["in", OPEN_REQUESTS]},
			fields=["name", "reference_name"],
			limit=100,
		):
			links.setdefault(row.get("reference_name"), []).append(row.get("name"))
	except Exception:
		frappe.log_error(title="OneChat open payment requests")
	pending = {}
	if frappe.db.table_exists("OneChat WhatsApp Payment"):
		for row in frappe.get_all(
			"OneChat WhatsApp Payment",
			filters={"reference_name": ["in", names], "status": "Pending"},
			fields=["name", "reference_name"],
		):
			pending.setdefault(row.reference_name, []).append(row.name)
	for row in rows:
		row["open"] = {"links": links.get(row["name"], []), "whatsapp": pending.get(row["name"], [])}
	return rows


def request_statuses(names):
	if not names:
		return {}
	try:
		rows = ERP.source().get_all(
			REQUEST,
			filters={"name": ["in", list(names)]},
			fields=["name", "status", "docstatus"],
			limit=len(names),
		)
	except Exception:
		return {}
	return {
		row.get("name"): "Cancelled" if cint(row.get("docstatus")) == 2 else row.get("status") for row in rows
	}


@frappe.whitelist(methods=["POST"])
def cancel_link(message: str):
	guard()
	row = frappe.db.get_value(MESSAGE, message, ["whatsapp_contact", "buttons"], as_dict=True)
	if not row or not row.whatsapp_contact:
		raise PaymentError(_("This message has no payment request."))
	check_visible(row.whatsapp_contact)
	try:
		spec = json.loads(row.buttons or "{}")
	except ValueError:
		spec = {}
	request = spec.get("payment_request")
	if not request:
		raise PaymentError(_("This message has no payment request."))
	require_erp(REQUEST, "cancel")
	source = ERP.source()
	current = source.get_value(REQUEST, request, ["status", "docstatus"])
	if not current:
		raise PaymentError(_("Payment request {0} was not found.").format(request))
	if current.get("status") == "Paid":
		raise PaymentError(_("{0} is already paid. Refund it in ERPNext instead.").format(request))
	if cint(current.get("docstatus")) == 1 and current.get("status") in OPEN_REQUESTS:
		cancel_request(source, request)
	from onechat.inbox.conversations import publish

	publish(row.whatsapp_contact, message)
	return _("Payment request {0} cancelled").format(request)


def link_messages(request):
	return frappe.get_all(
		MESSAGE,
		filters={
			"content_type": "interactive",
			"buttons": ["like", f'%"payment_request": {json.dumps(request)}%'],
		},
		fields=["name", "whatsapp_contact", "owner"],
	)


def alert_request(doc):
	from onechat.workspace.notifications import payment_alert

	try:
		rows = link_messages(doc.get("name"))
		contact = next((row.whatsapp_contact for row in rows if row.whatsapp_contact), None)
		if not contact and doc.get("party_type") == "Customer" and doc.get("party"):
			from onechat.integrations import links

			contact = next(iter(links.contacts_for("Customer", doc.get("party"))), None)
		if not contact:
			return
		amount = money(flt(doc.get("grand_total")), doc.get("currency"))
		payment_alert(
			doc.get("name"),
			contact,
			amount,
			doc.get("reference_name") or doc.get("name"),
			[row.owner for row in rows],
		)
	except Exception:
		frappe.log_error(title=f"OneChat payment alert: {doc.get('name')}")


def refresh_links(request):
	if not request:
		return
	from onechat.inbox.conversations import publish

	for row in link_messages(request):
		if row.whatsapp_contact:
			publish(row.whatsapp_contact, row.name)


INTEGRATION = "Integration Request"
SETTLED = ("Authorized", "Completed", "Cancelled")


def checkout_tokens(request, url=None):
	names = frappe.get_all(
		INTEGRATION, filters={"reference_doctype": REQUEST, "reference_docname": request}, pluck="name"
	)
	token = (parse_qs(urlparse(url or "").query).get("token") or [None])[0]
	if token and frappe.db.exists(INTEGRATION, token):
		names.append(token)
	return list(dict.fromkeys(names))


def expire_checkout(request, url=None):
	if ERP.source().remote or not frappe.db.table_exists(INTEGRATION):
		return 0
	if url is None and frappe.db.table_exists(REQUEST):
		url = frappe.db.get_value(REQUEST, request, "payment_url")
	closed = 0
	for name in checkout_tokens(request, url):
		if frappe.db.get_value(INTEGRATION, name, "status") not in SETTLED:
			frappe.db.set_value(INTEGRATION, name, "status", "Cancelled", update_modified=False)
			closed += 1
	return closed


def request_changed(doc, method=None):
	try:
		if doc.get("docstatus") == 2 or doc.get("status") in ("Failed", "Cancelled"):
			expire_checkout(doc.name, doc.get("payment_url"))
		refresh_links(doc.name)
	except Exception:
		frappe.log_error(title=f"OneChat payment link refresh: {doc.name}")


@frappe.whitelist(methods=["POST"])
def mark_link(message: str, status: str):
	guard()
	if status not in ("Paid", "Failed"):
		raise PaymentError(_("Choose Paid or Failed."))
	if status == "Paid":
		require_admin()
	row = frappe.db.get_value(MESSAGE, message, ["whatsapp_contact", "buttons"], as_dict=True)
	if not row or not row.whatsapp_contact:
		raise PaymentError(_("This message has no payment request."))
	check_visible(row.whatsapp_contact)
	try:
		request = json.loads(row.buttons or "{}").get("payment_request")
	except ValueError:
		request = None
	if not request:
		raise PaymentError(_("This message has no payment request."))
	if ERP.source().remote:
		raise PaymentError(_("ERPNext is on another site. Update {0} there.").format(request))
	require_erp("Payment Entry" if status == "Paid" else REQUEST, "create" if status == "Paid" else "write")
	doc = frappe.get_doc(REQUEST, request)
	if doc.docstatus != 1 or doc.status in ("Paid", "Cancelled"):
		raise PaymentError(
			_("{0} is already {1}.").format(request, _(doc.status if doc.docstatus == 1 else "Cancelled"))
		)
	if status == "Paid":
		from onechat.integrations.erpnext_commerce import mark_request_paid

		mark_request_paid(doc)
	else:
		doc.db_set("status", "Failed")
		expire_checkout(request, doc.get("payment_url"))
	refresh_links(request)
	return _("{0} marked as {1}").format(request, _(status).lower())
