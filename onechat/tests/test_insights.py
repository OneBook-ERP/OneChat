from collections import Counter

from frappe.tests import UnitTestCase

from onechat.insights.metrics import bands, delivery, last_line, ranked, slots, window


class TestInsightsHelpers(UnitTestCase):
	def test_short_ranges_are_hourly(self):
		self.assertTrue(window("24").hourly)
		self.assertFalse(window("168").hourly)

	def test_custom_range_orders_dates(self):
		span = window("custom", "2026-09-20 23:59:59", "2026-09-10 00:00:00")

		self.assertLess(span.since, span.until)
		self.assertEqual(span.since - span.previous, span.until - span.since)

	def test_slots_cover_every_day(self):
		span = window("custom", "2026-09-01 00:00:00", "2026-09-07 23:59:59")

		self.assertEqual(slots(span), [f"2026-09-0{day}" for day in range(1, 8)])

	def test_response_bands(self):
		counts = {row["name"]: row["value"] for row in bands([30, 299, 300, 1200, 7200, 90000])}

		self.assertEqual(counts["Under 5 min"], 2)
		self.assertEqual(counts["5–15 min"], 1)
		self.assertEqual(counts["15–60 min"], 1)
		self.assertEqual(counts["1–4 hours"], 1)
		self.assertEqual(counts["Over a day"], 1)

	def test_delivery_rates(self):
		result = delivery(Counter({"read": 3, "delivered": 1, "sent": 1, "failed": 1}))

		self.assertEqual(result["sent"], 6)
		self.assertEqual(result["delivered"], 4)
		self.assertEqual(result["read_rate"], 75.0)
		self.assertIsNone(delivery(Counter())["read_rate"])

	def test_ranked_drops_zero_and_names_blank(self):
		self.assertEqual(
			ranked({"": 2, "Agent": 5, "Bot": 0}),
			[{"name": "Agent", "value": 5}, {"name": "Other", "value": 2}],
		)

	def test_last_line_of_traceback(self):
		self.assertEqual(last_line("Traceback\n  File x\nValueError: bad\n"), "ValueError: bad")
		self.assertEqual(last_line("   "), "")
