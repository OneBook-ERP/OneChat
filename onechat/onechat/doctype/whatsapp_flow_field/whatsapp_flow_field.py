from frappe.model.document import Document


class WhatsAppFlowField(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		enabled: DF.Check
		error_message: DF.Data | None
		field_name: DF.Data
		field_type: DF.Literal[
			"TextInput",
			"TextArea",
			"DatePicker",
			"RadioButtonsGroup",
			"CheckboxGroup",
			"Dropdown",
			"OptIn",
			"EmbeddedLink",
			"Image",
			"TextHeading",
			"TextSubheading",
			"TextBody",
			"TextCaption",
			"Footer",
			"Form",
		]
		helper_text: DF.Data | None
		init_value: DF.Data | None
		label: DF.Data | None
		max_chars: DF.Int
		min_chars: DF.Int
		options: DF.Code | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		required: DF.Check
		screen: DF.Data
	# end: auto-generated types
	pass
