import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, formatdate, get_url

from onechat.assistant.tools import as_agent
from onechat.integrations import connection

SHOW = re.compile(r"<show>(.*?)</show>", re.S)
NEXT = re.compile(r"<next>(.*?)</next>", re.S)
CARD_LIMIT = 8
NEXT_LIMIT = 3
CHIP_TEXT = 60
FIELD_LIMIT = 3
TEXT_LIMIT = 60
STATUS_FIELDS = ("status", "workflow_state", "conversation_status")
AMOUNT_FIELDS = (
	"rounded_total",
	"grand_total",
	"total",
	"paid_amount",
	"amount",
	"deal_value",
	"opportunity_amount",
	"annual_revenue",
)
DATE_FIELDS = ("posting_date", "transaction_date", "delivery_date", "due_date", "date", "schedule_date")
PARTY_FIELDS = (
	"customer_name",
	"party_name",
	"supplier_name",
	"lead_name",
	"organization",
	"contact_name",
	"employee_name",
	"customer",
)
SKIP_TYPES = (
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Table",
	"Table MultiSelect",
	"Text Editor",
	"Long Text",
	"Code",
	"JSON",
	"Attach Image",
	"Password",
)
DOCSTATUS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
GREEN = (
	"paid",
	"completed",
	"closed",
	"won",
	"converted",
	"approved",
	"active",
	"delivered",
	"submitted",
	"resolved",
)
RED = ("overdue", "cancelled", "lost", "rejected", "failed", "expired", "unpaid")
AMBER = ("draft", "to pay", "to bill", "to deliver", "pending", "open", "partly paid", "on hold", "replied")
ROUTES = {
	"OneChat Contact": "/inbox/{name}",
	"OneChat Flow": "/automation/flows/{name}",
	"WhatsApp Flow": "/campaigns/forms/{name}",
}
CRM_PATHS = {"CRM Lead": "/crm/leads/{name}", "CRM Deal": "/crm/deals/{name}"}
PAYABLE = ("Sales Order", "Sales Invoice")


def shown(text):
	pairs = []
	for block in SHOW.findall(text or ""):
		doctype, _sep, names = block.partition(":")
		doctype = doctype.strip()
		for name in re.split(r"[,\n]", names):
			name = name.strip().strip(".")
			if doctype and name and (doctype, name) not in pairs:
				pairs.append((doctype, name))
	return pairs[:CARD_LIMIT]


def chips(text):
	out = []
	for block in NEXT.findall(text or ""):
		for part in re.split(r"[|\n]", block):
			part = part.strip(" -•\t")
			if part and part not in out:
				out.append(part[:CHIP_TEXT])
	return out[:NEXT_LIMIT]


def strip(text):
	return NEXT.sub("", SHOW.sub("", text or "")).strip()


def build(text, contact):
	cards = []
	for doctype, name in shown(text):
		try:
			made = card(doctype, name, contact)
		except Exception:
			frappe.log_error(title=f"OneChat assistant card: {doctype} {name}")
			made = None
		if made:
			cards.append(made)
	return {"cards": cards, "tiles": tiles(cards), "next": chips(text)}


def card(doctype, name, contact):
	owner = connection.owner_of(doctype)
	doc = remote_doc(owner, doctype, name) if owner else local_doc(doctype, name)
	if not doc:
		return None
	fields, title_field, submittable = layout(owner, doctype)
	by_name = {row["fieldname"]: row for row in fields}
	currency = doc.get("currency") or doc.get("company_currency") or frappe.db.get_default("currency")
	used = {"name", title_field}

	title = doc.get(title_field) if title_field else None
	party = next((doc.get(key) for key in PARTY_FIELDS if doc.get(key)), None)
	status = next((doc.get(key) for key in STATUS_FIELDS if doc.get(key)), None)
	if not status and submittable and doc.get("docstatus") is not None:
		status = DOCSTATUS.get(cint(doc.get("docstatus")))
	amount_field = next((key for key in AMOUNT_FIELDS if flt(doc.get(key))), None)
	date_field = next((key for key in DATE_FIELDS if doc.get(key)), None)
	due = flt(doc.get("outstanding_amount"))
	if doctype == "Sales Order" and doc.get("docstatus") == 1:
		due = max(flt(doc.get("rounded_total") or doc.get("grand_total")) - flt(doc.get("advance_paid")), 0)
	used.update({amount_field, date_field, "outstanding_amount", *STATUS_FIELDS, *PARTY_FIELDS})
	if amount_field:
		used.update(AMOUNT_FIELDS)

	extras = []
	for row in fields:
		key = row["fieldname"]
		if len(extras) >= FIELD_LIMIT:
			break
		if not row.get("in_list_view") or key in used or row.get("fieldtype") in SKIP_TYPES:
			continue
		value = shown_value(doc.get(key), row.get("fieldtype"), currency)
		if value and value not in (title, party, name):
			extras.append({"label": _(row.get("label") or key), "value": value})

	def label(key):
		return _((by_name.get(key) or {}).get("label") or key.replace("_", " ").title())

	return {
		"doctype": doctype,
		"doctype_label": _(doctype),
		"name": name,
		"title": str(title or party or doc.get("title") or name)[:TEXT_LIMIT],
		"subtitle": str(party)[:TEXT_LIMIT] if party and party != title else "",
		"status": _(status) if status else "",
		"theme": theme(status),
		"amount": {"label": label(amount_field), "value": money(doc.get(amount_field), currency)}
		if amount_field
		else None,
		"due": {"label": _("Due"), "value": money(due, currency), "raw": due} if due > 0 else None,
		"date": formatdate(doc.get(date_field)) if date_field else "",
		"fields": extras,
		"currency": currency,
		"total": flt(doc.get(amount_field)) if amount_field else 0,
		"open": target(owner, doctype, name),
		"pay": bool(contact and doctype in PAYABLE and due > 0 and can_pay(contact, doctype, name)),
	}


