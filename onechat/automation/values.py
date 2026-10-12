import re

from frappe.utils import cint, getdate, validate_email_address

PLACEHOLDER = re.compile(r"{{\s*([\w.]+)\s*}}")
ALIASES = {
	"name": "contact.display_name",
	"first_name": "contact.first_name",
	"phone": "contact.mobile_no",
	"email": "contact.email",
	"last_reply": "message.text",
}
OPERATORS = {
	"equals",
	"not_equals",
	"contains",
	"not_contains",
	"starts_with",
	"ends_with",
	"greater_than",
	"less_than",
	"is_empty",
	"is_not_empty",
	"is_one_of",
}


def lookup(context, path):
	path = ALIASES.get(path, path)
	value = context
	for part in path.split("."):
		if isinstance(value, dict):
			value = value.get(part)
		elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
			value = value[int(part)]
		else:
			return None
	return value


def as_text(value):
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	if isinstance(value, list | tuple):
		return ", ".join(as_text(item) for item in value)
	return str(value)


def render(text, context):
	if text is None:
		return ""
	return PLACEHOLDER.sub(lambda match: as_text(lookup(context, match.group(1))), str(text))


def resolve(value, context):
	if isinstance(value, str):
		match = PLACEHOLDER.fullmatch(value.strip())
		if match:
			return lookup(context, match.group(1))
		return render(value, context)
	if isinstance(value, dict):
		return {key: resolve(item, context) for key, item in value.items()}
	if isinstance(value, list):
		return [resolve(item, context) for item in value]
	return value


def number(value):
	try:
		return float(str(value).replace(",", "").strip())
	except (TypeError, ValueError):
		return None


def empty(value):
	return value is None or (
		isinstance(value, str | list | dict) and not (value.strip() if isinstance(value, str) else value)
	)


def compare(left, operator, right):
	if operator == "is_empty":
		return empty(left)
	if operator == "is_not_empty":
		return not empty(left)

	left_text, right_text = as_text(left).strip().lower(), as_text(right).strip().lower()
	if operator in ("greater_than", "less_than"):
		a, b = number(left), number(right)
		if a is None or b is None:
			return False
		return a > b if operator == "greater_than" else a < b
	if operator == "equals":
		a, b = number(left), number(right)
		return a == b if a is not None and b is not None else left_text == right_text
	if operator == "not_equals":
		return not compare(left, "equals", right)
	if operator == "contains":
		return right_text in left_text
	if operator == "not_contains":
		return right_text not in left_text
	if operator == "starts_with":
		return left_text.startswith(right_text)
	if operator == "ends_with":
		return left_text.endswith(right_text)
	if operator == "is_one_of":
		return left_text in {item.strip().lower() for item in as_text(right).split(",")}

	return False


def rule_spec(value):
	if isinstance(value, dict):
		return value
	return {"rules": value or []}


def rules_match(config, context, extra=None):
	config = rule_spec(config.get("rules")) if isinstance(config.get("rules"), dict) else config
	rules = [
		rule
		for rule in config.get("rules") or []
		if rule.get("operator") in OPERATORS or (extra and rule.get("operator") in extra)
	]
	if not rules:
		return True

	results = []
	for rule in rules:
		operator = rule.get("operator")
		if extra and operator in extra:
			results.append(bool(extra[operator](rule, context)))
			continue
		left = resolve(rule.get("field") or "", context)
		right = resolve(rule.get("value") or "", context)
		results.append(compare(left, operator, right))

	return any(results) if config.get("match") == "any" else all(results)


def validate_answer(kind, text):
	text = (text or "").strip()
	if not text:
		return False, None
	if kind == "number":
		value = number(text)
		return (value is not None), (int(value) if value is not None and value.is_integer() else value)
	if kind == "email":
		return bool(validate_email_address(text)), text
	if kind == "phone":
		digits = re.sub(r"\D", "", text)
		return 7 <= len(digits) <= 15, digits
	if kind == "date":
		try:
			return True, str(getdate(text))
		except Exception:
			return False, None
	if kind == "yes_no":
		lowered = text.lower()
		if lowered in {"yes", "y", "yeah", "yep", "ok", "sure", "haan", "ha", "aam"}:
			return True, "Yes"
		if lowered in {"no", "n", "nope", "nah", "illa", "nahi"}:
			return True, "No"
		return False, None

	return True, text


def plain(value):
	if isinstance(value, dict):
		return {key: plain(item) for key, item in value.items()}
	if isinstance(value, list | tuple):
		return [plain(item) for item in value]
	if isinstance(value, str | int | float | bool) or value is None:
		return value
	if hasattr(value, "isoformat"):
		return value.isoformat()
	return str(value)


def minutes_of(duration, unit):
	amount = max(cint(duration), 0)
	return amount * {"minutes": 1, "hours": 60, "days": 1440}.get(unit or "minutes", 1)
