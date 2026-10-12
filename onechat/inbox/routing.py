from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import cint, get_datetime, get_datetime_str, get_system_timezone, get_time, now_datetime

from onechat.inbox import accounts
from onechat.inbox.conversations import publish
from onechat.workspace.audit import track
from onechat.workspace.session import can_use_app, require_app_user

SETTINGS = "OneChat Settings"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
AGENT = "OneChat User"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NEW_CONVERSATIONS = "New conversations"
CONVERSATION = "OneChat Conversation"
LEAST_BUSY = "Least busy"
BUSY = ("Open", "Pending")
AVAILABILITY = ("Available", "Away")
IDLE_HOURS = 24


def config():
	return frappe.get_cached_doc(SETTINGS)


def on_message(doc, method=None):
	from onechat.inbox.service import needs_reply

	if doc.type != "Incoming" or not needs_reply(doc) or doc.flags.get("onechat_quiet"):
		return

	contact = doc.get("whatsapp_contact") or (
		doc.reference_name if doc.reference_doctype == CONTACT else None
	)
	if contact:
		route(doc, contact)


def route(doc, contact):
	try:
		settings = config()
	except Exception:
		frappe.log_error(title="OneChat routing: settings")
		return

	handlers = (auto_assign,) if doc.content_type == "comment" else (auto_assign, send_away_message)
	for handler in handlers:
		safely(handler, doc, contact, settings)


def safely(handler, *args):
	frappe.db.savepoint("onechat_routing")
	try:
		handler(*args)
	except Exception:
		frappe.db.rollback(save_point="onechat_routing")
		frappe.log_error(
			title=f"OneChat routing: {handler.__name__}",
			reference_doctype=MESSAGE,
			reference_name=args[0].name,
		)


def auto_assign(doc, contact, settings):
	if not cint(settings.auto_assign):
		return
	if frappe.db.get_value(CONTACT, contact, "assigned_to"):
		return
	if (settings.assign_on or NEW_CONVERSATIONS) == NEW_CONVERSATIONS and not is_new_conversation(
		doc, contact
	):
		return

	row = frappe.db.get_value(CONTACT, contact, ["whatsapp_account", "team"], as_dict=True)
	team = settings.get("assign_team") or row.team
	owners = accounts.teams_for(row.whatsapp_account)
	pool = sorted(owners) if owners and team not in owners else team
	agent = next_agent(settings, pool, contact)
	if not agent:
		return
	if isinstance(pool, list):
		team = next((name for name in pool if agent.user in team_members(name)), None)

	frappe.db.set_value(
		CONTACT,
		contact,
		{"assigned_to": agent.user, **({"team": team} if team else {})},
		update_modified=False,
	)
	track(CONTACT, contact, [("assigned_to", None, agent.user)])
	mark_assigned(agent)
	publish(contact, assigned=True)


