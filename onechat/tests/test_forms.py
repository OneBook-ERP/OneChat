from unittest.mock import patch

import frappe

from onechat.campaigns import forms
from onechat.tests.compat import UnitTestCase


def fields(*rows):
	return [frappe._dict(parent=parent, field_name=name) for parent, name in rows]


class TestFormByFields(UnitTestCase):
	def test_matches_the_only_form_with_exactly_these_fields(self):
		rows = fields(("Lead Address", "city"), ("Lead Address", "pincode"), ("Feedback", "city"))
		with patch.object(forms.frappe, "get_all", return_value=rows):
			self.assertEqual(
				forms.form_by_fields({"city": "Chennai", "pincode": "600021", "flow_token": "unused"}),
				"Lead Address",
			)

	def test_ambiguous_match_returns_none(self):
		rows = fields(("Form A", "city"), ("Form B", "city"))
		with patch.object(forms.frappe, "get_all", return_value=rows):
			self.assertIsNone(forms.form_by_fields({"city": "Chennai"}))

	def test_empty_response_returns_none(self):
		self.assertIsNone(forms.form_by_fields({"flow_token": "unused"}))


class TestResolveForm(UnitTestCase):
	def test_real_token_wins(self):
		with patch.object(forms.frappe.db, "get_value", return_value="Lead Address") as get_value:
			self.assertEqual(forms.resolve_form({"flow_token": "abc123"}), "Lead Address")
			get_value.assert_called_once()

	def test_unused_token_falls_back_to_template_button(self):
		sent = frappe._dict(flow=None, template="lead_fs-en")
		with (
			patch.object(forms.frappe.db, "get_value", return_value=sent),
			patch.object(forms, "template_form", return_value="Lead Address"),
		):
			self.assertEqual(forms.resolve_form({"flow_token": "unused"}, "wamid.reply"), "Lead Address")

	def test_falls_back_to_field_names(self):
		with (
			patch.object(forms.frappe.db, "get_value", return_value=None),
			patch.object(forms, "form_by_fields", return_value="Lead Address"),
		):
			self.assertEqual(
				forms.resolve_form({"flow_token": "unused", "city": "Chennai"}, "wamid.reply"), "Lead Address"
			)

	def test_parse_response_drops_flow_token(self):
		self.assertEqual(
			forms.parse_response('{"city": "Chennai", "flow_token": "unused"}'), {"city": "Chennai"}
		)
