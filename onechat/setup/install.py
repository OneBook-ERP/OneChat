import frappe


def before_install():
    roles_to_create = ["OneChat Agent", "OneChat Manager", "OneChat Admin"]

    for role_name in roles_to_create:
        if not frappe.db.exists("Role", role_name):
            role = frappe.get_doc({"doctype": "Role", "role_name": role_name})
            role.insert(ignore_permissions=True)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit - persist roles during bench app install


def before_uninstall():
    roles_to_delete = ["OneChat Agent", "OneChat Manager", "OneChat Admin"]

    for role_name in roles_to_delete:
        if frappe.db.exists("Role", role_name):
            frappe.delete_doc("Role", role_name)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit - persist role removal during bench uninstall
