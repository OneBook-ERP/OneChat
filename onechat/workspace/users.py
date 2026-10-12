import frappe
from frappe import _

from onechat.onechat.doctype.onechat_user.onechat_user import activate
from onechat.workspace.session import is_admin


@frappe.whitelist(methods=["POST"])
def create_user(
	email: str,
	first_name: str | None = None,
	last_name: str | None = None,
	middle_name: str | None = None,
	profile_image: str | None = None,
	enabled: bool = True,
):
	if not is_admin():
		frappe.throw(_("Only OneChat admins can invite people."), frappe.PermissionError)

	existing_user = frappe.db.exists("User", {"email": email})

	if existing_user:
		user_doc = frappe.get_doc("User", existing_user)
		if user_doc.role_profile_name or len(user_doc.get("role_profiles") or []):
			frappe.throw(_("User has a role profile set. Please set the role to OneChat Agent manually."))

		if "OneChat Agent" not in [row.role for row in user_doc.roles]:
			user_doc.append("roles", {"role": "OneChat Agent"})
			user_doc.save(ignore_permissions=True)
		activate(user_doc.name)

		return {"success": True, "message": _("User added to OneChat")}

	user_doc = frappe.new_doc("User")
	user_doc.email = email
	user_doc.first_name = first_name
	user_doc.last_name = last_name
	user_doc.middle_name = middle_name
	user_doc.user_image = profile_image
	user_doc.enabled = enabled
	user_doc.send_welcome_email = 1
	user_doc.append("roles", {"role": "OneChat Agent"})
	user_doc.insert(ignore_permissions=True)

	return {"success": True, "message": _("User added to OneChat")}
