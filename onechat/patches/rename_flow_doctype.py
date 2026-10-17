import frappe

# Frappe v16 ships its own "Automation Flow" (the automation engine CRM's Workflow
# Automations run on). onechat's bot flows move to their own name so both can exist.
OLD, NEW = "Automation Flow", "OneChat Flow"


def execute():
	if frappe.db.get_value("DocType", OLD, "module") != "OneChat" or frappe.db.exists("DocType", NEW):
		return
	frappe.rename_doc("DocType", OLD, NEW, force=True)
	frappe.clear_cache()