def is_new_conversation(doc, contact):
	if doc.flags.get("onechat_reopened"):
		return True

	previous = frappe.get_all(
		MESSAGE,
		filters={
			"whatsapp_contact": contact,
			"type": "Incoming",
			"content_type": ["!=", "reaction"],
			"name": ["!=", doc.name],
			"creation": ["<=", doc.creation],
		},
		fields=["creation"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if not previous:
		return True

	return get_datetime(doc.creation) - get_datetime(previous[0].creation) > timedelta(hours=IDLE_HOURS)


def team_members(team):
	parents = ["in", team] if isinstance(team, list) else team
	return frappe.get_all(
		"OneChat Team Member",
		filters={"parenttype": "OneChat Team", "parent": parents},
		pluck="user",
		distinct=True,
	)


def mark_assigned(agent):
	frappe.db.set_value(AGENT, agent.name, "last_assigned_at", now_datetime(), update_modified=False)


def open_load(users):
	if not users:
		return {}
	contact = frappe.qb.DocType(CONTACT)
	rows = (
		frappe.qb.from_(contact)
		.select(contact.assigned_to, Count("*"))
		.where(
			contact.assigned_to.isin(users) & contact.conversation_status.isin(BUSY) & (contact.disable == 0)
		)
		.groupby(contact.assigned_to)
		.run()
	)
	return {user: cint(count) for user, count in rows}


def previous_agent(contact):
	if not contact:
		return None
	rows = frappe.get_all(
		CONVERSATION,
		filters={"contact": contact, "assigned_to": ["is", "set"]},
		fields=["assigned_to"],
		order_by="opened_at desc",
		limit_page_length=1,
	)
	return rows[0].assigned_to if rows else None


def turn(row):
	return (row.last_assigned_at is not None, row.last_assigned_at or datetime.min, row.full_name or row.user)


def eligible_agents(settings, team=None):
	filters = {"enabled": 1}
	if team:
		filters["user"] = ["in", team_members(team) or [""]]
	rows = frappe.get_all(
		AGENT,
		filters=filters,
		fields=["name", "user", "full_name", "availability", "last_assigned_at"],
	)
	if cint(settings.get("assign_only_available")):
		rows = [row for row in rows if row.availability != "Away"]
	if rows:
		from onechat.workspace.shifts import working_users

		active = set(
			frappe.get_all(
				"User", filters={"name": ["in", [row.user for row in rows]], "enabled": 1}, pluck="name"
			)
		)
		rows = [row for row in rows if row.user in active and can_use_app(row.user)]
		on_duty = working_users([row.user for row in rows])
		rows = [row for row in rows if row.user in on_duty]
	return rows


def next_agent(settings, team=None, contact=None):
	rows = eligible_agents(settings, team)
	if not rows:
		return None

	load = open_load([row.user for row in rows])
	capacity = cint(settings.get("assign_capacity"))
	if capacity > 0:
		rows = [row for row in rows if load.get(row.user, 0) < capacity]
		if not rows:
			return None

	if cint(settings.get("assign_sticky")):
		last = previous_agent(contact)
		match = next((row for row in rows if row.user == last), None)
		if match:
			return match

	if settings.get("assign_method") == LEAST_BUSY:
		return min(rows, key=lambda row: (load.get(row.user, 0), *turn(row)))
	return min(rows, key=turn)


def release(contact):
	if not cint(config().get("assign_release_on_resolve")):
		return
	previous = frappe.db.get_value(CONTACT, contact, "assigned_to")
	if not previous:
		return
	frappe.db.set_value(CONTACT, contact, "assigned_to", None, update_modified=False)
	track(CONTACT, contact, [("assigned_to", previous, None)])


def send_away_message(doc, contact, settings):
	if doc.flags.get("onechat_auto_replied") or doc.flags.get("onechat_flow_handled"):
		return
	if not cint(settings.business_hours_enabled) or is_open(settings, now_datetime()):
		return

	text = (settings.away_message or "").strip()
	if not text:
		return

	cooldown = cint(settings.away_cooldown_hours)
	key = f"onechat:away:{contact}"
	cache = frappe.cache()
	if cooldown > 0:
		if cache.get_value(key):
			return
		cache.set_value(key, 1, expires_in_sec=cooldown * 3600)

	mobile = frappe.db.get_value(CONTACT, contact, "mobile_no") or doc.get("from")
	if not mobile:
		return

	outgoing = frappe.new_doc(MESSAGE)
	outgoing.update(
		{
			"type": "Outgoing",
			"message_type": "Manual",
			"source": "Away message",
			"content_type": "text",
			"message": text,
			"to": mobile,
			"reference_doctype": CONTACT,
			"reference_name": contact,
			"whatsapp_account": doc.get("whatsapp_account"),
		}
	)
	outgoing.insert(ignore_permissions=True)


def minutes(value):
	moment = get_time(value)
	return moment.hour * 60 + moment.minute


def ranges(settings):
	days = {}
	for row in settings.get("business_hours") or []:
		if row.weekday not in WEEKDAYS or not row.open_time or not row.close_time:
			continue
		start, end = minutes(row.open_time), minutes(row.close_time) or 1440
		if end > start:
			days.setdefault(WEEKDAYS.index(row.weekday), []).append((start, end))

	return days


def is_open(settings, moment, days=None):
	days = ranges(settings) if days is None else days
	current = moment.hour * 60 + moment.minute

	return any(start <= current < end for start, end in days.get(moment.weekday(), []))


def next_change(settings, moment):
	days = ranges(settings)
	if not days:
		return None

	current = is_open(settings, moment, days)
	midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
	boundaries = sorted(
		{
			midnight + timedelta(days=offset, minutes=value)
			for offset in range(8)
			for start, end in days.get((moment.weekday() + offset) % 7, [])
			for value in (start, end)
		}
	)
	for boundary in boundaries:
		if boundary > moment and is_open(settings, boundary, days) != current:
			return boundary

	return None


@frappe.whitelist()
def status():
	if not can_use_app():
		frappe.throw(_("You do not have access to OneChat."), frappe.PermissionError)

	settings = config()
	enabled = bool(cint(settings.business_hours_enabled))
	moment = now_datetime()
	change = next_change(settings, moment) if enabled else None

	return {
		"business_hours_enabled": enabled,
		"open_now": is_open(settings, moment) if enabled else True,
		"next_change": get_datetime_str(change) if change else None,
		"timezone": get_system_timezone(),
		"now": get_datetime_str(moment),
	}


@frappe.whitelist(methods=["POST"])
def set_availability(status: str):
	require_app_user()
	if status not in AVAILABILITY:
		frappe.throw(_("Choose Available or Away."))

	name = frappe.db.get_value(AGENT, {"user": frappe.session.user})
	if not name:
		frappe.throw(_("You are not a OneChat member."), frappe.PermissionError)

	frappe.db.set_value(AGENT, name, "availability", status)

	return status