def local_doc(doctype, name):
	if not frappe.db.exists(doctype, name) or not frappe.has_permission(doctype, "read", name):
		return None
	return frappe.get_doc(doctype, name).as_dict()


def remote_doc(owner, doctype, name):
	try:
		with as_agent():
			return connection.Remote(owner).get_doc(doctype, name) or None
	except frappe.ValidationError:
		frappe.clear_last_message()
		return None


def layout(owner, doctype):
	if owner:
		fields = connection.Remote(owner).meta_fields(doctype)
		return fields, None, False
	meta = frappe.get_meta(doctype)
	fields = [
		{
			"fieldname": row.fieldname,
			"label": row.label,
			"fieldtype": row.fieldtype,
			"in_list_view": row.in_list_view,
		}
		for row in meta.fields
		if row.fieldname
	]
	return fields, meta.title_field, bool(meta.is_submittable)


def shown_value(value, fieldtype, currency):
	if value in (None, "", 0) or isinstance(value, list | dict):
		return ""
	if fieldtype == "Currency":
		return money(value, currency)
	if fieldtype in ("Date", "Datetime"):
		return formatdate(value)
	if fieldtype == "Check":
		return _("Yes") if cint(value) else ""
	return str(value)[:TEXT_LIMIT]


def money(value, currency):
	return fmt_money(flt(value), currency=currency)


def theme(status):
	text = (status or "").lower()
	if any(word in text for word in RED):
		return "red"
	if any(word in text for word in GREEN):
		return "green"
	if any(word in text for word in AMBER):
		return "orange"
	return "gray"


def target(owner, doctype, name):
	safe = quote(str(name), safe="")
	if not owner and doctype in ROUTES:
		return {"route": ROUTES[doctype].format(name=safe)}
	if doctype in CRM_PATHS:
		path = CRM_PATHS[doctype].format(name=safe)
		return {"url": owner.url(path) if owner else get_url(path)}
	if owner:
		return {"url": owner.desk_url(doctype, name)}
	return {"url": get_url(f"/app/{frappe.scrub(doctype).replace('_', '-')}/{safe}")}


def can_pay(contact, doctype, name):
	from onechat.integrations.payments import can_link

	try:
		return can_link(frappe.get_doc("OneChat Contact", contact), doctype, name)
	except Exception:
		return False


def tiles(cards):
	if len(cards) < 2:
		return []
	currencies = {row["currency"] for row in cards if row["total"]}
	out = [{"label": _("Records"), "value": str(len(cards))}]
	if len(currencies) == 1:
		currency = currencies.pop()
		out.append({"label": _("Total"), "value": money(sum(row["total"] for row in cards), currency)})
		due = sum(row["due"]["raw"] for row in cards if row["due"])
		if due:
			out.append({"label": _("Due"), "value": money(due, currency)})
	return out


def progress_texts():
	change = _("Preparing the change")
	return {
		"count_and_total": _("Analysing the figures"),
		"customer_overview": _("Looking at the customer"),
		"find_items": _("Finding items"),
		"what_customer_owes": _("Checking what is due"),
		"create_document": change,
		"update_document": change,
		"submit_document": change,
		"send_payment_link": _("Preparing the payment link"),
		"send_message": _("Preparing the message"),
	}


def progress(tool, arguments):
	arguments = arguments or {}
	doctype = arguments.get("doctype") or ""
	if tool == "get_record" and doctype:
		return _("Opening {0} {1}").format(_(doctype), arguments.get("name") or "").strip()
	if tool == "search_records" and doctype:
		return _("Looking up {0} records").format(_(doctype))
	return progress_texts().get(tool) or _("Working on it")
