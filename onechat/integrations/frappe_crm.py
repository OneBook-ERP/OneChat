import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import flt, fmt_money, formatdate, get_fullname, strip_html

from onechat import integrations
from onechat.integrations import connection, links
from onechat.integrations.phone import frappe_phone

CRM = connection.site("crm")
LEAD = "CRM Lead"
DEAL = "CRM Deal"
NOTE = "FCRM Note"
TASK = "CRM Task"
MESSAGE = "OneChat Message"
CONTACT = "OneChat Contact"
CRM_REFERENCES = (LEAD, DEAL, "Contact")
ROUTES = {LEAD: "leads", DEAL: "deals", "CRM Organization": "organizations", "Contact": "contacts"}

THEMES = {
	"New": "gray",
	"Contacted": "blue",
	"Nurture": "amber",
	"Qualified": "green",
	"Unqualified": "red",
	"Junk": "red",
	"Qualification": "gray",
	"Demo/Making": "blue",
	"Proposal/Quotation": "blue",
	"Negotiation": "amber",
	"Ready to Close": "green",
	"Won": "green",
	"Lost": "red",
	"Backlog": "gray",
	"Todo": "blue",
	"In Progress": "amber",
	"Done": "green",
	"Canceled": "gray",
}


def spec():
	return {
		"name": "crm",
		"label": "Frappe CRM",
		"app": "crm",
		"ready": "onechat.integrations.frappe_crm.ready",
		"setup": "crm",
		"sites_help": _(
			"On this site Frappe CRM's WhatsApp tab and the OneChat inbox share the same chats. On another site OneChat connects over the Frappe REST API with Sign in (OAuth) or an API key; keep WhatsApp off in CRM there so chats don't arrive twice."
		),
		"icon": "lucide-handshake",
		"logo": "/assets/onechat/images/integrations/frappe-crm.svg",
		"category": _("CRM"),
		"docs_url": "https://docs.frappe.io/crm",
		"description": _(
			"Link WhatsApp chats to Frappe CRM leads and deals, see their status, notes and tasks, and turn chats into deals."
		),
		"features": [
			_("Match new chats to deals and leads by phone number"),
			_("See deal value, stage, notes and open tasks beside the conversation"),
			_("Create a lead from a chat and convert it to a deal in one click"),
			_("Start flows when a lead or deal is created or changes stage"),
		],
		"link_doctypes": [
			{
				"doctype": DEAL,
				"label": _("CRM deals"),
				"icon": "lucide-handshake",
				"theme": "green",
				"route": "/crm/deals/{name}",
			},
			{
				"doctype": LEAD,
				"label": _("CRM leads"),
				"icon": "lucide-user-round-plus",
				"theme": "blue",
				"route": "/crm/leads/{name}",
			},
		],
		"find_by_phone": "onechat.integrations.frappe_crm.find_by_phone",
		"find_all_by_phone": "onechat.integrations.frappe_crm.find_all_by_phone",
		"on_link": "onechat.integrations.frappe_crm.claim",
		"cards": "onechat.integrations.frappe_crm.cards",
		"stats": "onechat.integrations.frappe_crm.stats",
		"timeline": "onechat.integrations.frappe_crm.timeline",
		"actions": [
			{
				"key": "create_lead",
				"needs": [("CRM Lead", "create")],
				"label": _("Create CRM lead"),
				"icon": "lucide-user-round-plus",
				"method": "onechat.integrations.frappe_crm.create_lead",
				"condition": "onechat.integrations.frappe_crm.unlinked",
			},
			{
				"key": "convert_to_deal",
				"needs": [("CRM Deal", "create")],
				"label": _("Convert to CRM deal"),
				"icon": "lucide-handshake",
				"method": "onechat.integrations.frappe_crm.convert_to_deal",
				"condition": "onechat.integrations.frappe_crm.open_lead",
			},
		],
	}


def ready():
	return CRM.ready()


def route(doctype, name=None):
	path = f"/crm/{ROUTES.get(doctype, 'leads')}"
	if name:
		path += f"/{name}"
	return CRM.url(path)


def loose(wa_number):
	return "%" + "%".join(wa_number[-10:])


