import frappe
from frappe import _

from onechat.workspace.session import is_admin

ACCOUNT = "OneChat Account"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
TEAM = "OneChat Team"
TEAM_ACCOUNT = "OneChat Team Account"
MEMBER = "OneChat Team Member"
SETTINGS = "WhatsApp Settings"


def restricted():
	value = getattr(frappe.local, "onechat_account_teams", None)
	if value is None:
		value = {}
		if frappe.db.table_exists(TEAM_ACCOUNT):
			for row in frappe.get_all(
				TEAM_ACCOUNT, filters={"parenttype": TEAM}, fields=["parent", "whatsapp_account"]
			):
				value.setdefault(row.whatsapp_account, set()).add(row.parent)
		frappe.local.onechat_account_teams = value
	return value


def teams_for(account):
	return restricted().get(account) or set()


def unrestricted(user):
	return user in ("Administrator", "Guest") or is_admin(user)


def blocked(user=None, teams=None):
	user = user or frappe.session.user
	accounts = restricted()
	if not accounts or unrestricted(user):
		return set()
	if teams is None:
		teams = frappe.get_all(
			MEMBER, filters={"parenttype": TEAM, "user": user}, pluck="parent", distinct=True
		)
	mine = set(teams)
	return {account for account, owners in accounts.items() if not owners & mine}


def can_use(account, user=None, teams=None):
	return not account or account not in blocked(user, teams)


def allowed_users(account):
	owners = teams_for(account)
	if not owners:
		return None
	return set(
		frappe.get_all(MEMBER, filters={"parenttype": TEAM, "parent": ["in", list(owners)]}, pluck="user")
	)


def default_outgoing():
	return frappe.db.get_value(ACCOUNT, {"is_default_outgoing": 1, "status": ["!=", "Inactive"]}, "name")


def account_for(contact):
	return frappe.db.get_value(CONTACT, contact, "whatsapp_account") or default_outgoing()


def allow(account):
	if not can_use(account):
		frappe.throw(
			_(
				"Your team can't send from the account {0}. Ask an admin to add you to a team that has it."
			).format(frappe.bold(account)),
			frappe.PermissionError,
		)
	return account


def check(contact):
	return allow(account_for(contact))


def pick(contact, account=None):
	if not account:
		return check(contact)
	row = frappe.db.get_value(ACCOUNT, account, ["status", "channel"], as_dict=True)
	if not row:
		frappe.throw(_("Account {0} does not exist.").format(account))
	if row.status == "Inactive":
		frappe.throw(_("Account {0} is inactive. Activate it in Settings to send messages.").format(account))
	require_whatsapp(account)
	return allow(account)


@frappe.whitelist()
def choices(contact: str):
	from onechat.inbox.visibility import check as check_visible
	from onechat.workspace import numbers

	check_visible(contact)
	current = frappe.db.get_value(CONTACT, contact, "whatsapp_account")
	off = blocked() | set(numbers.hidden())
	rows = [
		row
		for row in frappe.get_all(
			ACCOUNT,
			filters={"status": "Active", "channel": ["!=", "Instagram"]},
			fields=["name", "account_name", "display_phone_number", "is_default_outgoing"],
			order_by="account_name asc",
		)
		if row.name not in off
	]
	from onechat.inbox import contact_accounts

	names = [row.name for row in rows]
	ready = sorted(
		(
			row
			for row in contact_accounts.rows_of(contact)
			if row.account in names and contact_accounts.window_open(row)
		),
		key=lambda row: row.last_incoming_at,
		reverse=True,
	)
	open_names = [row.account for row in ready]
	selected = (
		current
		if current in names
		else open_names[0]
		if open_names
		else next((row.name for row in rows if row.is_default_outgoing), names[0] if names else None)
	)
	return {
		"current": current,
		"selected": selected,
		"accounts": [
			{
				"name": row.name,
				"label": row.account_name or row.name,
				"phone": row.display_phone_number or "",
				"window_open": row.name in open_names,
			}
			for row in rows
		],
	}


def contact_of(doc):
	if doc.get("whatsapp_contact"):
		return doc.whatsapp_contact
	return doc.reference_name if doc.get("reference_doctype") == CONTACT else None


def default_team():
	if not frappe.get_meta(SETTINGS).has_field("default_team"):
		return None
	return frappe.db.get_single_value(SETTINGS, "default_team")


def team_for(account):
	owners = teams_for(account)
	if len(owners) == 1:
		return next(iter(owners))
	fallback = default_team()
	if fallback and (not owners or fallback in owners):
		return fallback
	return None


def on_message(doc, method=None):
	contact, account = contact_of(doc), doc.get("whatsapp_account")
	if not contact or not frappe.db.exists(CONTACT, contact):
		return
	row = frappe.db.get_value(CONTACT, contact, ["whatsapp_account", "team"], as_dict=True)
	updates = {}
	if account and row.whatsapp_account != account and (not row.whatsapp_account or doc.type == "Incoming"):
		updates["whatsapp_account"] = account
	if not row.team and doc.type == "Incoming":
		team = team_for(updates.get("whatsapp_account") or row.whatsapp_account)
		if team:
			updates["team"] = team
	if updates:
		frappe.db.set_value(CONTACT, contact, updates, update_modified=False)


@frappe.whitelist()
def options():
	from onechat.workspace.session import require_admin

	require_admin()
	owners = restricted()
	return [
		{
			"value": row.name,
			"label": row.account_name or row.name,
			"number": row.display_phone_number or "",
			"teams": sorted(owners.get(row.name) or []),
		}
		for row in frappe.get_all(
			ACCOUNT, fields=["name", "account_name", "display_phone_number"], order_by="account_name asc"
		)
	]


def require_whatsapp(account):
	if account and frappe.db.get_value(ACCOUNT, account, "channel") == "Instagram":
		frappe.throw(_("{0} is an Instagram account. This only works with WhatsApp numbers.").format(account))
