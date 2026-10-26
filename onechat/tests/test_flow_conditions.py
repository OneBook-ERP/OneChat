from typing import ClassVar

from onechat.automation.flow_runner import attribute_dict, evaluate
from onechat.automation.values import compare, render, rules_match, validate_answer
from onechat.tests.compat import UnitTestCase


class TestLegacyConditions(UnitTestCase):
	def test_attribute_and_key_access(self):
		context = {"doc": {"status": "Paid", "grand_total": 1500}}

		self.assertTrue(evaluate("context.doc.status == 'Paid'", context))
		self.assertTrue(evaluate("context['doc']['grand_total'] > 1000", context))
		self.assertFalse(evaluate("context.doc.status == 'Unpaid'", context))

	def test_blocks_sandbox_escape(self):
		self.assertFalse(evaluate("().__class__.__mro__[1].__subclasses__()", {}))
		self.assertFalse(evaluate("__import__('os').system('true')", {}))

	def test_invalid_expression_is_false(self):
		self.assertFalse(evaluate("context.doc.status ==", {}))

	def test_attribute_dict_converts_nested_values(self):
		value = attribute_dict({"items": [{"qty": 2}], "doc": {"name": "SO-1"}})

		self.assertEqual(value.doc.name, "SO-1")
		self.assertEqual(value["items"][0].qty, 2)


class TestValues(UnitTestCase):
	context: ClassVar[dict] = {
		"contact": {"contact_name": "Priya Raman", "first_name": "Priya", "mobile_no": "919876543210"},
		"answers": {"budget": "25,000", "city": "Chennai"},
		"message": {"text": "Track my order"},
	}

	def test_render_paths_and_aliases(self):
		self.assertEqual(
			render("Hi {{first_name}}, from {{ answers.city }}", self.context), "Hi Priya, from Chennai"
		)
		self.assertEqual(render("You said: {{last_reply}}", self.context), "You said: Track my order")
		self.assertEqual(render("Missing: {{answers.unknown}}.", self.context), "Missing: .")

	def test_compare_numbers_and_text(self):
		self.assertTrue(compare("25,000", "greater_than", "20000"))
		self.assertTrue(compare("Chennai", "equals", "chennai"))
		self.assertTrue(compare("Chennai", "is_one_of", "Madurai, Chennai"))
		self.assertTrue(compare("", "is_empty", None))
		self.assertFalse(compare("abc", "greater_than", "5"))

	def test_rules_all_and_any(self):
		rules = [
			{"field": "{{answers.budget}}", "operator": "greater_than", "value": "10000"},
			{"field": "{{answers.city}}", "operator": "equals", "value": "Madurai"},
		]

		self.assertFalse(rules_match({"match": "all", "rules": rules}, self.context))
		self.assertTrue(rules_match({"match": "any", "rules": rules}, self.context))
		self.assertTrue(rules_match({"rules": []}, self.context))

	def test_validate_answers(self):
		self.assertEqual(validate_answer("number", "42"), (True, 42))
		self.assertEqual(validate_answer("email", "not-an-email")[0], False)
		self.assertEqual(validate_answer("phone", "+91 98765 43210"), (True, "919876543210"))
		self.assertEqual(validate_answer("yes_no", "Yeah"), (True, "Yes"))
		self.assertEqual(validate_answer("text", "   ")[0], False)