def find_by_phone(wa_number):
	source = CRM.source()
	pattern = loose(wa_number)

	deals = source.get_list(
		DEAL, fields=["name"], filters={"mobile_no": ["like", pattern]}, order_by="modified desc", limit=1
	)
	if deals:
		return DEAL, deals[0].name

	contacts = source.get_list(
		"Contact", fields=["name"], filters=[["Contact Phone", "phone", "like", pattern]], limit=3
	)
	for contact in contacts:
		deals = source.get_list(
			DEAL,
			fields=["name"],
			filters=[["CRM Contacts", "contact", "=", contact.name]],
			order_by="modified desc",
			limit=1,
		)
		if deals:
			return DEAL, deals[0].name

	leads = source.get_list(
		LEAD,
		fields=["name"],
		filters={"converted": 0},
		or_filters={"mobile_no": ["like", pattern], "phone": ["like", pattern]},
		order_by="modified desc",
		limit=1,
	)
	if leads:
		return LEAD, leads[0].name

	return None


MATCH_LIMIT = 10
FORM_SCRIPT = "CRM Form Script"
SCRIPT_NAMES = {LEAD: "OneChat WhatsApp - Lead", DEAL: "OneChat WhatsApp - Deal"}


def chat_script(doctype):
	from frappe.utils import get_url

	base = get_url("/onechat/open")
	return (
		"function setupForm({ doc }) {\n"
		"  return {\n"
		"    actions: [\n"
		"      {\n"
		"        label: 'Chat on WhatsApp',\n"
		f"        onClick: () => window.open('{base}?doctype=' + encodeURIComponent('{doctype}') + '&name=' + encodeURIComponent(doc.name), '_blank'),\n"
		"      },\n"
		"    ],\n"
		"  }\n"
		"}\n"
	)


@frappe.whitelist(methods=["POST"])
def install_chat_button():
	from onechat.workspace.session import require_admin

	require_admin()
	source = CRM.source()
	if not source.has_doctype(FORM_SCRIPT):
		frappe.throw(_("This Frappe CRM version has no Form Scripts, so OneChat can't add the button."))
	for doctype, name in SCRIPT_NAMES.items():
		values = {"dt": doctype, "view": "Form", "enabled": 1, "script": chat_script(doctype)}
		try:
			if source.exists(FORM_SCRIPT, name):
				source.update(FORM_SCRIPT, name, values)
			else:
				source.insert({"doctype": FORM_SCRIPT, "name": name, **values})
		except frappe.PermissionError as error:
			frappe.throw(
				_(
					"Frappe CRM refused to save the Form Script. Sign in with a System Manager account. {0}"
				).format(str(error))
			)
	return _("Added Chat on WhatsApp to CRM leads and deals")


def find_all_by_phone(wa_number):
	source = CRM.source()
	pattern = loose(wa_number)
	found = [
		(DEAL, row.name)
		for row in source.get_list(
			DEAL,
			fields=["name"],
			filters={"mobile_no": ["like", pattern]},
			order_by="modified desc",
			limit=MATCH_LIMIT,
		)
	]

	for contact in source.get_list(
		"Contact", fields=["name"], filters=[["Contact Phone", "phone", "like", pattern]], limit=5
	):
		found += [
			(DEAL, row.name)
			for row in source.get_list(
				DEAL,
				fields=["name"],
				filters=[["CRM Contacts", "contact", "=", contact.name]],
				order_by="modified desc",
				limit=MATCH_LIMIT,
			)
		]

	found += [
		(LEAD, row.name)
		for row in source.get_list(
			LEAD,
			fields=["name"],
			or_filters={"mobile_no": ["like", pattern], "phone": ["like", pattern]},
			order_by="converted asc, modified desc",
			limit=MATCH_LIMIT,
		)
	]
	return list(dict.fromkeys(found))[:MATCH_LIMIT]


def shared():
	return not CRM.is_remote() and CRM.installed_here() and "crm" not in integrations.disabled()


def claim(contact, doctype, name):
	if doctype not in (LEAD, DEAL) or not shared():
		return

	message = frappe.qb.DocType(MESSAGE)
	(
		frappe.qb.update(message)
		.set(message.reference_doctype, doctype)
		.set(message.reference_name, name)
		.where(
			(message.whatsapp_contact == contact) & IfNull(message.reference_doctype, "").isin(["", CONTACT])
		)
	).run()


def on_message(doc, contact):
	if doc.reference_doctype not in CRM_REFERENCES or not shared():
		return

	if doc.type == "Outgoing" and not doc.get("source") and frappe.session.user != "Guest":
		doc.source = "Agent"
		frappe.db.set_value(MESSAGE, doc.name, "source", "Agent", update_modified=False)
		from onechat.automation.engine import stop_for_agent

		stop_for_agent(contact)

	if doc.reference_doctype in (LEAD, DEAL) and not links.has(
		contact, doc.reference_doctype, doc.reference_name
	):
		links.add(contact, doc.reference_doctype, doc.reference_name)
		claim(contact, doc.reference_doctype, doc.reference_name)


