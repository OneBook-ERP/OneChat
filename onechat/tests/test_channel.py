import frappe
from frappe.tests import IntegrationTestCase

from onechat.inbox import conversations

WHATSAPP = "OneChat Channel Test WhatsApp"
INSTAGRAM = "OneChat Channel Test Instagram"
IGSID = "17841400000099999"


def make_account(name, channel):
	if not frappe.db.exists("OneChat Account", name):
		frappe.get_doc(
			{
				"doctype": "OneChat Account",
				"name": name,
				"account_name": name,
				"status": "Active",
				"channel": channel,
			}
		).db_insert()


def incoming(account, party, profile="Test"):
	return frappe._dict(type="Incoming", whatsapp_account=account, profile_name=profile, **{"from": party})


class TestChannelMatching(IntegrationTestCase):
	def setUp(self):
		make_account(WHATSAPP, "WhatsApp")
		make_account(INSTAGRAM, "Instagram")

	def test_instagram_message_creates_an_instagram_contact(self):
		name = conversations.ensure_contact(incoming(INSTAGRAM, IGSID, "Asha"))

		contact = frappe.get_doc("OneChat Contact", name)
		self.assertEqual(contact.instagram_id, IGSID)
		self.assertEqual(contact.channel, "Instagram")
		self.assertFalse(contact.mobile_no)
		self.assertEqual(conversations.ensure_contact(incoming(INSTAGRAM, IGSID)), name)

	def test_instagram_id_never_matches_a_whatsapp_number(self):
		whatsapp = conversations.ensure_contact(incoming(WHATSAPP, "91" + IGSID[-10:]))
		instagram = conversations.ensure_contact(incoming(INSTAGRAM, IGSID))

		self.assertNotEqual(whatsapp, instagram)
		self.assertEqual(conversations.find_contact(IGSID), whatsapp)
		self.assertEqual(conversations.find_instagram_contact(IGSID, INSTAGRAM), instagram)

	def test_whatsapp_lookup_skips_instagram_contacts_with_a_phone(self):
		instagram = conversations.ensure_contact(incoming(INSTAGRAM, "17841400000088888"))
		frappe.db.set_value(
			"OneChat Contact", instagram, {"mobile_no": "919811122233", "wa_number": "919811122233"}
		)

		self.assertIsNone(conversations.find_contact("919811122233"))

	def test_profile_name_replaces_a_number_used_as_the_name(self):
		number = "919811100001"
		name = conversations.ensure_contact(incoming(WHATSAPP, number, profile=None))
		self.assertEqual(frappe.db.get_value("OneChat Contact", name, "contact_name"), number)

		conversations.refresh_name(name, "Aadhi")
		self.assertEqual(frappe.db.get_value("OneChat Contact", name, "contact_name"), "Aadhi")

		conversations.refresh_name(name, "Someone Else")
		self.assertEqual(frappe.db.get_value("OneChat Contact", name, "contact_name"), "Aadhi")

	def test_channel_follows_the_account(self):
		self.assertEqual(conversations.channel_of(frappe._dict(whatsapp_account=INSTAGRAM)), "Instagram")
		self.assertEqual(conversations.channel_of(frappe._dict(whatsapp_account=WHATSAPP)), "WhatsApp")
		self.assertEqual(conversations.channel_of(frappe._dict()), "WhatsApp")
