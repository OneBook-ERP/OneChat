import frappe

DOCTYPES = (
	"OneChat Account",
	"OneChat Contact",
	"OneChat Message",
	"OneChat Conversation",
	"OneChat Flow Session",
)


def execute():
	for doctype in DOCTYPES:
		if not frappe.db.has_column(doctype, "channel"):
			continue
		table = frappe.qb.DocType(doctype)
		(
			frappe.qb.update(table)
			.set(table.channel, "WhatsApp")
			.where(table.channel.isnull() | (table.channel == ""))
		).run()
