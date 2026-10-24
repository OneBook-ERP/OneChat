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
ROW = "OneChat Contact Account"
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


def inactive_accounts():
	cache = getattr(frappe.local, "onechat_view_filters", None)
	if cache is None:
		cache = frappe.local.onechat_view_filters = {}
	if "inactive" not in cache:
		cache["inactive"] = frappe.get_all(ACCOUNT, filters={"status": "Inactive"}, pluck="name")
	return cache["inactive"]


def hidden(user=None):
	off = set(preference(KEY, all_accounts, user))
	if from_app():
		off |= set(inactive_accounts())
	return sorted(off)


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


def unread_by_account():
	from frappe.query_builder.functions import Sum

	row, contact = frappe.qb.DocType(ROW), frappe.qb.DocType(CONTACT)
	query = (
		frappe.qb.from_(row)
		.join(contact)
		.on((row.parent == contact.name) & (row.parenttype == CONTACT))
		.select(row.account, Sum(row.unread_count).as_("unread"))
		.where((contact.disable == 0) & (row.unread_count > 0))
		.groupby(row.account)
	)
	return {item.account: int(item.unread or 0) for item in query.run(as_dict=True)}


@frappe.whitelist()
def options():
	require_app_user()
	blocked = accounts.blocked()
	off = set(hidden())
	unread = unread_by_account()
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
			"unread": unread.get(row.name, 0),
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


def account_rows(table, names, **where):
	from pypika.terms import ExistsCriterion

	row = frappe.qb.DocType(ROW)
	query = (
		frappe.qb.from_(row)
		.select(row.name)
		.where((row.parent == table.name) & (row.parenttype == CONTACT) & row.account.notin(names))
	)
	if where.get("unread"):
		query = query.where(row.unread_count > 0)
	return ExistsCriterion(query)


def shown_at(table, names):
	from frappe.query_builder.functions import Coalesce, Max

	row = frappe.qb.DocType(ROW)
	latest = (
		frappe.qb.from_(row)
		.select(Max(row.last_message_at))
		.where((row.parent == table.name) & (row.parenttype == CONTACT) & row.account.notin(names))
	)
	return Coalesce(latest, table.last_message_at)


def contact_condition(table, user=None):
	names = hidden(user)
	shown = (excluded(table.whatsapp_account, names) | account_rows(table, names)) if names else None
	names = hidden_teams(user)
	if names:
		part = excluded(table.team, names)
		shown = part if shown is None else shown & part
	return shown


def account_rows_sql(names):
	values = ", ".join(frappe.db.escape(name) for name in names)
	return (
		f"exists (select 1 from `tab{ROW}` ca where ca.parent = `tab{CONTACT}`.name"
		f" and ca.parenttype = {frappe.db.escape(CONTACT)} and ca.account not in ({values}))"
	)


def contact_sql(user=None):
	names = hidden(user)
	accounts = f"({sql(CONTACT, user)} or {account_rows_sql(names)})" if names else ""
	names = hidden_teams(user)
	parts = [accounts, excluded_sql(CONTACT, "team", names) if names else ""]
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
