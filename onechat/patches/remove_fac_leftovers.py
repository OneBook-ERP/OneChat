import frappe

CLIENT_NAME = "OneChat Assistant"
CACHE_PREFIXES = ("onechat:assistant:token:", "onechat:assistant:remote:")


def execute():
	for client in frappe.get_all("OAuth Client", filters={"app_name": CLIENT_NAME}, pluck="name"):
		frappe.db.delete("OAuth Bearer Token", {"client": client})
		frappe.delete_doc("OAuth Client", client, ignore_permissions=True, force=True)
	for prefix in CACHE_PREFIXES:
		frappe.cache().delete_keys(prefix)
