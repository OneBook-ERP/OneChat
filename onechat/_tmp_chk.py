import frappe


def run():
	meta = frappe.get_meta("OneChat Account")
	wanted = [
		f.fieldname
		for f in meta.fields
		if f.fieldtype in ("Data", "Check", "Select", "Link") and not f.fieldname.endswith("_break")
	]
	for row in frappe.get_all("OneChat Account", fields=["name", *wanted]):
		print(
			{
				k: v
				for k, v in row.items()
				if v not in (None, "", 0) and "token" not in k and "secret" not in k
			}
		)
	print("public url:", frappe.utils.get_url(), "| host_name:", frappe.conf.get("host_name"))
