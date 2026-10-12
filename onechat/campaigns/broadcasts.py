import json
import re

import frappe
from frappe import _
from frappe.query_builder.functions import Count, IfNull, Lower, Max
from frappe.utils import add_days, cint, getdate, now_datetime
from pypika.terms import Field

from onechat.api_types import JSON
from onechat.campaigns.smart_send import pending, sender_batches
from onechat.inbox.conversations import CONTACT, digits, find_contact
from onechat.onechat.report.bulk_whatsapp_status.bulk_whatsapp_status import (
    execute as run_status_report,
)
from onechat.workspace.session import is_admin, require


def ensure_read():
    from onechat.workspace.session import require_read

    require_read("Bulk WhatsApp Message")


def ensure_admin():
    if not is_admin():
        frappe.throw(
            _("Only OneChat admins can manage campaigns"), frappe.PermissionError
        )


def status_counts(name):
    message = frappe.qb.DocType("OneChat Message")
    status = Lower(IfNull(message.status, ""))
    rows = (
        frappe.qb.from_(message)
        .select(status.as_("status"), Count("*").as_("count"))
        .where(message.bulk_message_reference == name)
        .groupby(status)
        .run(as_dict=True)
    )

    return {row.status or "queued": cint(row.count) for row in rows}


@frappe.whitelist()
def broadcast(name: str, limit: int | str = 500):
    ensure_admin()
    ensure_read()
    doc = frappe.get_doc("Bulk WhatsApp Message", name)
    counts = status_counts(name)
    total = cint(doc.recipient_count)
    sent = sum(counts.get(key, 0) for key in ("sent", "delivered", "read", "success"))
    failed = counts.get("failed", 0)

    messages = frappe.get_all(
        "OneChat Message",
        filters={"bulk_message_reference": name},
        fields=["name", "to", "status", "creation", "modified"],
        order_by="creation desc",
        limit_page_length=cint(limit) or 500,
    )

    return {
        "doc": {
            key: value
            for key, value in doc.as_dict().items()
            if key not in ("smart_queue", "ab_remaining")
        },
        "counts": counts,
        "progress": {
            "total": total,
            "sent": sent,
            "failed": failed,
            "skipped": cint(doc.get("skipped_count")),
            "queued": counts.get("queued", 0),
            "delivered": counts.get("delivered", 0),
            "read": counts.get("read", 0),
            "percent": (
                min(
                    100,
                    round(
                        (sent + failed + cint(doc.get("skipped_count"))) / total * 100
                    ),
                )
                if total
                else 0
            ),
        },
        "messages": messages,
        "smart_pending": pending(doc),
    }


@frappe.whitelist()
def recipient_counts(names: JSON = None):
    ensure_admin()
    names = frappe.parse_json(names) or []
    if not names:
        return {}

    recipient = frappe.qb.DocType("WhatsApp Recipient")
    rows = (
        frappe.qb.from_(recipient)
        .select(recipient.parent, Count("*").as_("count"))
        .where(
            (recipient.parenttype == "WhatsApp Recipient List")
            & recipient.parent.isin(names)
        )
        .groupby(recipient.parent)
        .run(as_dict=True)
    )

    return {row.parent: cint(row.count) for row in rows}


@frappe.whitelist()
def doctype_fields(doctype: str):
    ensure_admin()
    skip = {
        "Section Break",
        "Column Break",
        "Tab Break",
        "Table",
        "Table MultiSelect",
        "HTML",
        "Button",
        "Image",
        "Fold",
        "Heading",
    }
    meta = frappe.get_meta(doctype)
    fields = [
        {"fieldname": "name", "label": _("ID"), "fieldtype": "Data", "options": ""}
    ]
    for field in meta.fields:
        if field.fieldtype in skip:
            continue
        fields.append(
            {
                "fieldname": field.fieldname,
                "label": _(field.label or field.fieldname),
                "fieldtype": field.fieldtype,
                "options": field.options or "",
            }
        )

    return fields


@frappe.whitelist()
def delivery_report(filters: JSON = None):
    ensure_admin()
    filters = frappe._dict(frappe.parse_json(filters) or {})
    if filters.get("from_date") and not filters.get("to_date"):
        filters.to_date = str(getdate())
    if filters.get("to_date") and not filters.get("from_date"):
        filters.from_date = "2000-01-01"
    if filters.get("to_date"):
        filters.to_date = f"{add_days(filters.to_date, 1)}"

    columns, rows = run_status_report(filters)
    totals = {
        key: sum(cint(row.get(key)) for row in rows)
        for key in (
            "recipient_count",
            "sent_count",
            "delivered_count",
            "read_count",
            "failed_count",
        )
    }

    return {"columns": columns, "rows": rows, "totals": totals}


