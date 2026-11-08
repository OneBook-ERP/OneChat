from contextlib import contextmanager

import frappe
from frappe import _

SETTINGS = "OneChat Settings"
FIELD = "automation_user"
FLAG = "onechat_automation"


def usable(user):
	if not user or user == "Guest":
		return False
	row = frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True)
	return bool(row and row.enabled and row.user_type == "System User")


def check_user(user):
	if user and not usable(user):
		frappe.throw(_("{0} can't run flows and AI. Pick an enabled System User.").format(user))


def automation_user():
	user = frappe.get_cached_doc(SETTINGS).get(FIELD)
	return user if usable(user) else None


def active():
	return bool(frappe.flags.get(FLAG))


@contextmanager
def switched(user):
	previous = frappe.session.user
	form = frappe.local.form_dict
	was_active = frappe.flags.get(FLAG)
	change = bool(user) and user != previous
	frappe.flags[FLAG] = True
	if change:
		frappe.set_user(user)
	try:
		yield user or previous
	finally:
		if change:
			frappe.set_user(previous)
			frappe.local.form_dict = form
		frappe.flags[FLAG] = was_active


def as_automation_user():
	return switched(automation_user())


def elevated(local=True):
	return switched(automation_user() or ("Administrator" if local else None))
