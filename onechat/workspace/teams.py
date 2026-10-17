import json

import frappe
from frappe import _

from onechat.api_types import JSON
from onechat.workspace.session import require_admin

TEAM = "OneChat Team"
MEMBER = "OneChat Team Member"
AGENT = "OneChat User"
LINKED = (("OneChat Contact", "team"), ("OneChat Conversation", "team"))


ROLE_LABELS = (
	("System Manager", "System Manager"),
	("OneChat Admin", "Admin"),
	("OneChat Manager", "Manager"),
	("OneChat Agent", "Agent"),
)


def agents():
	rows = frappe.get_all(AGENT, fields=["user", "full_name", "profile_image", "availability", "enabled"])
	users = [row.user for row in rows]
	if not users:
		return {}
	active = set(frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="name"))
	roles = {}
	for row in frappe.get_all(
		"Has Role",
		filters={
			"parenttype": "User",
			"parent": ["in", users],
			"role": ["in", [role for role, _label in ROLE_LABELS]],
		},
		fields=["parent", "role"],
	):
		roles.setdefault(row.parent, set()).add(row.role)
	out = {}
	for row in rows:
		held = roles.get(row.user, set())
		if row.user == "Administrator":
			held = held | {"System Manager"}
		role = next((label for name, label in ROLE_LABELS if name in held), None)
		row.role = role
		row.eligible = bool(row.enabled and row.user in active and role)
		row.reason = (
			None
			if row.eligible
			else (
				_("Disabled in OneChat")
				if not row.enabled
				else _("User is disabled")
				if row.user not in active
				else _("No OneChat role")
			)
		)
		out[row.user] = row
	return out


def person(agent, user):
	return {
		"user": user,
		"full_name": agent.get("full_name") or user,
		"image": agent.get("profile_image"),
		"availability": agent.get("availability") or "Available",
		"enabled": 1 if agent.get("enabled") else 0,
		"role": agent.get("role"),
		"eligible": 1 if agent.get("eligible") else 0,
		"reason": agent.get("reason") or (None if agent else _("Not a OneChat member")),
	}


@frappe.whitelist()
def candidates():
	require_admin()
	return sorted(
		(person(agent, user) for user, agent in agents().items() if agent.eligible),
		key=lambda row: row["full_name"].lower(),
	)


@frappe.whitelist()
def teams():
	require_admin()
	people = agents()
	members = {}
	for row in frappe.get_all(
		MEMBER, filters={"parenttype": TEAM}, fields=["parent", "user"], order_by="idx asc"
	):
		members.setdefault(row.parent, []).append(person(people.get(row.user) or {}, row.user))

	numbers = {}
	for row in frappe.get_all(
		"OneChat Team Account",
		filters={"parenttype": TEAM},
		fields=["parent", "whatsapp_account"],
		order_by="idx asc",
	):
		numbers.setdefault(row.parent, []).append(row.whatsapp_account)

	assigned = (
		frappe.db.get_single_value("OneChat Settings", "assign_team")
		if frappe.get_meta("OneChat Settings").has_field("assign_team")
		else None
	)
	return [
		{
			"name": row.name,
			"team_name": row.team_name,
			"description": row.description,
			"members": members.get(row.name, []),
			"auto_assign_target": row.name == assigned,
			"accounts": numbers.get(row.name, []),
			"flows": flows_using(row.name),
		}
		for row in frappe.get_all(TEAM, fields=["name", "team_name", "description"], order_by="team_name asc")
	]


@frappe.whitelist()
def save_team(
	team_name: str,
	description: str | None = None,
	members: JSON = None,
	name: str | None = None,
	accounts: JSON = None,
):
	require_admin()
	team_name = (team_name or "").strip()
	if not team_name:
		frappe.throw(_("Give the team a name."))

	users = [user for user in dict.fromkeys(frappe.parse_json(members) or []) if user]
	people = agents()
	current = (
		set(frappe.get_all(MEMBER, filters={"parenttype": TEAM, "parent": name}, pluck="user"))
		if name
		else set()
	)
	blocked = [
		user for user in users if user not in current and not (people.get(user) and people[user].eligible)
	]
	if blocked:
		frappe.throw(
			_("Only active OneChat members with a OneChat role can join a team: {0}").format(
				", ".join(
					f"{user} ({(people.get(user) or {}).get('reason') or _('Not a OneChat member')})"
					for user in sorted(blocked)
				)
			)
		)

	if name and name != team_name:
		if frappe.db.exists(TEAM, team_name):
			frappe.throw(_("A team called {0} already exists.").format(team_name))
		frappe.rename_doc(TEAM, name, team_name, force=True)
		rename_in_flows(name, team_name)
		name = team_name

	doc = frappe.get_doc(TEAM, name) if name else frappe.new_doc(TEAM)
	if not name and frappe.db.exists(TEAM, team_name):
		frappe.throw(_("A team called {0} already exists.").format(team_name))
	doc.team_name = team_name
	doc.description = description or None
	doc.set("members", [{"user": user} for user in users])
	if accounts is not None:
		numbers = [account for account in dict.fromkeys(frappe.parse_json(accounts) or []) if account]
		missing = [account for account in numbers if not frappe.db.exists("OneChat Account", account)]
		if missing:
			frappe.throw(_("These accounts don't exist: {0}").format(", ".join(missing)))
		doc.set("accounts", [{"whatsapp_account": account} for account in numbers])
	doc.save(ignore_permissions=True)
	return teams()


def rename_in_flows(old, new):
	for flow in frappe.get_all(
		"OneChat Flow", filters={"graph_json": ["like", f"%{old}%"]}, fields=["name", "graph_json"]
	):
		try:
			graph = json.loads(flow.graph_json or "{}")
		except ValueError:
			continue
		changed = False
		for node in graph.get("nodes") or []:
			config = (node.get("data") or {}).get("config") or {}
			if config.get("team") == old:
				config["team"] = new
				changed = True
		if changed:
			frappe.db.set_value(
				"OneChat Flow", flow.name, "graph_json", json.dumps(graph, ensure_ascii=False, indent=2)
			)


def flows_using(team):
	names = []
	for flow in frappe.get_all(
		"OneChat Flow",
		filters={"graph_json": ["like", f"%{team}%"]},
		fields=["name", "flow_name", "graph_json"],
	):
		try:
			nodes = json.loads(flow.graph_json or "{}").get("nodes") or []
		except ValueError:
			continue
		if any(((node.get("data") or {}).get("config") or {}).get("team") == team for node in nodes):
			names.append({"name": flow.name, "label": flow.flow_name or flow.name})
	return names


@frappe.whitelist()
def delete_team(name: str):
	require_admin()
	for doctype, field in LINKED:
		if frappe.get_meta(doctype).has_field(field):
			table = frappe.qb.DocType(doctype)
			frappe.qb.update(table).set(table[field], None).where(table[field] == name).run()
	if (
		frappe.get_meta("OneChat Settings").has_field("assign_team")
		and frappe.db.get_single_value("OneChat Settings", "assign_team") == name
	):
		frappe.db.set_single_value("OneChat Settings", "assign_team", None)
	frappe.delete_doc(TEAM, name, ignore_permissions=True, force=True)
	return teams()