@frappe.whitelist()
def cancel_schedule(name: str):
    ensure_admin()
    require("Bulk WhatsApp Message", "write")
    doc = frappe.get_doc("Bulk WhatsApp Message", name)
    if doc.docstatus != 0:
        frappe.throw(_("Only draft broadcasts can be unscheduled"))

    doc.db_set("scheduled_time", None)
    return True


def send_due_broadcasts():
    due = frappe.get_all(
        "Bulk WhatsApp Message",
        filters={"docstatus": 0, "scheduled_time": ["<=", now_datetime()]},
        pluck="name",
    )

    for name in due:
        try:
            frappe.get_doc("Bulk WhatsApp Message", name).submit()
            frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit each scheduled broadcast submission
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Scheduled broadcast {name} failed")

    from onechat.campaigns.smart_send import release_due

    try:
        release_due()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="Smart send release failed")


AUDIENCES = {
    "read_no_reply": "Read, no reply",
    "no_reply": "No reply",
    "not_read": "Not read",
}
REACHED = ("sent", "delivered", "read", "success")


def audiences(name):
    account = frappe.db.get_value("Bulk WhatsApp Message", name, "whatsapp_account")
    message = frappe.qb.DocType("OneChat Message")
    rows = (
        frappe.qb.from_(message)
        .select(
            message.to,
            Lower(IfNull(message.status, "")).as_("status"),
            message.creation,
        )
        .where((message.bulk_message_reference == name) & (message.type == "Outgoing"))
        .run(as_dict=True)
    )
    sent = {}
    for row in rows:
        if row.status in REACHED and digits(row.to):
            sent[digits(row.to)] = row
    if not sent:
        return {key: [] for key in AUDIENCES}

    sender = Field("from", table=message)
    since = min(row.creation for row in sent.values())
    last = {}
    for batch in sender_batches([row.to for row in sent.values()]):
        condition = (
            (message.type == "Incoming")
            & (message.creation >= since)
            & sender.isin(batch)
        )
        if account:
            condition = condition & (message.whatsapp_account == account)
        for row in (
            frappe.qb.from_(message)
            .select(sender.as_("sender"), Max(message.creation).as_("at"))
            .where(condition)
            .groupby(sender)
            .run(as_dict=True)
        ):
            key = digits(row.sender)
            last[key] = max(last.get(key) or row.at, row.at)

    out = {key: [] for key in AUDIENCES}
    for number, row in sent.items():
        if last.get(number) and last[number] > row.creation:
            continue
        out["no_reply"].append(number)
        if row.status == "read":
            out["read_no_reply"].append(number)
        elif row.status == "delivered":
            out["not_read"].append(number)
    return out


@frappe.whitelist()
def follow_up_counts(name: str):
    ensure_admin()
    ensure_read()
    return {key: len(numbers) for key, numbers in audiences(name).items()}


def follow_up_variables(source, template):
    if template == source.template:
        return source.template_variables
    body = frappe.db.get_value("WhatsApp Templates", template, "template") or ""
    count = len(set(re.findall(r"\{\{\s*(\d+)\s*\}\}", body)))
    if not count:
        return None
    if count == 1:
        return json.dumps({"1": "recipient.recipient_name"})
    frappe.throw(
        _(
            "Template {0} needs {1} values that a follow-up can't fill. Keep the original template, or pick one with at most one value (it gets the person's name)."
        ).format(frappe.bold(template), count)
    )


@frappe.whitelist(methods=["POST"])
def create_follow_up(name: str, audience: str, template: str | None = None):
    ensure_admin()
    require("Bulk WhatsApp Message", "create")
    if audience not in AUDIENCES:
        frappe.throw(_("Choose who to follow up with."))
    source = frappe.get_doc("Bulk WhatsApp Message", name)
    wanted = set(audiences(name)[audience])
    if not wanted:
        frappe.throw(_("Nobody matches this audience yet."))
    template = template or source.template
    variables = follow_up_variables(source, template)

    rows, seen = [], set()
    for row in source.all_recipients():
        key = digits(row.get("mobile_number"))
        if key in wanted and key not in seen:
            seen.add(key)
            rows.append(
                {
                    "mobile_number": row.get("mobile_number"),
                    "recipient_name": row.get("recipient_name"),
                    "recipient_data": row.get("recipient_data"),
                }
            )
    for number in sorted(wanted - seen):
        contact = find_contact(number)
        rows.append(
            {
                "mobile_number": number,
                "recipient_name": (
                    frappe.db.get_value(CONTACT, contact, "contact_name")
                    if contact
                    else None
                ),
            }
        )

    doc = frappe.get_doc(
        {
            "doctype": "Bulk WhatsApp Message",
            "title": _("{0} · follow-up").format((source.title or source.name)[:120]),
            "whatsapp_account": source.whatsapp_account,
            "use_template": 1,
            "template": template,
            "template_variables": variables,
            "recipient_type": "Individual",
            "recipients": rows,
            "follow_up_of": source.name,
            "follow_up_audience": AUDIENCES[audience],
        }
    ).insert()
    return doc.name
