from unittest.mock import MagicMock, patch

import frappe

from onechat.inbox import contact_accounts
from onechat.tests.compat import UnitTestCase


def message(**values):
	return frappe._dict(
		{
			"type": "Incoming",
			"content_type": "text",
			"message": "Hello",
			"whatsapp_account": "FS Test",
			"creation": "2026-10-24 10:00:00",
			**values,
		}
	)


class TestRowUpdates(UnitTestCase):
	def test_incoming_bumps_unread_and_incoming_time(self):
		values = contact_accounts.row_updates(message(), "Hello", {"unread_count": 2})

		self.assertEqual(values["unread_count"], 3)
		self.assertEqual(values["last_incoming_at"], "2026-10-24 10:00:00")
		self.assertEqual(values["last_message_type"], "Incoming")

	def test_quiet_incoming_keeps_unread(self):
		values = contact_accounts.row_updates(message(), "Hello", {"unread_count": 2}, unread=False)

		self.assertEqual(values["unread_count"], 2)

	def test_outgoing_leaves_unread_and_incoming_alone(self):
		values = contact_accounts.row_updates(message(type="Outgoing"), "Hi there", {"unread_count": 2})

		self.assertNotIn("unread_count", values)
		self.assertNotIn("last_incoming_at", values)
		self.assertEqual(values["last_message"], "Hi there")


def account_row(account, incoming_at=None, unread=0):
	return frappe._dict(
		account=account, last_incoming_at=incoming_at, last_message_at=incoming_at, unread_count=unread
	)


class TestReplyAccount(UnitTestCase):
	def test_window_is_open_for_24_hours(self):
		at = frappe.utils.get_datetime("2026-10-24 12:00:00")

		self.assertTrue(contact_accounts.window_open(account_row("A", "2026-10-23 12:30:00"), at))
		self.assertFalse(contact_accounts.window_open(account_row("A", "2026-10-23 11:30:00"), at))
		self.assertFalse(contact_accounts.window_open(account_row("A"), at))

	def test_prefers_the_current_account_when_its_window_is_open(self):
		rows = [
			account_row("FS Test", frappe.utils.now_datetime()),
			account_row("Test Account", frappe.utils.now_datetime()),
		]
		with (
			patch.object(frappe.db, "get_value", return_value="Test Account"),
			patch.object(contact_accounts, "rows_of", return_value=rows),
		):
			self.assertEqual(contact_accounts.reply_account("WC-1"), "Test Account")

	def test_falls_back_to_the_newest_open_shown_account(self):
		rows = [
			account_row("FS Test", frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-2)),
			account_row("Test Account", frappe.utils.now_datetime()),
		]
		with (
			patch.object(frappe.db, "get_value", return_value="Old"),
			patch.object(contact_accounts, "rows_of", return_value=rows),
		):
			self.assertEqual(contact_accounts.reply_account("WC-1"), "Test Account")
			self.assertEqual(contact_accounts.reply_account("WC-1", hidden=["Test Account"]), "FS Test")
			self.assertIsNone(contact_accounts.reply_account("WC-1", hidden=["Test Account", "FS Test"]))

	def test_closed_window_is_refused(self):
		rows = [account_row("FS Test", frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-30))]
		with patch.object(contact_accounts, "rows_of", return_value=rows):
			with self.assertRaises(frappe.ValidationError):
				contact_accounts.require_window("WC-1", "FS Test")
			contact_accounts.require_window("WC-1", "Unknown")


