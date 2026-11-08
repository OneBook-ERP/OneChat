import json
from unittest.mock import patch

import frappe

from onechat.assistant import cards, tools
from onechat.assistant.access import RIGHTS
from onechat.assistant.tools import Tool, records
from onechat.tests.compat import IntegrationTestCase, UnitTestCase

EVERYTHING = frozenset(RIGHTS)
READ = frozenset({"read"})


def names(level, contact=None):
	return {spec["name"] for spec in tools.available(level, contact)}


def result(name, arguments, level=EVERYTHING, contact=None):
	text, error = tools.run(name, arguments, level, contact)
	return (text if error else json.loads(text)), error


class TestRegistry(UnitTestCase):
	def test_tools_are_unique_and_well_formed(self):
		found = tools.registry()
		self.assertEqual(len(found), len({tool.name for tool in found}))
		for tool in found:
			self.assertEqual(tool.schema["type"], "object")
			self.assertIn(tool.right, RIGHTS)
			self.assertTrue(tool.description)

	def test_read_only_hides_changes(self):
		with patch.object(tools, "integration_ready", return_value=True):
			shown = names(READ, "CONTACT-1")
		self.assertIn("search_records", shown)
		self.assertIn("customer_overview", shown)
		self.assertNotIn("create_document", shown)
		self.assertNotIn("send_payment_link", shown)

	def test_chat_tools_need_an_open_chat(self):
		with patch.object(tools, "integration_ready", return_value=True):
			self.assertNotIn("what_customer_owes", names(EVERYTHING))
			self.assertIn("what_customer_owes", names(EVERYTHING, "CONTACT-1"))

	def test_integration_tools_need_the_integration(self):
		with patch.object(tools, "integration_ready", return_value=False):
			shown = names(EVERYTHING, "CONTACT-1")
		self.assertIn("get_record", shown)
		self.assertNotIn("find_items", shown)
		self.assertNotIn("send_payment_link", shown)

	def test_only_reads_skip_confirmation(self):
		self.assertFalse(tools.needs_confirm("search_records"))
		self.assertTrue(tools.needs_confirm("create_document"))
		self.assertTrue(tools.needs_confirm("send_payment_link"))
		self.assertTrue(tools.needs_confirm("run_python_code"))

	def test_unknown_tools_are_refused(self):
		text, error = tools.run("run_database_query", {}, EVERYTHING)
		self.assertTrue(error)
		self.assertFalse(tools.allowed("delete_document", EVERYTHING))

	def test_progress_names_the_tool(self):
		self.assertEqual(cards.progress("search_records", {"doctype": "ToDo"}), "Looking up ToDo records")
		self.assertEqual(cards.progress("find_items", {}), "Finding items")
		self.assertEqual(cards.progress("anything_else", {}), "Working on it")


class TestRecordTools(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "Call Leo about the sofa order"}
		).insert()

	def test_handlers_run_as_the_agent(self):
		seen = {}
		probe = Tool(
			"probe", "probe", {"type": "object"}, lambda call: seen.update(agent=frappe.flags.onechat_agent)
		)
		with patch.object(tools, "registry", return_value=[probe]):
			tools.run("probe", {}, EVERYTHING)
		self.assertEqual(seen["agent"], "Administrator")
		self.assertFalse(frappe.flags.get("onechat_agent"))

	def test_blocked_doctypes_are_refused(self):
		for doctype in ("User", "OneChat Message", "OneChat Settings"):
			text, error = result("search_records", {"doctype": doctype})
			self.assertTrue(error, doctype)

	def test_unknown_doctype_is_explained(self):
		text, error = result("get_record", {"doctype": "No Such Thing", "name": "X"})
		self.assertTrue(error)
		self.assertIn("No Such Thing", text)

	def test_search_finds_by_text(self):
		data, error = result("search_records", {"doctype": "ToDo", "text": "sofa order", "fields": ["name"]})
		self.assertFalse(error)
		self.assertIn(self.todo.name, [row["name"] for row in data["rows"]])

	def test_bad_field_names_are_refused(self):
		text, error = result("search_records", {"doctype": "ToDo", "fields": ["name; drop table"]})
		self.assertTrue(error)

	def test_get_record_is_compact(self):
		data, error = result("get_record", {"doctype": "ToDo", "name": self.todo.name})
		self.assertFalse(error)
		self.assertEqual(data["name"], self.todo.name)
		self.assertFalse([key for key in data if key.startswith("_")])

	def test_count_and_total(self):
		data, error = result("count_and_total", {"doctype": "ToDo", "filters": {"name": self.todo.name}})
		self.assertFalse(error)
		self.assertEqual(data["count"], 1)

	def test_create_ignores_protected_fields(self):
		data, error = result(
			"create_document",
			{"doctype": "ToDo", "values": {"description": "Follow up", "owner": "Guest", "docstatus": 1}},
		)
		self.assertFalse(error)
		created = frappe.get_doc("ToDo", data["name"])
		self.assertEqual(created.owner, "Administrator")
		self.assertEqual(created.docstatus, 0)

	def test_failed_change_is_rolled_back(self):
		before = frappe.db.count("ToDo")
		text, error = result("create_document", {"doctype": "ToDo", "values": {"status": "Not A Status"}})
		self.assertTrue(error)
		self.assertEqual(frappe.db.count("ToDo"), before)

	def test_update_changes_only_given_fields(self):
		data, error = result(
			"update_document", {"doctype": "ToDo", "name": self.todo.name, "values": '{"priority": "High"}'}
		)
		self.assertFalse(error)
		self.assertEqual(data["fields"], ["priority"])
		self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "priority"), "High")

	def test_read_level_cannot_create(self):
		text, error = result("create_document", {"doctype": "ToDo", "values": {"description": "x"}}, READ)
		self.assertTrue(error)

	def test_child_rows_are_trimmed(self):
		rows = [
			{"item_code": str(index), "parent": "X", "idx": index} for index in range(records.CHILD_ROWS + 2)
		]
		data = records.compact({"name": "A", "items": rows, "_seen": "x", "empty": ""})
		self.assertEqual(len(data["items"]), records.CHILD_ROWS)
		self.assertEqual(data["items_more_rows"], 2)
		self.assertNotIn("parent", data["items"][0])
		self.assertNotIn("_seen", data)
		self.assertNotIn("empty", data)