def theme(status):
	return THEMES.get(status, "gray")


def person(user):
	return get_fullname(user) if user and not CRM.is_remote() else user


def field_rows(doc, fields):
	return [{"label": label, "value": value} for label, value in fields if value not in (None, "", 0)]


def cards(doctype, name):
	if doctype not in (LEAD, DEAL):
		return []

	source = CRM.source()
	doc = source.get_doc(doctype, name)
	if doctype == DEAL:
		value = doc.get("deal_value") or doc.get("annual_revenue")
		summary = {
			"title": _("CRM deal"),
			"icon": "lucide-handshake",
			"url": route(DEAL, name),
			"fields": field_rows(
				doc,
				[
					(_("Stage"), doc.get("status")),
					(_("Value"), fmt_money(flt(value), currency=doc.get("currency")) if flt(value) else None),
					(
						_("Probability"),
						f"{flt(doc.get('probability')):g}%" if flt(doc.get("probability")) else None,
					),
					(
						_("Expected close"),
						formatdate(doc.get("expected_closure_date"))
						if doc.get("expected_closure_date")
						else None,
					),
					(_("Organization"), doc.get("organization")),
					(_("Owner"), person(doc.get("deal_owner"))),
				],
			),
		}
	else:
		full_name = " ".join(
			[part for part in [doc.get("first_name"), doc.get("last_name")] if part]
		) or doc.get("lead_name")
		summary = {
			"title": _("CRM lead"),
			"icon": "lucide-user-round-plus",
			"url": route(LEAD, name),
			"fields": field_rows(
				doc,
				[
					(_("Name"), full_name),
					(_("Status"), doc.get("status")),
					(_("Organization"), doc.get("organization")),
					(_("Source"), doc.get("source")),
					(_("Email"), doc.get("email")),
					(_("Owner"), person(doc.get("lead_owner"))),
					(_("Converted"), _("Yes") if doc.get("converted") else None),
				],
			),
		}

	return [summary, tasks_card(source, doctype, name), notes_card(source, doctype, name)]


def tasks_card(source, doctype, name):
	rows = source.get_list(
		TASK,
		fields=["name", "title", "status", "priority", "due_date", "assigned_to"],
		filters={
			"reference_doctype": doctype,
			"reference_docname": name,
			"status": ["not in", ["Done", "Canceled"]],
		},
		order_by="due_date asc",
		limit=5,
	)
	return {
		"title": _("Open tasks"),
		"icon": "lucide-list-todo",
		"rows": [
			{
				"title": row.title or row.name,
				"subtitle": " · ".join(
					[
						part
						for part in [
							formatdate(row.due_date) if row.due_date else None,
							row.priority,
							person(row.assigned_to),
						]
						if part
					]
				),
				"status": row.status,
				"theme": theme(row.status),
				"url": route(doctype, name) + "#tasks",
				"doctype": TASK,
				"name": row.name,
			}
			for row in rows
		],
		"empty": _("No open tasks"),
		"url": route(doctype, name) + "#tasks",
	}


def notes_card(source, doctype, name):
	rows = source.get_list(
		NOTE,
		fields=["name", "title", "content", "modified", "owner"],
		filters={"reference_doctype": doctype, "reference_docname": name},
		order_by="modified desc",
		limit=3,
	)
	return {
		"title": _("Recent notes"),
		"icon": "lucide-notebook-pen",
		"rows": [
			{
				"title": row.title or _("Note"),
				"subtitle": " · ".join(
					[part for part in [formatdate(row.modified), strip_html(row.content or "")[:80]] if part]
				),
				"url": route(doctype, name) + "#notes",
				"doctype": NOTE,
				"name": row.name,
			}
			for row in rows
		],
		"empty": _("No notes yet"),
		"url": route(doctype, name) + "#notes",
	}


def unlinked(contact):
	return not contact.reference_docname


def open_lead(contact):
	if contact.reference_doctype != LEAD or not contact.reference_docname:
		return False
	return not CRM.source().get_value(LEAD, contact.reference_docname, "converted")


def create_lead(contact):
	source = CRM.source()
	name = (contact.contact_name or contact.mobile_no or "").strip()
	parts = name.split(" ", 1)
	first, last = parts[0], parts[1] if len(parts) > 1 else ""
	values = {
		"doctype": LEAD,
		"first_name": first or contact.mobile_no,
		"last_name": last or None,
		"mobile_no": frappe_phone(contact.mobile_no),
		"email": contact.email,
	}
	if source.exists("CRM Lead Source", "WhatsApp"):
		values["source"] = "WhatsApp"
	lead = source.insert(values)

	return LEAD, lead.name


