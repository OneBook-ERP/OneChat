import frappe
from frappe import _
from frappe.query_builder.functions import IfNull

from onechat.inbox import accounts
from onechat.workspace import numbers
from onechat.workspace.session import can_use_app, is_admin

CONTACT = "OneChat Contact"
SETTINGS = "OneChat Settings"
MEMBER = "OneChat Team Member"
ALL = "All conversations"
TEAM = "Team conversations"
OWN = "Own conversations"
MODES = (ALL, TEAM, OWN)


def mode():
	value = getattr(frappe.local, "onechat_visibility_mode", None)
	if value is None:
		if frappe.get_meta(SETTINGS).has_field("agent_visibility"):
			value = frappe.db.get_single_value(SETTINGS, "agent_visibility")
		value = value if value in MODES else ALL
		frappe.local.onechat_visibility_mode = value
	return value


def restricted(user=None, teams=None):
	user = user or frappe.session.user
	if user in ("Administrator", "Guest") or is_admin(user):
		return False
	return mode() != ALL or bool(accounts.blocked(user, teams))


def teams_of(user):
	return frappe.get_all(
		MEMBER, filters={"parenttype": "OneChat Team", "user": user}, pluck="parent", distinct=True
	)


def rule(user=None, teams=None):
	user = user or frappe.session.user
	if user in ("Administrator", "Guest") or is_admin(user):
		return None
	teams = teams_of(user) if teams is None else teams
	if not restricted(user, teams):
		return None
	return {
		"user": user,
		"teams": teams,
		"team_wide": mode() == TEAM,
		"everyone": mode() == ALL,
		"blocked": sorted(accounts.blocked(user, teams)),
	}


def criterion(table, user=None):
	scope = rule(user)
	if not scope:
		return None
	condition = None
	if not scope["everyone"]:
		teams = scope["teams"]
		unassigned = IfNull(table.assigned_to, "") == ""
		pool = (
			unassigned & ((IfNull(table.team, "") == "") | table.team.isin(teams))
			if teams
			else unassigned & (IfNull(table.team, "") == "")
		)
		condition = (table.assigned_to == scope["user"]) | pool
		if scope["team_wide"] and teams:
			condition = condition | table.team.isin(teams)
	if scope["blocked"]:
		number = (IfNull(table.whatsapp_account, "") == "") | table.whatsapp_account.notin(scope["blocked"])
		condition = number if condition is None else condition & number
	return condition


def shown(table, user=None):
	condition = None
	for part in (criterion(table, user), numbers.contact_condition(table, user)):
		if part is not None:
			condition = part if condition is None else condition & part
	return condition


def allowed(row, user=None, teams=None):
	scope = rule(user, teams)
	if not scope:
		return True
	if not row:
		return False
	if row.get("whatsapp_account") in scope["blocked"]:
		return False
	if scope["everyone"]:
		return True
	assigned, team = row.get("assigned_to"), row.get("team")
	if assigned == scope["user"]:
		return True
	if not assigned and (not team or team in scope["teams"]):
		return True
	return bool(scope["team_wide"] and team and team in scope["teams"])


def can_see(contact, user=None):
	if not rule(user):
		return True
	row = frappe.db.get_value(CONTACT, contact, ["assigned_to", "team", "whatsapp_account"], as_dict=True)
	return allowed(row, user)


def check(contact):
	if contact and not can_see(contact):
		frappe.throw(_("This conversation is assigned to someone else."), frappe.PermissionError)
	if contact:
		from onechat.workspace.session import require_read

		require_read(CONTACT, contact)


def sql_condition(user):
	scope = rule(user)
	if not scope:
		return ""
	table = f"`tab{CONTACT}`"
	conditions = []
	if not scope["everyone"]:
		me = frappe.db.escape(scope["user"])
		teams = ", ".join(frappe.db.escape(team) for team in scope["teams"])
		unassigned = f"ifnull({table}.assigned_to, '') = ''"
		no_team = f"ifnull({table}.team, '') = ''"
		pool = (
			f"({unassigned} and ({no_team} or {table}.team in ({teams})))"
			if teams
			else f"({unassigned} and {no_team})"
		)
		parts = [f"{table}.assigned_to = {me}", pool]
		if scope["team_wide"] and teams:
			parts.append(f"{table}.team in ({teams})")
		conditions.append("(" + " or ".join(parts) + ")")
	if scope["blocked"]:
		numbers = ", ".join(frappe.db.escape(account) for account in scope["blocked"])
		conditions.append(
			f"(ifnull({table}.whatsapp_account, '') = '' or {table}.whatsapp_account not in ({numbers}))"
		)
	return "(" + " and ".join(conditions) + ")"


def contact_query(user=None):
	user = user or frappe.session.user
	return " and ".join(part for part in (sql_condition(user), numbers.contact_sql(user)) if part)


def message_query(user=None):
	condition = contact_query(user)
	if not condition:
		return ""
	return f"`tabOneChat Message`.whatsapp_contact in (select `tab{CONTACT}`.name from `tab{CONTACT}` where {condition})"


def note_query(user=None):
	condition = contact_query(user)
	if not condition:
		return ""
	return (
		f"(ifnull(`tabOneChat Note`.reference_doctype, '') != {frappe.db.escape(CONTACT)}"
		f" or `tabOneChat Note`.reference_docname in (select `tab{CONTACT}`.name from `tab{CONTACT}` where {condition}))"
	)


def contact_permission(doc, ptype=None, user=None, debug=False):
	return not (restricted(user) and not allowed(doc, user))


def message_permission(doc, ptype=None, user=None, debug=False):
	return not (restricted(user) and doc.get("whatsapp_contact") and not can_see(doc.whatsapp_contact, user))


def note_permission(doc, ptype=None, user=None, debug=False):
	return not (
		restricted(user)
		and doc.get("reference_doctype") == CONTACT
		and not can_see(doc.reference_docname, user)
	)


def app_users():
	return frappe.get_all("OneChat User", filters={"enabled": 1}, pluck="user")


def audience(contact):
	row = frappe.db.get_value(CONTACT, contact, ["assigned_to", "team", "whatsapp_account"], as_dict=True)
	if mode() == ALL and not accounts.teams_for((row or {}).get("whatsapp_account")):
		return None, []
	memberships = {}
	for member in frappe.get_all(MEMBER, filters={"parenttype": "OneChat Team"}, fields=["user", "parent"]):
		memberships.setdefault(member.user, []).append(member.parent)
	seeing, hidden = [], []
	for user in app_users():
		if not can_use_app(user):
			continue
		(seeing if allowed(row, user, memberships.get(user, [])) else hidden).append(user)
	return seeing, hidden


def broadcast(event, payload, contact, room, removed=None):
	seeing, hidden = audience(contact)
	if seeing is None:
		frappe.publish_realtime(event, payload, room=room, after_commit=True)
		return
	for user in seeing:
		frappe.publish_realtime(event, payload, user=user, after_commit=True)
	if removed is not None:
		for user in hidden:
			frappe.publish_realtime(event, removed, user=user, after_commit=True)
