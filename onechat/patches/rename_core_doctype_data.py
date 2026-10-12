import frappe

from onechat.patches.rename_core_doctypes import RENAMES

STORED = (
	("Webhook", ("condition", "webhook_json")),
	("Automation Flow", ("graph_json",)),
)


def renamed(text):
	for old, new in RENAMES.items():
		text = text.replace(f'"{old}"', f'"{new}"').replace(f"'{old}'", f"'{new}'")
	return text


def execute():
	for doctype, fields in STORED:
		if not frappe.db.table_exists(doctype):
			continue
		columns = [field for field in fields if frappe.db.has_column(doctype, field)]
		for row in frappe.get_all(doctype, fields=["name", *columns]):
			updates = {
				field: renamed(row[field])
				for field in columns
				if row[field] and renamed(row[field]) != row[field]
			}
			if updates:
				frappe.db.set_value(doctype, row.name, updates, update_modified=False)
