from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.utils.password import get_decrypted_password, set_encrypted_password

from onechat.assistant import llm, presets, providers, setup
from onechat.patches import migrate_ai_settings
from onechat.tests.compat import IntegrationTestCase, UnitTestCase

SETTINGS = "OneChat Settings"


class RateLimitError(Exception):
	pass


class APIConnectionError(Exception):
	pass


def target(model="anthropic/claude-opus-5-5", api_base=None):
	return frappe._dict(name="x", label="X", model=model, api_key="k", api_base=api_base)


def response(content="", calls=(), finish="stop"):
	tool_calls = [
		SimpleNamespace(id=f"call-{index}", function=SimpleNamespace(name=name, arguments=arguments))
		for index, (name, arguments) in enumerate(calls)
	]
	message = SimpleNamespace(
		content=content,
		tool_calls=tool_calls or None,
		model_dump=lambda exclude_none=True: {"role": "assistant", "content": content},
	)
	return SimpleNamespace(
		choices=[SimpleNamespace(message=message, finish_reason=finish)],
		usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
	)


class TestLLMLayer(UnitTestCase):
	def test_claude_system_prompt_gets_a_cache_marker(self):
		messages = llm.with_cache("anthropic/claude-opus-5-5", [{"role": "system", "content": "rules"}])
		self.assertEqual(messages[0]["content"][0]["cache_control"], llm.CACHE)

	def test_other_models_are_left_alone(self):
		messages = [{"role": "system", "content": "rules"}]
		self.assertIs(llm.with_cache("openai/gpt-6.1-sol", messages), messages)

	def test_claude_on_openrouter_is_pinned_to_anthropic(self):
		extra = llm.routing(target("openrouter/anthropic/claude-opus-5.5"))["extra_body"]
		self.assertEqual(extra["provider"]["order"], ["anthropic"])
		self.assertEqual(
			llm.routing(target(api_base="http://localhost:11434/v1")),
			{"api_base": "http://localhost:11434/v1"},
		)

	def test_errors_become_fixed_messages(self):
		self.assertIn("busy", llm.user_facing_error(RateLimitError("secret details")))
		self.assertNotIn("secret", llm.user_facing_error(ValueError("secret details")))

	def test_used_up_quota_says_so(self):
		message = llm.user_facing_error(RateLimitError("You exceeded your current quota, per day limit"))
		self.assertIn("quota", message)
		self.assertNotIn("per day limit", message)

	def test_rate_limits_are_not_retried(self):
		with patch.object(llm, "call", side_effect=RateLimitError("slow down")) as sent:
			with self.assertRaises(RateLimitError):
				llm.complete(target(), [], [], 100)
		self.assertEqual(sent.call_count, 1)

	def test_dropped_connections_are_retried_once(self):
		with (
			patch.object(llm, "call", side_effect=[APIConnectionError("reset"), "ok"]) as sent,
			patch.object(llm.time, "sleep"),
		):
			self.assertEqual(llm.complete(target(), [], [], 100), "ok")
		self.assertEqual(sent.call_count, 2)

	def test_broken_tool_arguments_are_repaired_or_emptied(self):
		self.assertEqual(providers.arguments_of('{"a": 1}'), {"a": 1})
		self.assertEqual(providers.arguments_of({"a": 1}), {"a": 1})
		self.assertIsInstance(providers.arguments_of("{'a': 1,"), dict)
		self.assertEqual(providers.arguments_of("[1, 2]"), {})

	def test_step_reads_tool_calls(self):
		provider = providers.Provider(
			target(), "rules", [{"name": "find_items", "description": "d", "schema": {}}]
		)
		messages = []
		with patch.object(
			llm, "complete", return_value=response("Looking", [("find_items", '{"text": "sofa"}')])
		):
			turn = provider.step(messages)
		self.assertEqual(turn.calls, [{"id": "call-0", "name": "find_items", "input": {"text": "sofa"}}])
		self.assertEqual(turn.usage, {"input": 10, "output": 5})
		self.assertEqual(messages[-1]["role"], "assistant")

	def test_refusal_is_reported(self):
		provider = providers.Provider(target(), "rules", [])
		with patch.object(llm, "complete", return_value=response(finish="content_filter")):
			self.assertTrue(provider.step([]).refused)

	def test_provider_errors_are_safe(self):
		provider = providers.Provider(target(), "rules", [])
		with patch.object(llm, "complete", side_effect=RateLimitError("raw provider text")):
			with self.assertRaises(providers.ProviderError) as caught:
				provider.step([])
		self.assertNotIn("raw provider text", str(caught.exception))

	def test_failed_tools_are_marked(self):
		messages = []
		providers.Provider(target(), "rules", []).results(
			messages, [{"id": "1", "text": "no", "error": True}]
		)
		self.assertEqual(messages, [{"role": "tool", "tool_call_id": "1", "content": "Error: no"}])


