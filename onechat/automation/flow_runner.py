import traceback

import frappe


def evaluate(condition, context):
	try:
		return bool(
			frappe.safe_eval(
				condition,
				eval_locals={"context": attribute_dict(context), "true": True, "false": False},
			)
		)
	except Exception:
		frappe.log_error(title="OneChat flow condition", message=f"{condition}\n\n{traceback.format_exc()}")
		return False


def attribute_dict(value):
	if isinstance(value, dict):
		return frappe._dict({key: attribute_dict(item) for key, item in value.items()})
	if isinstance(value, list):
		return [attribute_dict(item) for item in value]

	return value
