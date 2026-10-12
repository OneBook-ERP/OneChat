import frappe

from onechat.integrations import links

CONTACT = "OneChat Contact"


def execute():
	owners = {}
	done = set(frappe.get_all(links.LINK, filters={"parenttype": CONTACT}, pluck="parent", distinct=True))
	for row in frappe.get_all(
		CONTACT,
		filters={"reference_doctype": ["is", "set"], "reference_docname": ["is", "set"]},
		fields=["name", "reference_doctype", "reference_docname"],
	):
		if row.name in done:
			continue
		if row.reference_doctype not in owners:
			owners[row.reference_doctype] = links.owner(row.reference_doctype)
		integration = owners[row.reference_doctype]
		if not integration:
			continue
		frappe.get_doc(
			{
				"doctype": links.LINK,
				"parent": row.name,
				"parenttype": CONTACT,
				"parentfield": "links",
				"idx": 1,
				"integration": integration,
				"link_doctype": row.reference_doctype,
				"link_name": row.reference_docname,
			}
		).db_insert()
