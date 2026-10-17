import frappe
from frappe import _
from frappe.translate import get_all_translations
from frappe.utils import cint

APP_ROLES = {"OneChat Agent", "OneChat Admin", "OneChat Manager", "System Manager"}
ADMIN_ROLES = {"OneChat Admin", "OneChat Manager", "System Manager"}


def can_use_app(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if "System Manager" in roles:
		return True
	if not APP_ROLES & roles:
		return False
	enabled = frappe.db.get_value("OneChat User", {"user": user}, "enabled")
	return enabled is None or bool(cint(enabled))


def is_admin(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	return bool(ADMIN_ROLES & set(frappe.get_roles(user)))


def require_app_user():
	if not can_use_app():
		frappe.throw(_("You do not have access to OneChat."), frappe.PermissionError)


def require_admin():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can do this."), frappe.PermissionError)


READ_DOCTYPES = (
	"OneChat Contact",
	"OneChat Message",
	"OneChat Note",
	"Bulk WhatsApp Message",
	"WhatsApp Templates",
	"WhatsApp Recipient List",
	"WhatsApp Flow",
	"OneChat Flow",
	"OneChat Chat Link",
	"OneChat Media",
)


ACTION_DOCTYPES = (*READ_DOCTYPES, "OneChat Label", "OneChat Segment", "OneChat WhatsApp Payment")
PTYPES = ("read", "write", "create", "delete")
VERBS = {
	"read": "read",
	"write": "edit",
	"create": "create",
	"delete": "delete",
	"cancel": "cancel",
	"submit": "submit",
}


def can(doctype, ptype="read", doc=None, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	try:
		return bool(frappe.has_permission(doctype, ptype, doc=doc, user=user))
	except frappe.DoesNotExistError:
		return False


def can_read(doctype, doc=None, user=None):
	return can(doctype, "read", doc, user)


def require(doctype, ptype="read", doc=None):
	if not can(doctype, ptype, doc):
		frappe.throw(
			_("Your role can't {0} {1}. Ask an admin to allow it in Role Permission Manager.").format(
				_(VERBS.get(ptype, ptype)), _(doctype)
			),
			frappe.PermissionError,
		)


def require_read(doctype, doc=None):
	require(doctype, "read", doc)


def is_system_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


@frappe.whitelist()
def me():
	user = frappe.get_cached_doc("User", frappe.session.user)

	return {
		"name": user.name,
		"full_name": user.full_name,
		"image": user.user_image,
		"is_admin": is_admin(),
		"is_system_manager": is_system_manager(),
		"availability": frappe.db.get_value("OneChat User", {"user": user.name}, "availability")
		or "Available",
		"language": frappe.local.lang or user.language or "en",
		"rtl": (frappe.local.lang or user.language or "en") in RIGHT_TO_LEFT,
		"theme": theme(),
		"can_read": {doctype: can_read(doctype) for doctype in READ_DOCTYPES},
		"can": {doctype: {ptype: can(doctype, ptype) for ptype in PTYPES} for doctype in ACTION_DOCTYPES},
	}


THEMES = {"Light": "light", "Dark": "dark", "Automatic": "system"}

LANGUAGES = {"en": "English", "hi": "हिन्दी", "ar": "العربية"}
RIGHT_TO_LEFT = {"ar"}


@frappe.whitelist()
def theme():
	return THEMES.get(frappe.db.get_value("User", frappe.session.user, "desk_theme"), "light")


@frappe.whitelist()
def languages():
	require_app_user()
	installed = set(frappe.get_all("Language", filters={"name": ("in", list(LANGUAGES))}, pluck="name"))
	return [
		{"name": code, "language_name": label, "rtl": code in RIGHT_TO_LEFT}
		for code, label in LANGUAGES.items()
		if code in installed
	]


@frappe.whitelist(methods=["POST"])
def set_language(language: str):
	require_app_user()
	if language not in LANGUAGES or not frappe.db.exists("Language", language):
		frappe.throw(_("That language is not available."))
	frappe.db.set_value("User", frappe.session.user, "language", language)
	frappe.clear_cache(user=frappe.session.user)
	return language


@frappe.whitelist()
def boot():
	return {
		"csrf_token": frappe.sessions.get_csrf_token(),
		"site_name": frappe.local.site,
		"socketio_port": frappe.conf.socketio_port or 9000,
		"onechat_user": me(),
		"onechat_country": default_country(),
	}


def default_country():
	country = frappe.db.get_single_value("System Settings", "country")
	code = frappe.db.get_value("Country", country, "code") if country else None
	return (code or "").upper() or None


@frappe.whitelist()
def translations():
	return get_all_translations(frappe.local.lang)
