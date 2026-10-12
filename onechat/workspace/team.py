import frappe
from frappe import _
from frappe.utils import cint

from onechat.onechat.doctype.onechat_user.onechat_user import AGENT, has_app_role
from onechat.workspace.session import can_use_app, is_admin

ADMIN_ROLE = "OneChat Admin"
AGENT_ROLE = "OneChat Agent"


def ensure_admin():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can manage the team."), frappe.PermissionError)


@frappe.whitelist()
def members():
	ensure_admin()

	rows = frappe.get_all(
		"OneChat User",
		fields=["name", "user", "full_name", "profile_image", "enabled", "availability"],
		order_by="full_name asc",
	)
	users = [row.user for row in rows]
	if not users:
		return []

	details = {
		row.name: row
		for row in frappe.get_all(
			"User",
			filters={"name": ["in", users]},
			fields=["name", "full_name", "user_image", "enabled"],
		)
	}
	roles = frappe.get_all(
		"Has Role",
		filters={
			"parenttype": "User",
			"parent": ["in", users],
			"role": ["in", [ADMIN_ROLE, "System Manager"]],
		},
		fields=["parent", "role"],
	)
	admins = {row.parent for row in roles if row.role == ADMIN_ROLE}
	managers = {row.parent for row in roles if row.role == "System Manager"}

	out = []
	for row in rows:
		user = details.get(row.user) or {}
		out.append(
			{
				"name": row.name,
				"user": row.user,
				"full_name": row.full_name or user.get("full_name") or row.user,
				"image": row.profile_image or user.get("user_image"),
				"enabled": cint(row.enabled),
				"availability": row.availability or "Available",
				"user_enabled": cint(user.get("enabled")),
				"is_admin": row.user in admins or row.user == "Administrator",
				"is_system_manager": row.user in managers or row.user == "Administrator",
			}
		)

	return out


@frappe.whitelist(methods=["POST"])
def set_admin(user: str, admin: int):
	ensure_admin()

	admin = cint(admin)
	if user == frappe.session.user and not admin:
		frappe.throw(_("You cannot remove your own admin access."))
	if not frappe.db.exists("OneChat User", {"user": user}):
		frappe.throw(_("{0} is not a OneChat member.").format(user))

	if admin:
		if not frappe.db.exists("Has Role", {"parenttype": "User", "parent": user, "role": ADMIN_ROLE}):
			row = frappe.new_doc("Has Role")
			row.parent = user
			row.parenttype = "User"
			row.parentfield = "roles"
			row.role = ADMIN_ROLE
			row.insert(ignore_permissions=True)
	else:
		frappe.db.delete("Has Role", {"parenttype": "User", "parent": user, "role": ADMIN_ROLE})

	frappe.clear_cache(user=user)

	return {"user": user, "is_admin": bool(admin)}


@frappe.whitelist(methods=["POST"])
def set_active(user: str, active: int):
	ensure_admin()

	active = cint(active)
	if user == frappe.session.user and not active:
		frappe.throw(_("You cannot turn yourself off."))
	name = frappe.db.get_value(AGENT, {"user": user})
	if not name:
		frappe.throw(_("{0} is not a OneChat member.").format(user))

	if active:
		user_doc = frappe.get_doc("User", user)
		if not has_app_role(user_doc):
			if user_doc.role_profile_name or user_doc.get("role_profiles"):
				frappe.throw(
					_("{0} has a role profile. Add the OneChat Agent role to that profile instead.").format(
						user
					)
				)
			user_doc.flags.ignore_permissions = True
			user_doc.add_roles(AGENT_ROLE)
	frappe.db.set_value(AGENT, name, "enabled", active)
	if not active and not can_use_app(user):
		frappe.publish_realtime("onechat_access", {"active": 0}, user=user, after_commit=True)

	return {"user": user, "enabled": active}
