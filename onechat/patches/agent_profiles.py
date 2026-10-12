import frappe

from onechat.onechat.doctype.onechat_user.onechat_user import AGENT, APP_ROLES, create_agent


def execute():
	holders = set(
		frappe.get_all("Has Role", filters={"parenttype": "User", "role": ["in", APP_ROLES]}, pluck="parent")
	)
	profiles = {row.user: row for row in frappe.get_all(AGENT, fields=["name", "user", "enabled"])}

	for user in holders - set(profiles) - {"Guest"}:
		if frappe.db.exists("User", user):
			create_agent(frappe.get_doc("User", user))

	for user, row in profiles.items():
		if row.enabled and user not in holders and user != "Administrator":
			frappe.db.set_value(AGENT, row.name, "enabled", 0, update_modified=False)
