frappe.notification = {
	setup_fieldname_select: function (frm) {
		if (!frm.doc.reference_doctype) {
			return;
		}
		frappe.model.with_doctype(frm.doc.reference_doctype, function () {
			let get_select_options = function (df, parent_field) {
				let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;
				let path = parent_field ? parent_field + " > " + df.fieldname : df.fieldname;

				return {
					value: select_value,
					label: path + " (" + __(df.label, null, df.parent) + ")",
				};
			};

			let get_date_change_options = function () {
				let date_options = $.map(fields, function (d) {
					return d.fieldtype == "Date" || d.fieldtype == "Datetime"
						? get_select_options(d)
						: null;
				});
				return date_options.concat([
					{ value: "creation", label: `creation (${__("Created On")})` },
					{ value: "modified", label: `modified (${__("Last Modified Date")})` },
				]);
			};

			let fields = frappe.get_doc("DocType", frm.doc.reference_doctype).fields;
			let options = $.map(fields, function (d) {
				return frappe.model.no_value_type.includes(d.fieldtype)
					? null
					: get_select_options(d);
			});

			frm.set_df_property("date_changed", "options", get_date_change_options());
			frm.set_df_property("value_changed", "options", [""].concat(options));
			frm.set_df_property("set_property_after_alert", "options", [""].concat(options));
		});
	},
	setup_alerts_button: function (frm) {
		frm.add_custom_button(__("Get Alerts for Today"), function () {
			frappe.call({
				method: "onechat.onechat.doctype.whatsapp_notification.whatsapp_notification.call_trigger_notifications",
				args: {
					method: "daily",
				},
				callback: function (response) {
					if (!(response.message && response.message.length > 0)) {
						frappe.msgprint(__("No alerts for today"));
					}
				},
				error: function (error) {
					frappe.msgprint(__("Failed to trigger notifications"));
				},
			});
		});
	},
	toggle_plain_mode: function (frm) {
		const plain = frm.doc.send_plain_message;
		frm.toggle_display("message_body", plain);
		frm.toggle_display("template", !plain);
		frm.toggle_display("code", !plain);
		frm.toggle_display("button_fields", !plain);
		frm.toggle_display("attach_document_print", !plain);
		frm.toggle_display("custom_attachment", !plain);
		frm.toggle_display("attach", !plain);
		frm.toggle_display("attach_from_field", !plain);
		frm.toggle_display("file_name", !plain);
	},
};

frappe.ui.form.on("WhatsApp Notification", {
	refresh: function (frm) {
		frappe.notification.toggle_plain_mode(frm);
		frm.trigger("load_template");
		frappe.notification.setup_fieldname_select(frm);
		frappe.notification.setup_alerts_button(frm);
	},
	send_plain_message: function (frm) {
		frappe.notification.toggle_plain_mode(frm);
		if (!frm.doc.send_plain_message) {
			frm.trigger("load_template");
		} else {
			frm.set_value("template", "");
			frm.set_value("code", "");
			frm.set_value("header_type", "");
		}
	},
	template: function (frm) {
		frm.trigger("load_template");
	},
	load_template: function (frm) {
		if (frm.doc.send_plain_message) return;

		frappe.db.get_value(
			"WhatsApp Templates",
			frm.doc.template,
			["template", "header_type"],
			(r) => {
				if (r && r.template) {
					frm.set_value("header_type", r.header_type);
					frm.refresh_field("header_type");
					if (["DOCUMENT", "IMAGE"].includes(r.header_type)) {
						frm.toggle_display("custom_attachment", true);
						frm.toggle_display("attach_document_print", true);
					} else {
						frm.toggle_display("custom_attachment", false);
						frm.toggle_display("attach_document_print", false);
						frm.set_value("attach_document_print", 0);
						frm.set_value("custom_attachment", 0);
					}

					frm.refresh_field("custom_attachment");

					frm.set_value("code", r.template);
					frm.refresh_field("code");
				}
			}
		);
	},
	custom_attachment: function (frm) {
		if (
			frm.doc.custom_attachment == 1 &&
			["DOCUMENT", "IMAGE"].includes(frm.doc.header_type)
		) {
			frm.set_df_property("file_name", "reqd", frm.doc.custom_attachment);
		} else {
			frm.set_df_property("file_name", "reqd", 0);
		}
		if (frm.doc.header_type) {
			frm.set_value("attach_document_print", !frm.doc.custom_attachment);
		}
	},
	attach_document_print: function (frm) {
		if (["DOCUMENT", "IMAGE"].includes(frm.doc.header_type)) {
			frm.set_value("custom_attachment", !frm.doc.attach_document_print);
		}
	},
	reference_doctype: function (frm) {
		frappe.notification.setup_fieldname_select(frm);
	},
});
