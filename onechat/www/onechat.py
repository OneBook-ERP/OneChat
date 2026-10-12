import frappe
from frappe import _
from frappe.utils.telemetry import capture

from onechat.workspace.session import boot, can_use_app

no_cache = 1

SPA_PATH = "/onechat"


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = f"/login?redirect-to={SPA_PATH}"
        raise frappe.Redirect

    if not can_use_app():
        frappe.throw(_("You do not have access to OneChat."), frappe.PermissionError)

    context.boot = boot()
    frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit user session boot data before rendering spa
    capture("active_site", "onechat")

    return context
