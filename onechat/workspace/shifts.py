import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime

from onechat.api_types import JSON
from onechat.workspace.session import is_admin, require_app_user

AGENT = "OneChat User"
HOURS = "OneChat Business Hour"
LEAVE = "OneChat Leave"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def schedules(users=None):
	filters = {"enabled": 1}
	if users is not None:
		filters["user"] = ["in", list(users) or [""]]
	agents = frappe.get_all(
		AGENT,
		filters=filters,
		fields=["name", "user", "use_shift", "availability", "shift_state", "away_by_shift"],
	)
	names = [row.name for row in agents]
	hours, leaves = {}, {}
	if names:
		for row in frappe.get_all(
			HOURS,
			filters={"parenttype": AGENT, "parentfield": "shifts", "parent": ["in", names]},
			fields=["parent", "weekday", "open_time", "close_time"],
			order_by="idx asc",
		):
			hours.setdefault(row.parent, []).append(row)
		for row in frappe.get_all(
			LEAVE,
			filters={"parenttype": AGENT, "parentfield": "leaves", "parent": ["in", names]},
			fields=["parent", "from_date", "to_date", "reason"],
			order_by="from_date asc",
		):
			leaves.setdefault(row.parent, []).append(row)
	for agent in agents:
		agent.shifts = hours.get(agent.name, [])
		agent.leaves = leaves.get(agent.name, [])
	return agents


def on_leave(agent, day):
	return next((row for row in agent.leaves if getdate(row.from_date) <= day <= getdate(row.to_date)), None)


def working(agent, moment=None):
	from onechat.inbox.routing import is_open, ranges

	moment = moment or now_datetime()
	if on_leave(agent, moment.date()):
		return False
	if not cint(agent.use_shift):
		return True
	return is_open(None, moment, ranges({"business_hours": agent.shifts}))


def working_users(users, moment=None):
	moment = moment or now_datetime()
	return {agent.user for agent in schedules(users) if working(agent, moment)}


def run():
	moment = now_datetime()
	for agent in schedules():
		if not cint(agent.use_shift) and not agent.leaves and not agent.shift_state:
			continue
		state = "On" if working(agent, moment) else "Off"
		if state == agent.shift_state:
			continue
		values = {"shift_state": state}
		if state == "Off" and agent.availability != "Away":
			values.update(availability="Away", away_by_shift=1)
		elif state == "On" and cint(agent.away_by_shift):
			values.update(availability="Available", away_by_shift=0)
		frappe.db.set_value(AGENT, agent.name, values, update_modified=False)
		if "availability" in values:
			frappe.publish_realtime(
				"onechat_availability",
				{"availability": values["availability"], "reason": "schedule"},
				user=agent.user,
				after_commit=True,
			)


def as_time(value):
	text = str(value or "")
	return text[:5] if text else ""


def payload(agent):
	today = now_datetime().date()
	current = on_leave(agent, today)
	return {
		"user": agent.user,
		"use_shift": cint(agent.use_shift),
		"shifts": [
			{
				"weekday": row.weekday,
				"open_time": as_time(row.open_time),
				"close_time": as_time(row.close_time),
			}
			for row in agent.shifts
		],
		"leaves": [
			{"from_date": str(row.from_date), "to_date": str(row.to_date), "reason": row.reason or ""}
			for row in agent.leaves
			if getdate(row.to_date) >= today
		],
		"working_now": working(agent),
		"on_leave": bool(current),
	}


def load(user):
	agent = next(iter(schedules([user])), None)
	if not agent:
		frappe.throw(_("{0} is not an active OneChat member.").format(user))
	return agent


def can_edit(user, whole=True):
	require_app_user()
	if is_admin():
		return
	if whole or user != frappe.session.user:
		frappe.throw(
			_("Only admins can change working hours. You can add your own leave."), frappe.PermissionError
		)


@frappe.whitelist()
def schedule(user: str | None = None):
	user = user or frappe.session.user
	require_app_user()
	if user != frappe.session.user and not is_admin():
		frappe.throw(_("You can only see your own schedule."), frappe.PermissionError)
	return payload(load(user))


@frappe.whitelist()
def team_schedule():
	require_app_user()
	if not is_admin():
		frappe.throw(_("Only admins can see everyone's schedule."), frappe.PermissionError)
	return {agent.user: payload(agent) for agent in schedules()}


def clean_shifts(rows):
	out = []
	for row in frappe.parse_json(rows) or []:
		weekday, start, end = (
			row.get("weekday"),
			as_time(row.get("open_time")),
			as_time(row.get("close_time")),
		)
		if weekday not in WEEKDAYS or not start or not end:
			continue
		if end != "00:00" and end <= start:
			frappe.throw(_("On {0}, the shift must end after it starts.").format(_(weekday)))
		out.append({"weekday": weekday, "open_time": f"{start}:00", "close_time": f"{end}:00"})
	return out


def clean_leaves(rows):
	out = []
	for row in frappe.parse_json(rows) or []:
		if not row.get("from_date") or not row.get("to_date"):
			continue
		start, end = getdate(row["from_date"]), getdate(row["to_date"])
		if end < start:
			frappe.throw(_("Leave must end on or after the day it starts."))
		out.append({"from_date": start, "to_date": end, "reason": (row.get("reason") or "").strip()[:140]})
	return out


@frappe.whitelist(methods=["POST"])
def save_schedule(user: str, use_shift: bool | int | str = 0, shifts: JSON = None, leaves: JSON = None):
	can_edit(user)
	doc = frappe.get_doc(AGENT, load(user).name)
	shift_rows = clean_shifts(shifts)
	if cint(use_shift) and not shift_rows:
		frappe.throw(_("Add at least one working day, or turn working hours off."))
	past = [row for row in doc.leaves if getdate(row.to_date) < now_datetime().date()]
	doc.use_shift = 1 if cint(use_shift) else 0
	doc.set("shifts", shift_rows)
	doc.set(
		"leaves",
		[{"from_date": row.from_date, "to_date": row.to_date, "reason": row.reason} for row in past]
		+ clean_leaves(leaves),
	)
	doc.save(ignore_permissions=True)
	run()
	return payload(load(user))


@frappe.whitelist(methods=["POST"])
def save_leaves(leaves: JSON = None, user: str | None = None):
	user = user or frappe.session.user
	can_edit(user, whole=False)
	doc = frappe.get_doc(AGENT, load(user).name)
	past = [row for row in doc.leaves if getdate(row.to_date) < now_datetime().date()]
	doc.set(
		"leaves",
		[{"from_date": row.from_date, "to_date": row.to_date, "reason": row.reason} for row in past]
		+ clean_leaves(leaves),
	)
	doc.save(ignore_permissions=True)
	run()
	return payload(load(user))