class TestOverlay(UnitTestCase):
	def test_preview_and_unread_come_from_shown_accounts(self):
		rows = [frappe._dict(name="WC-1", last_message="hidden one", unread_count=5)]
		grouped = {
			"WC-1": [
				frappe._dict(
					account="FS Test",
					last_message="shown one",
					last_message_at="2026-10-24 09:00:00",
					last_message_type="Incoming",
					unread_count=1,
				),
				frappe._dict(
					account="Other",
					last_message="older",
					last_message_at="2026-10-24 08:00:00",
					last_message_type="Outgoing",
					unread_count=2,
				),
			]
		}
		with patch.object(contact_accounts, "rows_for", return_value=grouped):
			contact_accounts.overlay(rows, hidden=["Test Account"])

		self.assertEqual(rows[0].last_message, "shown one")
		self.assertEqual(rows[0].unread_count, 3)

	def test_nothing_hidden_leaves_rows_alone(self):
		rows = [frappe._dict(name="WC-1", last_message="x", unread_count=5)]
		with patch.object(contact_accounts, "rows_for") as rows_for:
			contact_accounts.overlay(rows, hidden=[])

		rows_for.assert_not_called()
		self.assertEqual(rows[0].unread_count, 5)


class TestSamePerson(UnitTestCase):
	def test_instagram_twins_are_found_by_username_on_other_accounts(self):
		from onechat.inbox import conversations, visibility
		from onechat.workspace import numbers

		doc = frappe._dict(
			name="IG-1", channel="Instagram", instagram_username="Leo_Daniel", whatsapp_account="Brand"
		)
		twins = [
			frappe._dict(name="IG-2", whatsapp_account="Support", conversation_status="Open", unread_count=2),
			frappe._dict(name="IG-3", whatsapp_account="Hidden", conversation_status="Open", unread_count=0),
		]
		accounts = [frappe._dict(name="Support", account_name="Support desk")]
		with (
			patch.object(frappe, "get_all", side_effect=[twins, accounts]) as get_all,
			patch.object(numbers, "hidden", return_value=["Hidden"]),
			patch.object(visibility, "allowed", return_value=True),
		):
			result = conversations.same_person(doc)

		self.assertEqual(get_all.call_args_list[0].kwargs["filters"]["instagram_username"], "leo_daniel")
		self.assertEqual([row["name"] for row in result], ["IG-2"])
		self.assertEqual(result[0]["account_label"], "Support desk")
		self.assertEqual(result[0]["unread_count"], 2)

	def test_whatsapp_contacts_and_missing_usernames_have_no_twins(self):
		from onechat.inbox import conversations

		self.assertEqual(
			conversations.same_person(frappe._dict(channel="WhatsApp", instagram_username="x")), []
		)
		self.assertEqual(
			conversations.same_person(frappe._dict(channel="Instagram", instagram_username="")), []
		)


class TestTouch(UnitTestCase):
	def test_updates_the_existing_row_for_the_account(self):
		current = frappe._dict(name="ROW-1", unread_count=1)
		with (
			patch.object(frappe.db, "get_value", return_value=current) as get_value,
			patch.object(frappe.db, "set_value") as set_value,
		):
			contact_accounts.touch("WC-1", message(), "Hello")

		self.assertEqual(get_value.call_args.args[1]["account"], "FS Test")
		self.assertEqual(set_value.call_args.args[1], "ROW-1")
		self.assertEqual(set_value.call_args.args[2]["unread_count"], 2)

	def test_inserts_a_row_for_a_new_account(self):
		inserted = MagicMock()
		with (
			patch.object(frappe.db, "get_value", return_value=None),
			patch.object(frappe, "get_doc", return_value=inserted) as get_doc,
		):
			contact_accounts.touch("WC-1", message(whatsapp_account="Test Account"), "Hello")

		row = get_doc.call_args.args[0]
		self.assertEqual(
			(row["parent"], row["parentfield"], row["account"]), ("WC-1", "accounts", "Test Account")
		)
		self.assertEqual(row["unread_count"], 1)
		inserted.insert.assert_called_once_with(ignore_permissions=True)

	def test_reactions_and_messages_without_account_are_ignored(self):
		with patch.object(frappe.db, "get_value") as get_value:
			contact_accounts.touch("WC-1", message(content_type="reaction"), "")
			contact_accounts.touch("WC-1", message(whatsapp_account=None), "Hello")

		get_value.assert_not_called()
