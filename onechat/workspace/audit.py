import frappe
from frappe import _
from frappe.utils import add_days, cint, get_fullname, getdate, now_datetime, strip_html

from onechat.workspace.session import is_admin, is_system_manager

CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
NOTE = "OneChat Note"
VERSION = "Version"
TRACKED = ("assigned_to", "conversation_status", "opted_out", "labels")
RANGES = {"today": 0, "7d": 7, "30d": 30, "90d": 90}
MAX_SCAN = 2000

ACTIONS = {
	"Sent message": ("message", None),
	"Sent template": ("message", None),
	"Assigned": ("version", "assigned_to"),
	"Resolved": ("version", "conversation_status"),
	"Reopened": ("version", "conversation_status"),
	"Marked pending": ("version", "conversation_status"),
	"Opted out": ("version", "opted_out"),
	"Opted in": ("version", "opted_out"),
	"Labels changed": ("version", "labels"),
	"Added note": ("note", None),
}


def track(doctype, name, changes):
	changed = [[field, old, new] for field, old, new in changes if (old or None) != (new or None)]
	if not changed:
		return

	try:
		frappe.get_doc(
			{
				"doctype": VERSION,
				"ref_doctype": doctype,
				"docname": name,
				"data": frappe.as_json({"changed": changed, "added": [], "removed": [], "row_changed": []}),
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="OneChat audit")


CATEGORIES = {
	"messages": ["Sent message", "Sent template"],
	"assignments": ["Assigned"],
	"status": ["Resolved", "Reopened", "Marked pending"],
	"consent": ["Opted out", "Opted in"],
	"labels": ["Labels changed"],
	"notes": ["Added note"],
}


def admin_only():
	if not is_system_manager():
		frappe.throw(_("Only System Managers can view the audit log."), frappe.PermissionError)


def since(period):
	return getdate(add_days(now_datetime(), -RANGES[period])) if period in RANGES else None


def bounds(period, from_date=None, to_date=None):
	if period == "custom":
		if not (from_date and to_date):
			return None, None
		return getdate(from_date), add_days(getdate(to_date), 1)
	return since(period), None


def matching_contacts(search):
	pattern = f"%{search}%"
	return frappe.get_all(
		CONTACT,
		or_filters={"contact_name": ["like", pattern], "mobile_no": ["like", pattern]},
		pluck="name",
		limit_page_length=500,
	)


def version_events(field, actor, contacts, start_date, end_date, limit):
	filters = [[VERSION, "ref_doctype", "=", CONTACT]]
	if actor:
		filters.append([VERSION, "owner", "=", actor])
	if contacts is not None:
		filters.append([VERSION, "docname", "in", contacts or [""]])
	if start_date:
		filters.append([VERSION, "creation", ">=", start_date])
	if end_date:
		filters.append([VERSION, "creation", "<", end_date])

	fields = [field] if field else TRACKED
	or_filters = [[VERSION, "data", "like", f'%"{name}"%'] for name in fields]
	rows = frappe.get_all(
		VERSION,
		filters=filters,
		or_filters=or_filters,
		fields=["name", "owner", "docname", "data", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	total = len(
		frappe.get_all(
			VERSION, filters=filters, or_filters=or_filters, pluck="name", limit_page_length=MAX_SCAN
		)
	)

	events = []
	for row in rows:
		for name, old, new in (frappe.parse_json(row.data) or {}).get("changed", []):
			if name not in TRACKED or (field and name != field):
				continue
			event = describe(name, old, new)
			if event:
				events.append(
					{
						**event,
						"key": f"{row.name}-{name}",
						"owner": row.owner,
						"contact": row.docname,
						"at": row.creation,
					}
				)

	return events, total


def describe(field, old, new):
	if field == "assigned_to":
		return {"action": "Assigned", "details": get_fullname(new) if new else _("Unassigned")}
	if field == "conversation_status":
		action = {"Resolved": "Resolved", "Pending": "Marked pending"}.get(new, "Reopened")
		return {"action": action, "details": _("{0} → {1}").format(_(old or "Open"), _(new or "Open"))}
	if field == "opted_out":
		return {"action": "Opted out" if cint(new) else "Opted in", "details": None}
	if field == "labels":
		return {"action": "Labels changed", "details": new or _("No labels")}

	return None


def message_events(action, actor, contacts, start_date, end_date, limit):
	filters = [
		[MESSAGE, "type", "=", "Outgoing"],
		[MESSAGE, "content_type", "!=", "reaction"],
		[MESSAGE, "whatsapp_contact", "is", "set"],
	]
	if action == "Sent template":
		filters.append([MESSAGE, "message_type", "=", "Template"])
	elif action == "Sent message":
		filters.append([MESSAGE, "message_type", "!=", "Template"])
	if actor:
		filters.append([MESSAGE, "owner", "=", actor])
	if contacts is not None:
		filters.append([MESSAGE, "whatsapp_contact", "in", contacts or [""]])
	if start_date:
		filters.append([MESSAGE, "creation", ">=", start_date])
	if end_date:
		filters.append([MESSAGE, "creation", "<", end_date])

	rows = frappe.get_all(
		MESSAGE,
		filters=filters,
		fields=[
			"name",
			"owner",
			"whatsapp_contact",
			"message",
			"message_type",
			"template",
			"bulk_message_reference",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=limit,
	)

	events = []
	for row in rows:
		template = row.message_type == "Template"
		details = row.template if template else strip_html(row.message or "")[:140] or _("Attachment")
		if row.bulk_message_reference:
			details = _("Broadcast {0}: {1}").format(row.bulk_message_reference, details)
		events.append(
			{
				"key": row.name,
				"action": "Sent template" if template else "Sent message",
				"details": details,
				"owner": row.owner,
				"contact": row.whatsapp_contact,
				"at": row.creation,
			}
		)

	return events, frappe.db.count(MESSAGE, filters)


def note_events(actor, contacts, start_date, end_date, limit):
	filters = [[NOTE, "reference_doctype", "=", CONTACT]]
	if actor:
		filters.append([NOTE, "owner", "=", actor])
	if contacts is not None:
		filters.append([NOTE, "reference_docname", "in", contacts or [""]])
	if start_date:
		filters.append([NOTE, "creation", ">=", start_date])
	if end_date:
		filters.append([NOTE, "creation", "<", end_date])

	rows = frappe.get_all(
		NOTE,
		filters=filters,
		fields=["name", "owner", "reference_docname", "content", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)

	events = [
		{
			"key": row.name,
			"action": "Added note",
			"details": strip_html(row.content or "")[:140],
			"owner": row.owner,
			"contact": row.reference_docname,
			"at": row.creation,
		}
		for row in rows
	]

	return events, frappe.db.count(NOTE, filters)


@frappe.whitelist()
def feed(
	action: str | None = None,
	actor: str | None = None,
	contact: str | None = None,
	period: int | str = "30d",
	start: int | str = 0,
	limit: int | str = 20,
	category: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
):
	admin_only()

	return collect(
		action, actor, contact, period, cint(start), min(cint(limit) or 20, 100), category, from_date, to_date
	)


@frappe.whitelist()
def export_feed(
	action: str | None = None,
	actor: str | None = None,
	contact: str | None = None,
	period: int | str = "30d",
	category: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
):
	admin_only()

	return collect(action, actor, contact, period, 0, MAX_SCAN, category, from_date, to_date)["rows"]


def collect(action, actor, contact, period, start, limit, category, from_date=None, to_date=None):
	allowed = CATEGORIES.get(category)
	if allowed and action not in allowed:
		action = None
	if allowed and not action and len(allowed) == 1:
		action = allowed[0]

	window = min(start + limit, MAX_SCAN)
	start_date, end_date = bounds(period, from_date, to_date)
	contacts = matching_contacts(contact.strip()) if contact and contact.strip() else None
	source, field = ACTIONS.get(action or (allowed[0] if allowed else None), (None, None))
	wanted = [action] if action else allowed

	events = []
	total = 0
	if source in (None, "version"):
		rows, count = version_events(field, actor, contacts, start_date, end_date, window)
		if wanted:
			rows = [row for row in rows if row["action"] in wanted]
		events += rows
		total += count
	if source in (None, "message"):
		rows, count = message_events(action, actor, contacts, start_date, end_date, window)
		events += rows
		total += count
	if source in (None, "note"):
		rows, count = note_events(actor, contacts, start_date, end_date, window)
		events += rows
		total += count

	events.sort(key=lambda row: row["at"], reverse=True)
	page = events[start : start + limit]

	people = {}
	names = (
		dict(
			frappe.get_all(
				CONTACT,
				filters={"name": ["in", list({row["contact"] for row in page})]},
				fields=["name", "contact_name"],
				as_list=True,
			)
		)
		if page
		else {}
	)
	for row in page:
		owner = row.pop("owner")
		customer = owner == "Guest" and row["action"] in ("Opted out", "Opted in", "Reopened")
		if owner == "Guest":
			row.update(
				{
					"actor": None,
					"actor_kind": "Customer" if customer else "System",
					"actor_name": _("Customer") if customer else _("System"),
				}
			)
		else:
			if owner not in people:
				people[owner] = (
					frappe.db.get_value("User", owner, ["full_name", "user_image"], as_dict=True) or {}
				)
			row.update(
				{
					"actor": owner,
					"actor_kind": "User",
					"actor_name": people[owner].get("full_name") or owner,
					"actor_image": people[owner].get("user_image"),
				}
			)
		row["contact_name"] = names.get(row["contact"]) or row["contact"]

	return {"rows": page, "total": min(total, MAX_SCAN), "actions": list(ACTIONS)}


@frappe.whitelist()
def people():
	admin_only()

	users = frappe.get_all(
		"OneChat User",
		filters={"enabled": 1},
		fields=["user as value", "full_name as label"],
		order_by="full_name asc",
	)
	return [{"value": row.value, "label": row.label or row.value} for row in users]


CHAT_ACTIVITY_LIMIT = 300


@frappe.whitelist()
def chat_activity(contact: str, start: int | str | None = None):
	if not is_admin():
		frappe.throw(_("Only OneChat admins can see chat activity."), frappe.PermissionError)
	from onechat.inbox.visibility import check as check_visible

	check_visible(contact)
	filters = {"ref_doctype": CONTACT, "docname": contact}
	if start:
		filters["creation"] = [">=", start]
	rows = frappe.get_all(
		VERSION,
		filters=filters,
		fields=["name", "owner", "data", "creation"],
		order_by="creation asc",
		limit_page_length=CHAT_ACTIVITY_LIMIT,
	)
	names = {}
	out = []
	for row in rows:
		for field, old, new in (frappe.parse_json(row.data) or {}).get("changed", []):
			event = describe(field, old, new) if field in TRACKED else None
			if not event:
				continue
			if row.owner not in names:
				names[row.owner] = get_fullname(row.owner)
			out.append(
				{
					"key": f"{row.name}-{field}",
					"action": event["action"],
					"details": event["details"],
					"actor": names[row.owner],
					"creation": str(row.creation),
				}
			)
	return out