def convert_to_deal(contact):
	result = CRM.source().call(
		"crm.fcrm.doctype.crm_lead.crm_lead.convert_to_deal", lead=contact.reference_docname
	)
	deal = result.get("name") if isinstance(result, dict) else result
	if not deal:
		frappe.throw(_("Frappe CRM did not return the new deal."))

	return DEAL, deal


def stats(doctype, name):
	if doctype not in (LEAD, DEAL):
		return []
	doc = CRM.source().get_doc(doctype, name)
	if doctype == DEAL:
		value = doc.get("deal_value") or doc.get("annual_revenue")
		return [
			{
				"key": "deal_stage",
				"label": _("Deal stage"),
				"value": doc.get("status"),
				"theme": theme(doc.get("status")),
			},
			{
				"key": "deal_value",
				"label": _("Deal value"),
				"value": fmt_money(flt(value), currency=doc.get("currency")) if flt(value) else None,
			},
			{
				"key": "probability",
				"label": _("Probability"),
				"value": f"{flt(doc.get('probability')):g}%" if flt(doc.get("probability")) else None,
			},
		]
	return [
		{
			"key": "lead_status",
			"label": _("Lead status"),
			"value": doc.get("status"),
			"theme": theme(doc.get("status")),
		},
		{"key": "lead_source", "label": _("Source"), "value": doc.get("source")},
	]


def timeline(doctype, name, before=None, limit=30):
	if doctype not in (LEAD, DEAL):
		return []
	source = CRM.source()
	out = []
	doc = source.get_value(doctype, name, ["name", "creation", "status"])
	if doc and (not before or str(doc.get("creation")) < before):
		out.append(
			{
				"id": f"{doctype}:{name}",
				"at": str(doc.get("creation")),
				"title": _("CRM deal created") if doctype == DEAL else _("Became a CRM lead"),
				"status": doc.get("status"),
				"theme": theme(doc.get("status")),
				"url": route(doctype, name),
				"icon": "lucide-handshake" if doctype == DEAL else "lucide-user-round-plus",
			}
		)
	filters = {"reference_doctype": doctype, "reference_docname": name}
	if before:
		filters["creation"] = ["<", before]
	for row in source.get_list(
		TASK,
		fields=["name", "creation", "title", "status"],
		filters=filters,
		order_by="creation desc",
		limit=limit,
	):
		out.append(
			{
				"id": f"task:{row.name}",
				"at": str(row.creation),
				"title": _("Task: {0}").format(row.title or row.name),
				"status": row.status,
				"theme": theme(row.status),
				"url": route(doctype, name) + "#tasks",
				"icon": "lucide-list-todo",
			}
		)
	return out


def won(status):
	if not status:
		return False
	if status == "Won":
		return True
	try:
		return CRM.source().get_value("CRM Deal Status", status, "type") == "Won"
	except Exception:
		return False


def deal_update(doc, method=None):
	if not shared() or not doc.has_value_changed("status") or not won(doc.status):
		return
	queue_hand_off(doc.name)


def remote_deal(name, doc):
	if won(doc.get("status")):
		queue_hand_off(name)


def queue_hand_off(deal):
	if not integrations.find("erpnext") or not links.contacts_for(DEAL, deal):
		return
	frappe.enqueue(
		"onechat.integrations.frappe_crm.hand_off",
		queue="short",
		job_id=f"onechat_deal_won_{deal}",
		deduplicate=True,
		enqueue_after_commit=True,
		deal=deal,
	)


def hand_off(deal):
	from onechat.inbox.conversations import publish
	from onechat.integrations.erpnext import create_customer

	erp = integrations.find("erpnext")
	if not erp:
		return
	create = integrations.setting("create_customer_on_win")
	for contact in links.contacts_for(DEAL, deal):
		current = links.get(contact, "erpnext")
		if current and current.doctype == "Customer":
			continue
		doc = frappe.get_doc(CONTACT, contact)
		if current:
			match = (current.doctype, current.name)
		else:
			match = integrations.run(erp.get("find_by_phone"), doc.wa_number) if doc.wa_number else None
		if create and (not match or match[0] != "Customer"):
			view = links.view(doc, "erpnext")
			if match:
				view.reference_doctype, view.reference_docname = match
			match = create_customer(view, ignore_permissions=True)
		if match and (not current or tuple(match) != (current.doctype, current.name)):
			links.add(contact, match[0], match[1], main=True)
			integrations.linked(contact, match[0], match[1])
			publish(contact)
