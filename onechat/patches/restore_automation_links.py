import frappe

NEW = "OneChat Flow"


def execute():
	"""rename_flow_doctype used rename_doc, which also repointed Frappe's own links to
	Automation Flow (Automation Run, Automation Trigger Queue) at OneChat Flow, so no
	Workflow Automation could be queued. Reload those doctypes from their own JSON."""
	doctypes = frappe.db.sql_list(
		"""select distinct df.parent from `tabDocField` df
		join `tabDocType` dt on dt.name = df.parent
		where df.options = %s and dt.module != 'OneChat'""",
		NEW,
	)
	for doctype in doctypes:
		frappe.reload_doctype(doctype, force=True)
	if doctypes:
		frappe.clear_cache()
