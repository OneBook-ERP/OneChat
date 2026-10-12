import frappe


def execute():
	if "crm" not in frappe.get_installed_apps():
		return

	from onechat.integrations.frappe_crm import DEAL, LEAD, claim

	for row in frappe.get_all(
		"OneChat Contact",
		filters={"reference_doctype": ["in", [LEAD, DEAL]], "reference_docname": ["is", "set"]},
		fields=["name", "reference_doctype", "reference_docname"],
	):
		claim(row.name, row.reference_doctype, row.reference_docname)
