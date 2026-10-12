import frappe
from frappe.model.document import Document

AGENT = "OneChat User"
APP_ROLES = ("OneChat Agent", "OneChat Admin", "OneChat Manager")


class OneChatUser(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		availability: DF.Literal["Available", "Away"]
		enabled: DF.Check
		first_name: DF.Data | None
		full_name: DF.Data | None
		last_assigned_at: DF.Datetime | None
		last_name: DF.Data | None
		middle_name: DF.Data | None
		profile_image: DF.AttachImage | None
		user: DF.Link
		user_owner: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.set_full_name()

	def before_insert(self):
		self.user_owner = frappe.session.user

	def after_delete(self):
		if self.user:
			user = frappe.get_doc("User", self.user)
			user.flags.ignore_permissions = True
			user.flags.deleting_onechat_user = True
			user.remove_roles("OneChat Agent")
			user.save()

	def set_full_name(self):
		if self.first_name:
			self.full_name = " ".join(
				[
					part
					for part in [
						self.first_name,
						self.middle_name,
						self.last_name,
					]
					if part
				]
			)


def has_app_role(user_doc):
	return user_doc.name == "Administrator" or any(
		row.role in APP_ROLES for row in user_doc.get("roles") or []
	)


def create_agent(user_doc):
	agent = frappe.new_doc(AGENT)
	agent.user = user_doc.name
	agent.first_name = user_doc.first_name
	agent.middle_name = user_doc.middle_name
	agent.last_name = user_doc.last_name
	agent.full_name = user_doc.full_name or user_doc.first_name or user_doc.name
	agent.profile_image = user_doc.user_image
	agent.enabled = 1 if user_doc.enabled else 0
	agent.insert(ignore_permissions=True)
	return agent


def activate(user):
	name = frappe.db.get_value(AGENT, {"user": user})
	if name:
		frappe.db.set_value(AGENT, name, "enabled", 1)
	else:
		create_agent(frappe.get_doc("User", user))


def add_user_to_onechat(doc, method=None):
	if doc.flags.deleting_onechat_user or doc.name == "Guest":
		return

	has_role = has_app_role(doc)
	name = frappe.db.get_value(AGENT, {"user": doc.name})
	if not name:
		if has_role:
			create_agent(doc)
		return

	agent = frappe.get_doc(AGENT, name)
	before = doc.get_doc_before_save()
	enabled = agent.enabled
	if not has_role or not doc.enabled:
		enabled = 0
	elif before is not None and not has_app_role(before):
		enabled = 1
	values = {
		"full_name": agent.full_name or doc.full_name or doc.first_name,
		"profile_image": agent.profile_image or doc.user_image,
		"enabled": enabled,
	}
	if any(agent.get(field) != value for field, value in values.items()):
		agent.update(values)
		agent.save(ignore_permissions=True)


def remove_user_from_onechat(doc, method):
	if frappe.db.exists("OneChat User", {"user": doc.name}):
		onchat_user = frappe.get_doc("OneChat User", {"user": doc.name})
		onchat_user.delete(ignore_permissions=True)