class TestModels(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		for name in frappe.get_all(llm.PROVIDER, filters={"provider_name": ["like", "Test %"]}, pluck="name"):
			setup.remove_provider(name)

	def add(self, preset_id, key="", base="", models=("m1",), name="Test Provider"):
		preset = presets.find(preset_id)
		return presets.install(preset, key, base, list(models), name)

	def test_missing_key_is_explained(self):
		_provider, (model,) = self.add("openai")
		with self.assertRaises(llm.ModelError):
			llm.resolve(model)

	def test_keyless_custom_server_works(self):
		_provider, (model,) = self.add("custom", base="http://localhost:11434/v1", name="Test Ollama")
		resolved = llm.resolve(model)
		self.assertEqual(resolved.model, "openai/m1")
		self.assertEqual(resolved.api_base, "http://localhost:11434/v1")

	def test_switched_off_model_is_refused(self):
		_provider, (model,) = self.add("anthropic", key="sk-ant-test")
		self.assertTrue(llm.ready(model))
		setup.set_model_enabled(model, 0)
		self.assertFalse(llm.ready(model))

	def test_install_is_idempotent_and_keeps_the_key(self):
		provider, _models = self.add("anthropic", key="sk-ant-test", models=("claude-opus-5-5",))
		self.add("anthropic", key="", models=("claude-opus-5-5",))
		self.assertEqual(frappe.db.count(llm.PROVIDER, {"name": provider}), 1)
		self.assertEqual(frappe.get_doc(llm.PROVIDER, provider).resolved_key(), "sk-ant-test")
		self.assertEqual(frappe.db.count(llm.MODEL, {"provider": provider, "enabled": 1}), 1)


class TestMigration(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if frappe.db.exists(llm.PROVIDER, "Anthropic"):
			self.skipTest("This site already has an Anthropic provider.")
		self.before = frappe.db.get_single_value(SETTINGS, "assistant_model")
		frappe.db.set_single_value(SETTINGS, "assistant_model", None)

	def tearDown(self):
		for name in frappe.get_all(
			llm.PROVIDER, filters={"name": ["in", ["Anthropic", "Test Gateway"]]}, pluck="name"
		):
			setup.remove_provider(name)
		frappe.db.set_single_value(SETTINGS, "assistant_model", self.before)

	def old(self, values, keys):
		for field, value in values.items():
			frappe.db.sql(
				"insert into `tabSingles` (doctype, field, value) values (%s, %s, %s)",
				(SETTINGS, field, value),
			)
		for field, value in keys.items():
			set_encrypted_password(SETTINGS, SETTINGS, value, field)

	def test_old_settings_become_providers_and_keys_are_cleared(self):
		self.old(
			{
				"assistant_provider": "Other",
				"assistant_other_name": "Test Gateway",
				"assistant_other_url": "http://localhost:4000/v1",
				"assistant_other_model": "llama3.1",
			},
			{"assistant_anthropic_key": "sk-ant-old", "assistant_other_key": "gw-old"},
		)
		migrate_ai_settings.execute()

		self.assertEqual(frappe.get_doc(llm.PROVIDER, "Anthropic").resolved_key(), "sk-ant-old")
		self.assertEqual(frappe.get_doc(llm.PROVIDER, "Test Gateway").api_base, "http://localhost:4000/v1")
		self.assertEqual(frappe.db.get_single_value(SETTINGS, "assistant_model"), "Test Gateway: llama3.1")
		self.assertIsNone(
			get_decrypted_password(SETTINGS, SETTINGS, "assistant_anthropic_key", raise_exception=False)
		)
		self.assertEqual(migrate_ai_settings.old_value("assistant_other_url"), "")

		migrate_ai_settings.execute()
		self.assertEqual(frappe.db.count(llm.PROVIDER, {"name": "Test Gateway"}), 1)
