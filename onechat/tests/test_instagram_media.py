from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from onechat.instagram import media, send, webhook


class TestInstagramMediaLinks(IntegrationTestCase):
	def setUp(self):
		self.file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"secret-{frappe.generate_hash(length=6)}.png",
				"is_private": 1,
				"content": b"\x89PNG\r\n\x1a\nfake",
			}
		).save(ignore_permissions=True)

	def token_of(self, url):
		return url.split("token=")[1]

	def test_private_file_is_shared_by_an_expiring_link_not_a_public_copy(self):
		before = frappe.db.count("File", {"is_private": 0})
		url = send.public_url(self.file.file_url)

		self.assertIn("/api/method/onechat.instagram.media.fetch?token=", url)
		self.assertEqual(frappe.db.count("File", {"is_private": 0}), before)

		response = media.fetch(self.token_of(url))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.mimetype, "image/png")
		self.assertEqual(response.get_data(), b"\x89PNG\r\n\x1a\nfake")

	def test_unknown_or_expired_token_is_not_found(self):
		self.assertEqual(media.fetch("nope").status_code, 404)
		url = media.share(self.file.file_url)
		frappe.cache().delete_value(media.token_key(self.token_of(url)))
		self.assertEqual(media.fetch(self.token_of(url)).status_code, 404)


class TestInstagramEchoDedup(IntegrationTestCase):
	def test_echo_of_a_onechat_send_is_skipped(self):
		mid = f"m.{frappe.generate_hash(length=8)}"
		with patch.object(send.graph, "send", return_value={"message_id": mid}):
			send.post(frappe._dict(), {"recipient": {"id": "1"}, "message": {"text": "Hi"}})

		self.assertTrue(send.sent_by_onechat(mid))
		with patch.object(webhook, "insert") as insert:
			webhook.receive_echo({"recipient": {"id": "1"}, "message": {"mid": mid, "is_echo": True}}, "any")
		insert.assert_not_called()
