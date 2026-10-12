import frappe

from onechat.campaigns.chat_links import click

no_cache = 1
sitemap = 0


def get_context(context):
	frappe.local.flags.redirect_location = click(frappe.form_dict.get("code"))
	raise frappe.Redirect
