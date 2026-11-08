import frappe
from frappe.utils import cint

READ_ONLY = "Read only"
READ_WRITE = "Read and write"
RIGHTS = ("read", "write", "create")
CHECKS = tuple(f"can_{right}" for right in RIGHTS)


def access(user=None):
	from onechat.workspace.session import is_admin

	user = user or frappe.session.user
	meta = frappe.get_meta("OneChat Assistant Role")
	checks = [field for field in CHECKS if meta.has_field(field)]
	rows = frappe.get_all(
		"OneChat Assistant Role",
		filters={"parenttype": "OneChat Settings"},
		fields=["role", "access", *checks],
	)
	if not rows:
		return frozenset(RIGHTS) if is_admin(user) else frozenset({"read"})
	roles = set(frappe.get_roles(user))
	granted = set()
	for row in rows:
		if row.role in roles:
			granted |= rights_of(row, checks)
	if granted & {"write", "create"}:
		granted.add("read")
	return frozenset(granted) or None


def rights_of(row, checks):
	if checks:
		return {right for right in RIGHTS if cint(row.get(f"can_{right}"))}
	return set(RIGHTS) if row.access == READ_WRITE else {"read"}


def per_agent():
	value = frappe.get_cached_doc("OneChat Settings").get("assistant_agent_signin")
	return value is None or bool(cint(value))


def agent_sites():
	from onechat.integrations import connection

	return [row for row in connection.remote_sites() if row.uses_oauth()]


def sign_ins(user):
	if not per_agent():
		return []
	from onechat.integrations import oauth

	return [
		{
			"integration": row.key,
			"label": row.label,
			"signed_in_as": oauth.agent_signed_in(user, row.key) or "",
		}
		for row in agent_sites()
	]


def data_sites():
	from onechat.integrations import connection

	local = [
		key
		for key in connection.APPS
		if not connection.site(key).is_remote() and connection.site(key).ready()
	]
	remote = [row.label for row in connection.remote_sites()]
	return ([frappe.local.site] if local else []) + remote
