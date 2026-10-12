import re

import frappe

from onechat import integrations

PHONE_TYPES = ("Phone",)


def country_code():
	return str(integrations.setting("default_country_code") or "").strip().lstrip("+")


def frappe_phone(value):
	text = str(value or "").strip()
	digits = re.sub(r"\D", "", text)
	if not digits:
		return value
	if re.fullmatch(r"\+\d{1,4}-\d{4,}", text):
		return text

	code = country_code()
	if code and len(digits) == 10:
		return f"+{code}-{digits}"

	try:
		import phonenumbers

		parsed = phonenumbers.parse(f"+{digits}")
		if phonenumbers.is_valid_number(parsed):
			return f"+{parsed.country_code}-{parsed.national_number}"
	except Exception:
		pass

	if code and digits.startswith(code) and len(digits) > len(code) + 6:
		return f"+{code}-{digits[len(code) :]}"
	return f"+{digits}"


def phone_fields(doctype, source):
	if source.remote:
		return {
			row["fieldname"]
			for row in source.meta_fields(doctype)
			if row["fieldtype"] in PHONE_TYPES or row.get("options") == "Phone"
		}
	meta = frappe.get_meta(doctype)
	return {df.fieldname for df in meta.fields if df.fieldtype in PHONE_TYPES or df.options == "Phone"}


def with_phones(doctype, values, source):
	fields = phone_fields(doctype, source)
	return {key: frappe_phone(value) if key in fields and value else value for key, value in values.items()}
