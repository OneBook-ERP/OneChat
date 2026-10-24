import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
ROW = "OneChat Contact Account"
FIELD = "accounts"
BATCH = 500
WINDOW_HOURS = 24


def window_open(row, at=None):
	stamp = row.get("last_incoming_at")
	return bool(stamp) and get_datetime(stamp) > add_to_date(at or now_datetime(), hours=-WINDOW_HOURS)


def reply_account(contact, hidden=None):
	current = frappe.db.get_value(CONTACT, contact, "whatsapp_account")
	rows = [row for row in rows_of(contact) if row.account not in (hidden or [])]
	ready = sorted(
		(row for row in rows if window_open(row)), key=lambda row: row.last_incoming_at, reverse=True
	)
	if not ready:
		return None
	if any(row.account == current for row in ready):
		return current
	return ready[0].account


def require_window(contact, account):
	row = next((row for row in rows_of(contact) if row.account == account), None)
	if row and not window_open(row):
		frappe.throw(_("The 24-hour reply window on {0} is closed. Send a template instead.").format(account))


def attach(rows):
	grouped = rows_for([row.name for row in rows])
	for row in rows:
		row.accounts = grouped.get(row.name, [])
	return rows


def row_updates(doc, preview, current=None, unread=True):
	incoming = doc.type == "Incoming"
	values = {
		"last_message": preview,
		"last_message_at": doc.creation,
		"last_message_type": doc.type or "Outgoing",
	}
	if incoming:
		values["last_incoming_at"] = doc.creation
		values["unread_count"] = cint((current or {}).get("unread_count")) + (1 if unread else 0)
	return values


def touch(contact, doc, preview, unread=True):
	account = doc.get("whatsapp_account")
	if not account or doc.content_type == "reaction":
		return
	current = frappe.db.get_value(
		ROW,
		{"parent": contact, "parenttype": CONTACT, "account": account},
		["name", "unread_count"],
		as_dict=True,
	)
	values = row_updates(doc, preview, current, unread)
	if current:
		frappe.db.set_value(ROW, current.name, values, update_modified=False)
		return
	frappe.get_doc(
		{
			"doctype": ROW,
			"parent": contact,
			"parenttype": CONTACT,
			"parentfield": FIELD,
			"account": account,
			**values,
		}
	).insert(ignore_permissions=True)


def clear_unread(contact, accounts=None):
	filters = {"parent": contact, "parenttype": CONTACT, "unread_count": [">", 0]}
	if accounts is not None:
		filters["account"] = ["in", list(accounts) or [""]]
	for name in frappe.get_all(ROW, filters=filters, pluck="name"):
		frappe.db.set_value(ROW, name, "unread_count", 0, update_modified=False)


def rows_of(contact):
	return frappe.get_all(
		ROW,
		filters={"parent": contact, "parenttype": CONTACT},
		fields=[
			"account",
			"last_message_at",
			"last_message",
			"last_message_type",
			"last_incoming_at",
			"unread_count",
		],
		order_by="last_message_at desc",
	)


def rows_for(contacts, exclude=None):
	if not contacts:
		return {}
	filters = {"parent": ["in", list(contacts)], "parenttype": CONTACT}
	if exclude:
		filters["account"] = ["not in", list(exclude)]
	grouped = {}
	for row in frappe.get_all(
		ROW,
		filters=filters,
		fields=[
			"parent",
			"account",
			"last_message_at",
			"last_message",
			"last_message_type",
			"last_incoming_at",
			"unread_count",
		],
		order_by="last_message_at desc",
	):
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def overlay(rows, hidden):
	if not hidden or not rows:
		return rows
	grouped = rows_for([row.name for row in rows], exclude=hidden)
	for row in rows:
		shown = grouped.get(row.name)
		if not shown:
			continue
		newest = shown[0]
		row.update(
			{
				"last_message": newest.last_message,
				"last_message_at": newest.last_message_at,
				"last_message_type": newest.last_message_type,
				"unread_count": sum(cint(item.unread_count) for item in shown),
			}
		)
	return rows


def read(contact, hidden=None):
	if not hidden:
		clear_unread(contact)
		frappe.db.set_value(CONTACT, contact, "unread_count", 0, update_modified=False)
		return 0
	shown = [row.account for row in rows_of(contact) if row.account not in hidden]
	clear_unread(contact, shown)
	left = sum(cint(row.unread_count) for row in rows_of(contact))
	frappe.db.set_value(CONTACT, contact, "unread_count", left, update_modified=False)
	return left


def backfill(contact):
	from onechat.inbox.conversations import preview

	seen = {}
	rows = frappe.get_all(
		MESSAGE,
		filters={
			"whatsapp_contact": contact,
			"content_type": ["!=", "reaction"],
			"whatsapp_account": ["is", "set"],
		},
		fields=[
			"type",
			"content_type",
			"message",
			"message_type",
			"template",
			"whatsapp_account",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=0,
	)
	unread = cint(frappe.db.get_value(CONTACT, contact, "unread_count"))
	for row in rows:
		account = row.whatsapp_account
		entry = seen.get(account)
		if entry is None:
			entry = seen[account] = {
				"last_message": preview(row),
				"last_message_at": row.creation,
				"last_message_type": row.type or "Outgoing",
				"last_incoming_at": None,
				"unread_count": 0,
			}
		if row.type == "Incoming" and not entry["last_incoming_at"]:
			entry["last_incoming_at"] = row.creation
	if seen and unread:
		latest = max(seen, key=lambda name: seen[name]["last_message_at"])
		seen[latest]["unread_count"] = unread

	frappe.db.delete(ROW, {"parent": contact, "parenttype": CONTACT})
	for account, values in seen.items():
		frappe.get_doc(
			{
				"doctype": ROW,
				"parent": contact,
				"parenttype": CONTACT,
				"parentfield": FIELD,
				"account": account,
				**values,
			}
		).insert(ignore_permissions=True)
	return len(seen)
