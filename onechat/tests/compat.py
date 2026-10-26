try:
	from frappe.tests import IntegrationTestCase, UnitTestCase
except ImportError:
	from frappe.tests.utils import FrappeTestCase as IntegrationTestCase
	from frappe.tests.utils import FrappeTestCase as UnitTestCase

__all__ = ["IntegrationTestCase", "UnitTestCase"]
