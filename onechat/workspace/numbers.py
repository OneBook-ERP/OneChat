import json
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.query_builder.functions import IfNull

from onechat.api_types import JSON
from onechat.inbox import accounts
from onechat.workspace.session import is_admin, require_app_user

APP_PATH = "/onechat"
ACCOUNT = "OneChat Account"
CONTACT = "OneChat Contact"
KEY = "onechat_hidden_numbers"
TEAM_KEY = "onechat_hidden_teams"
TEAM = "OneChat Team"
MEMBER = "OneChat Team Member"


def from_app():
	if not getattr(frappe.local, "request", None):
		return False
	path = urlparse(frappe.get_request_header("Referer") or "").path
	return path == APP_PATH or path.startswith(f"{APP_PATH}/")


def preference(key, choices, user=None):
	if not from_app():
		return []
	user = user or frappe.session.user
	cache = getattr(frappe.local, "onechat_view_filters", None)
	if cache is None:
		cache = frappe.local.onechat_view_filters = {}
	if (key, user) not in cache:
		try:
			value = json.loads(frappe.defaults.get_user_default(key, user=user) or "[]")
		except ValueError:
			value = []
		cache[(key, user)] = sorted(set(value) & set(choices(user))) if value else []
	return cache[(key, user)]


def remember(key, names):
	frappe.defaults.set_user_default(key, json.dumps(sorted(names)))
	frappe.local.onechat_view_filters = None


def all_accounts(user=None):
	return frappe.get_all(ACCOUNT, pluck="name")


def hidden(user=None):
	return preference(KEY, all_accounts, user)


def hidden_teams(user=None):
	return preference(TEAM_KEY, my_teams, user)


def excluded(field, names):
	return (IfNull(field, "") == "") | field.notin(names)


def excluded_sql(table_name, column, names):
	field = f"`tab{table_name}`.{column}"
	values = ", ".join(frappe.db.escape(name) for name in names)
	return f"(ifnull({field}, '') = '' or {field} not in ({values}))"


def condition(table, user=None):
	names = hidden(user)
	return excluded(table.whatsapp_account, names) if names else None


def sql(table_name, user=None):
	names = hidden(user)
	return excluded_sql(table_name, "whatsapp_account", names) if names else ""


def template_query(user=None):
	return sql("WhatsApp Templates", user)


def form_query(user=None):
	return sql("WhatsApp Flow", user)


def chat_link_query(user=None):
	return sql("OneChat Chat Link", user)


def broadcast_query(user=None):
	return sql("Bulk WhatsApp Message", user)


@frappe.whitelist()
def options():
	require_app_user()
	blocked = accounts.blocked()
	off = set(hidden())
	filters = {"status": "Active"}
	if blocked:
		filters["name"] = ["not in", list(blocked)]
	rows = frappe.get_all(
		ACCOUNT,
		filters=filters,
		fields=["name", "account_name", "display_phone_number", "channel"],
		order_by="account_name asc",
	)
	return [
		{
			"name": row.name,
			"label": row.account_name or row.name,
			"phone": row.display_phone_number or "",
			"channel": row.channel or "WhatsApp",
			"shown": row.name not in off,
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def save(hidden_numbers: JSON):
	require_app_user()
	names = set(frappe.parse_json(hidden_numbers) or [])
	known = {row["name"] for row in options()}
	names &= known
	if known and names >= known:
		frappe.throw(_("Keep at least one account shown."))
	remember(KEY, names)
	return options()


def my_teams(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or is_admin(user):
		return frappe.get_all(TEAM, pluck="name", order_by="name asc")
	return sorted(
		frappe.get_all(MEMBER, filters={"parenttype": TEAM, "user": user}, pluck="parent", distinct=True)
	)


def contact_condition(table, user=None):
	shown = condition(table, user)
	names = hidden_teams(user)
	if names:
		part = excluded(table.team, names)
		shown = part if shown is None else shown & part
	return shown


def contact_sql(user=None):
	names = hidden_teams(user)
	parts = [sql(CONTACT, user), excluded_sql(CONTACT, "team", names) if names else ""]
	return " and ".join(part for part in parts if part)


@frappe.whitelist()
def team_options():
	require_app_user()
	off = set(hidden_teams())
	return [{"name": name, "label": name, "shown": name not in off} for name in my_teams()]


@frappe.whitelist(methods=["POST"])
def save_teams(hidden: JSON):
	require_app_user()
	known = set(my_teams())
	names = set(frappe.parse_json(hidden) or []) & known
	if known and names >= known:
		frappe.throw(_("Keep at least one team shown."))
	remember(TEAM_KEY, names)
	return team_options()
