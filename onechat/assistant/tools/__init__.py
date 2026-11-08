import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _
from frappe.utils import strip_html

RESULT_LIMIT = 20000
SAVEPOINT = "onechat_assistant_tool"
AGENT_FLAG = "onechat_agent"


class ToolError(frappe.ValidationError):
	pass


@dataclass
class Tool:
	name: str
	description: str
	schema: dict
	handler: Any
	right: str = "read"
	needs: tuple = ()
	contact: bool = False

	def spec(self):
		return {"name": self.name, "description": self.description, "schema": self.schema}

	def ready(self, level, contact=None):
		if self.right not in (level or ()):
			return False
		if self.contact and not contact:
			return False
		return all(integration_ready(key) for key in self.needs)


@dataclass
class Call:
	arguments: dict
	contact: str | None = None

	def get(self, key, default=None):
		value = self.arguments.get(key)
		return default if value in (None, "") else value


def integration_ready(key):
	if key == "payments":
		from onechat.integrations.extras import payments_active

		return payments_active()
	from onechat.integrations import connection

	return connection.site(key).ready()


def registry():
	from onechat.assistant.tools import erpnext, records

	return [*records.TOOLS, *erpnext.TOOLS]


def find(name):
	return next((tool for tool in registry() if tool.name == name), None)


def available(level, contact=None):
	return [tool.spec() for tool in registry() if tool.ready(level, contact)]


def allowed(name, level, contact=None):
	tool = find(name)
	return bool(tool and tool.ready(level, contact))


def needs_confirm(name):
	tool = find(name)
	return not tool or tool.right != "read"


@contextmanager
def as_agent():
	previous = frappe.flags.get(AGENT_FLAG)
	frappe.flags[AGENT_FLAG] = frappe.session.user
	try:
		yield
	finally:
		frappe.flags[AGENT_FLAG] = previous


def as_text(result):
	text = result if isinstance(result, str) else json.dumps(result, default=str, ensure_ascii=False)
	return text[:RESULT_LIMIT]


def run(name, arguments, level, contact=None):
	tool = find(name)
	if not tool or not tool.ready(level, contact):
		return _("This tool is not available to you."), True
	frappe.db.savepoint(SAVEPOINT)
	try:
		with as_agent():
			return as_text(tool.handler(Call(arguments or {}, contact))), False
	except (frappe.ValidationError, frappe.PermissionError) as error:
		frappe.db.rollback(save_point=SAVEPOINT)
		frappe.clear_last_message()
		return strip_html(str(error)).strip() or _("That didn't work."), True
	except Exception:
		frappe.db.rollback(save_point=SAVEPOINT)
		frappe.log_error(title=f"OneChat assistant tool {name}")
		return _("Something went wrong running {0}.").format(name), True
