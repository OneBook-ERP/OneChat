import re

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, formatdate

from onechat.inbox.conversations import CONTACT, guard
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import connection, links

TEMPLATE = "WhatsApp Templates"
VARIABLE = re.compile(r"{{\s*(\d+)\s*}}")
MONEY_WORDS = ("total", "amount", "outstanding", "price", "rate", "paid", "due_amount")
DATE_WORDS = ("date", "_on", "until", "expiry")
TITLE_FIELDS = ("customer_name", "lead_name", "organization", "first_name", "title", "supplier_name")
GUESSES = (
	(re.compile(r"(hi|hello|hey|dear|namaste|vanakkam)[\s,]*$", re.I), "first_name"),
	(re.compile(r"(₹|rs\.?|inr|amount|total|due|pay|of)\s*$", re.I), "amount_due"),
	(re.compile(r"(order|invoice|bill|no\.?|number|#|ref\.?)\s*[:#]?\s*$", re.I), "document"),
	(re.compile(r"(date|on|by|before)\s*[:]?\s*$", re.I), "date"),
)
CONTEXT = 30


def variable_count(text):
	found = [int(match) for match in VARIABLE.findall(text or "")]
	return max(found) if found else 0


def split(value):
	return [part.strip() for part in (value or "").split(",")]


def is_money(field, value):
	return isinstance(value, int | float) and any(word in field for word in MONEY_WORDS)


def display(record, field):
	value = record.get(field)
	if value in (None, ""):
		return ""
	if is_money(field, value):
		return fmt_money(flt(value), currency=record.get("currency"))
	if any(word in field for word in DATE_WORDS):
		try:
			return formatdate(value)
		except Exception:
			return str(value)
	return str(value)


def readable(doctype, name):
	if connection.source_for(doctype).remote:
		return True
	from onechat.workspace.session import can_read

	return can_read(doctype, name)


def load(doctype, name):
	if not (doctype and name) or not readable(doctype, name):
		return None
	try:
		record = connection.source_for(doctype).get_doc(doctype, name)
	except Exception:
		return None
	as_dict = getattr(record, "as_dict", None)
	record = dict(as_dict() if callable(as_dict) else record or {})
	return record or None


def documents(contact, for_doctype):
	out = []
	try:
		from onechat.integrations.payments import payable

		for row in payable(contact):
			out.append(
				{
					"doctype": row["doctype"],
					"name": row["name"],
					"label": f"{_(row['doctype'])} {row['name']}",
					"hint": " · ".join(
						part
						for part in (
							row.get("due_label") and _("{0} due").format(row["due_label"]),
							row.get("date"),
						)
						if part
					),
				}
			)
	except Exception:
		frappe.log_error(title="OneChat template fill: documents")
	for row in links.of(contact):
		if not any((item["doctype"], item["name"]) == (row.doctype, row.name) for item in out):
			out.append(
				{
					"doctype": row.doctype,
					"name": row.name,
					"label": f"{_(row.doctype)} {row.name}",
					"hint": "",
				}
			)
	if for_doctype:
		out.sort(key=lambda item: item["doctype"] != for_doctype)
	return out


def due_of(record):
	if record.get("doctype") == "Sales Invoice":
		return flt(record.get("outstanding_amount"))
	if record.get("doctype") == "Sales Order":
		return max(flt(record.get("rounded_total")) or flt(record.get("grand_total")), 0) - flt(
			record.get("advance_paid")
		)
	return 0


def suggestions(contact, record):
	full = (contact.get("contact_name") or "").strip()
	out = [
		{
			"key": "first_name",
			"label": _("First name"),
			"value": full.split(" ")[0] if full else "",
			"source": _("Chat contact"),
		},
		{"key": "full_name", "label": _("Full name"), "value": full, "source": _("Chat contact")},
		{
			"key": "mobile",
			"label": _("WhatsApp number"),
			"value": contact.get("mobile_no") or "",
			"source": _("Chat contact"),
		},
	]
	main = next((row for row in links.of(contact) if row.main), None)
	if main:
		out.append(
			{"key": "record", "label": _(main.doctype), "value": main.name, "source": _("Linked record")}
		)
	if record:
		source = f"{_(record.get('doctype') or '')} {record.get('name') or ''}".strip()
		title = next((record.get(field) for field in TITLE_FIELDS if record.get(field)), None)
		due = due_of(record)
		rows = [
			("document", _("Document number"), record.get("name")),
			("customer", _("Customer name"), title),
			("total", _("Total"), display(record, "rounded_total") or display(record, "grand_total")),
			(
				"amount_due",
				_("Amount due"),
				fmt_money(due, currency=record.get("currency")) if due > 0 else "",
			),
			(
				"date",
				_("Date"),
				display(record, "due_date")
				or display(record, "delivery_date")
				or display(record, "posting_date")
				or display(record, "transaction_date"),
			),
		]
		out += [
			{"key": key, "label": label, "value": value, "source": source}
			for key, label, value in rows
			if value
		]
	return [row for row in out if row["value"]]


def guess(text, index, known):
	at = (text or "").find(f"{{{{{index}}}}}")
	if at < 0:
		return None
	before = text[max(0, at - CONTEXT) : at]
	for pattern, key in GUESSES:
		if pattern.search(before) and key in known:
			return known[key]
	return None


@frappe.whitelist()
def fill(contact: str, template: str, doctype: str | None = None, name: str | None = None):
	guard()
	check_visible(contact)
	row = frappe.get_doc(TEMPLATE, template)
	chat = frappe.get_doc(CONTACT, contact)
	count = variable_count(row.template)
	choices = documents(chat, row.get("for_doctype"))
	chosen = (
		next((item for item in choices if (item["doctype"], item["name"]) == (doctype, name)), None)
		if doctype and name
		else None
	)
	chosen = (
		chosen
		or next((item for item in choices if item["doctype"] == row.get("for_doctype")), None)
		or (choices[0] if choices else None)
	)
	record = load(chosen["doctype"], chosen["name"]) if chosen else None
	if record is not None:
		record.setdefault("doctype", chosen["doctype"])
	hints = suggestions(chat, record)
	known = {item["key"]: item for item in hints}
	fields = split(row.get("field_names"))
	contact_values = chat.as_dict()
	values = []
	for index in range(1, count + 1):
		field = fields[index - 1] if index - 1 < len(fields) else ""
		value, source, label = "", "", ""
		if field and record and record.get(field) not in (None, ""):
			value, source = display(record, field), f"{chosen['label']} · {field}"
		elif field and contact_values.get(field) not in (None, ""):
			value, source = display(contact_values, field), _("Chat contact · {0}").format(field)
		else:
			found = guess(row.template, index, known)
			if found:
				value, source = found["value"], _("{0} (guessed)").format(found["label"])
		if field:
			label = field.replace("_", " ").capitalize()
		values.append({"value": value, "source": source, "label": label})
	return {
		"values": values,
		"documents": choices,
		"document": {"doctype": chosen["doctype"], "name": chosen["name"]} if chosen else None,
		"suggestions": hints,
	}
