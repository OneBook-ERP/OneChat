import frappe

from onechat.inbox import auto_reply
from onechat.onechat.doctype.onechat_auto_reply.onechat_auto_reply import keyword_list
from onechat.tests.compat import IntegrationTestCase, UnitTestCase


class TestKeywordMatching(UnitTestCase):
	def match(self, text, keyword, match_type="Contains"):
		return auto_reply.matches(auto_reply.normalize(text), keyword, match_type)

	def test_contains_matches_whole_words_only(self):
		self.assertTrue(self.match("Hi there", "hi"))
		self.assertFalse(self.match("this is it", "hi"))

	def test_contains_ignores_case_and_punctuation(self):
		self.assertTrue(self.match("What's the PRICE?", "price"))

	def test_exact_ignores_trailing_punctuation(self):
		self.assertTrue(self.match("Hello!", "hello", "Exact"))
		self.assertFalse(self.match("hello world", "hello", "Exact"))

	def test_starts_with_needs_a_word_boundary(self):
		self.assertTrue(self.match("order status please", "order status", "Starts with"))
		self.assertFalse(self.match("orders", "order", "Starts with"))

	def test_keyword_list_splits_dedupes_and_lowercases(self):
		self.assertEqual(keyword_list("Price, how  much\nprice\n\n"), ["price", "how much"])


class TestRuleSelection(IntegrationTestCase):
	def make_rule(self, name, keywords, priority=0, cooldown=0):
		return frappe.get_doc(
			{
				"doctype": "OneChat Auto Reply",
				"rule_name": name,
				"keywords": keywords,
				"message": f"Reply from {name}",
				"priority": priority,
				"cooldown_minutes": cooldown,
			}
		).insert(ignore_permissions=True)

	def setUp(self):
		frappe.db.delete("OneChat Auto Reply")

	def test_highest_priority_wins(self):
		self.make_rule("Low", "price", priority=0)
		high = self.make_rule("High", "price", priority=5)

		rule = auto_reply.first_match("what is the price", "contact-a")

		self.assertEqual(rule.name, high.name)

	def test_no_match_returns_none(self):
		self.make_rule("Pricing", "price")

		self.assertIsNone(auto_reply.first_match("where is my order", "contact-a"))

	def test_cooldown_blocks_second_reply(self):
		rule = self.make_rule(f"Cooldown {frappe.generate_hash(length=6)}", "hours", cooldown=60)
		contact = f"contact-{frappe.generate_hash(length=6)}"

		self.assertEqual(auto_reply.first_match("your hours?", contact).name, rule.name)
		self.assertIsNone(auto_reply.first_match("your hours?", contact))

	def test_disabled_rule_is_skipped(self):
		rule = self.make_rule("Paused", "refund")
		frappe.db.set_value("OneChat Auto Reply", rule.name, "enabled", 0)

		self.assertIsNone(auto_reply.first_match("I want a refund", "contact-a"))
