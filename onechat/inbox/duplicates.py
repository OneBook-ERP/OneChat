import json
import re

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import cint, get_datetime

from onechat.inbox.conversations import (
    CONTACT,
    CONTACT_LABEL,
    MESSAGE,
    digits,
    guard,
    publish,
)
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import links
from onechat.workspace.audit import track
from onechat.workspace.session import require_admin

SETTINGS = "OneChat Settings"
AUTOMATIC = "Automatic"
GROUP_LIMIT = 10
FIELDS = [
    "name",
    "contact_name",
    "mobile_no",
    "wa_number",
    "other_numbers",
    "email",
    "reference_doctype",
    "reference_docname",
    "profile_image",
    "last_message_at",
    "creation",
    "opted_out",
]
STRONG = {"phone"}
EVIDENCE = {"phone", "email", "record"}
REASONS = {
    "phone": "Same phone number",
    "email": "Same email",
    "record": "Linked to the same record",
    "name": "Same name",
}


def setting(field):
    meta = frappe.get_meta(SETTINGS)
    return (
        frappe.db.get_single_value(SETTINGS, field) if meta.has_field(field) else None
    )


def automatic():
    return setting("duplicate_merge") == AUTOMATIC


def ignored():
    try:
        return set(json.loads(setting("ignored_duplicates") or "[]"))
    except ValueError:
        return set()


def pair_key(first, second):
    return "|".join(sorted((first, second)))


def phones(row):
    numbers = [row.get("wa_number") or digits(row.get("mobile_no"))] + [
        line for line in (row.get("other_numbers") or "").split()
    ]
    return {digits(number)[-10:] for number in numbers if len(digits(number)) >= 10}


def person_name(row):
    text = re.sub(r"[^a-z]+", " ", (row.get("contact_name") or "").lower()).strip()
    return text if len(text.replace(" ", "")) >= 5 else None


def keys_of(row):
    out = [("phone", number) for number in phones(row)]
    if row.get("email"):
        out.append(("email", row["email"].strip().lower()))
    if row.get("reference_doctype") and row.get("reference_docname"):
        out.append(
            ("record", f"{row['reference_doctype']}::{row['reference_docname']}")
        )
    name = person_name(row)
    if name:
        out.append(("name", name))
    return out


def find_pairs(rows):
    groups = {}
    for row in rows:
        for key in keys_of(row):
            groups.setdefault(key, []).append(row["name"])
    pairs = {}
    for (kind, _value), names in groups.items():
        names = sorted(set(names))
        if len(names) < 2 or len(names) > GROUP_LIMIT:
            continue
        for index, first in enumerate(names):
            for second in names[index + 1 :]:
                pairs.setdefault(pair_key(first, second), set()).add(kind)
    return {key: kinds for key, kinds in pairs.items() if kinds & EVIDENCE}


def confident(reasons):
    return (
        bool(reasons & STRONG)
        or reasons >= {"email", "name"}
        or reasons >= {"record", "name"}
    )


def keeper(first, second):
    def rank(row):
        return (
            1 if row.get("reference_docname") else 0,
            get_datetime(row.get("last_message_at") or "1900-01-01"),
            (
                -get_datetime(row.get("creation")).timestamp()
                if row.get("creation")
                else 0
            ),
        )

    return (first, second) if rank(first) >= rank(second) else (second, first)


def all_rows():
    return frappe.get_all(CONTACT, fields=FIELDS, limit_page_length=0)


@frappe.whitelist()
def suggestions(limit: int | str = 100):
    guard()
    rows = {row.name: row for row in all_rows()}
    skip = ignored()
    counts = message_counts(list(rows))
    out = []
    for key, reasons in find_pairs(rows.values()).items():
        if key in skip:
            continue
        first, second = (rows[name] for name in key.split("|"))
        keep, merge = keeper(first, second)
        out.append(
            {
                "key": key,
                "reasons": [
                    {"kind": kind, "label": _(REASONS[kind])}
                    for kind in ("phone", "record", "email", "name")
                    if kind in reasons
                ],
                "confident": confident(reasons),
                "keep": card(keep, counts),
                "merge": card(merge, counts),
            }
        )
    out.sort(key=lambda row: (not row["confident"], row["keep"]["contact_name"] or ""))
    return {
        "pairs": out[: cint(limit) or 100],
        "total": len(out),
        "mode": setting("duplicate_merge") or "Manual",
    }


def message_counts(names):
    if not names:
        return {}
    message = frappe.qb.DocType(MESSAGE)
    rows = (
        frappe.qb.from_(message)
        .select(message.whatsapp_contact, Count(message.name).as_("total"))
        .where(message.whatsapp_contact.isin(list(names)))
        .groupby(message.whatsapp_contact)
        .run(as_dict=True)
    )
    return {row.whatsapp_contact: cint(row.total) for row in rows}


def card(row, counts):
    return {
        "name": row.name,
        "contact_name": row.contact_name,
        "mobile_no": row.mobile_no,
        "email": row.email,
        "reference_doctype": row.reference_doctype,
        "reference_docname": row.reference_docname,
        "profile_image": row.profile_image,
        "last_message_at": str(row.last_message_at) if row.last_message_at else None,
        "messages": counts.get(row.name, 0),
    }


@frappe.whitelist()
def ignore(key: str):
    require_admin()
    names = [name for name in (key or "").split("|") if name]
    if len(names) != 2:
        frappe.throw(_("Pick two contacts."))
    skip = ignored()
    skip.add(pair_key(*names))
    frappe.db.set_single_value(SETTINGS, "ignored_duplicates", json.dumps(sorted(skip)))
    return True


@frappe.whitelist()
def get_mode():
    require_admin()
    return setting("duplicate_merge") or "Manual"


@frappe.whitelist()
def set_mode(mode: str):
    require_admin()
    if mode not in ("Manual", AUTOMATIC):
        frappe.throw(_("Pick Manual or Automatic."))
    frappe.db.set_single_value(SETTINGS, "duplicate_merge", mode)
    if mode == AUTOMATIC:
        frappe.enqueue(
            "onechat.inbox.duplicates.merge_all",
            queue="long",
            enqueue_after_commit=True,
        )
    return mode


def union(*values):
    seen = []
    for value in values:
        for line in (value or "").split():
            if line and line not in seen:
                seen.append(line)
    return "\n".join(seen)


@frappe.whitelist(methods=["POST"])
def merge(keep: str, duplicate: str):
    require_admin()
    check_visible(keep)
    check_visible(duplicate)
    return merge_contacts(keep, duplicate)


def merge_contacts(keep, duplicate):
    if keep == duplicate:
        frappe.throw(_("Pick two different contacts."))
    first = frappe.get_doc(CONTACT, keep)
    second = frappe.get_doc(CONTACT, duplicate)

    updates = {}
    if (
        not first.contact_name
        or first.contact_name == first.mobile_no
        or digits(first.contact_name) == first.wa_number
    ):
        if second.contact_name and digits(second.contact_name) != second.wa_number:
            updates["contact_name"] = second.contact_name
    for field in ("email", "profile_image"):
        if not first.get(field) and second.get(field):
            updates[field] = second.get(field)
    if not first.reference_docname and second.reference_docname:
        updates.update(
            reference_doctype=second.reference_doctype,
            reference_docname=second.reference_docname,
        )
    if not first.assigned_to and second.assigned_to:
        updates["assigned_to"] = second.assigned_to
    if cint(second.opted_out) and not cint(first.opted_out):
        updates.update(opted_out=1, opted_out_at=second.opted_out_at)
    if (second.last_message_at or "") and str(second.last_message_at) > str(
        first.last_message_at or ""
    ):
        updates.update(
            last_message=second.last_message,
            last_message_at=second.last_message_at,
            last_message_type=second.last_message_type,
        )
    if second.conversation_status == "Open":
        updates["conversation_status"] = "Open"
    updates["unread_count"] = cint(first.unread_count) + cint(second.unread_count)
    numbers = union(
        first.other_numbers,
        second.wa_number if second.wa_number != first.wa_number else "",
        second.other_numbers,
    )
    updates["other_numbers"] = numbers or None
    labels = [row.label for row in first.labels] + [
        row.label
        for row in second.labels
        if row.label not in {item.label for item in first.labels}
    ]
    kept = links.of(first)
    records = kept + [
        frappe._dict(row, main=0)
        for row in links.of(second)
        if (row.doctype, row.name) not in {(item.doctype, item.name) for item in kept}
    ]

    frappe.db.set_value(CONTACT, keep, updates, update_modified=False)
    frappe.rename_doc(
        CONTACT, duplicate, keep, merge=True, force=True, show_alert=False
    )
    frappe.db.delete(
        CONTACT_LABEL, {"parenttype": CONTACT, "parentfield": "labels", "parent": keep}
    )
    for index, label in enumerate(labels, start=1):
        frappe.get_doc(
            {
                "doctype": CONTACT_LABEL,
                "parent": keep,
                "parenttype": CONTACT,
                "parentfield": "labels",
                "idx": index,
                "label": label,
            }
        ).db_insert()
    frappe.db.delete(links.LINK, {"parenttype": CONTACT, "parent": keep})
    for row in records:
        links.add(keep, row.doctype, row.name, main=bool(row.main))

    track(CONTACT, keep, [("merged", duplicate, keep)])
    publish(keep)
    frappe.publish_realtime(
        "onechat_inbox",
        {"removed": duplicate},
        room=f"doctype:{CONTACT}",
        after_commit=True,
    )
    try:
        from onechat.inbox.scores import queue_update

        queue_update(keep)
    except Exception:
        pass
    return keep


def merge_all():
    if not automatic():
        return 0
    merged = 0
    skip = ignored()
    rows = {row.name: row for row in all_rows()}
    for key, reasons in find_pairs(rows.values()).items():
        if key in skip or not reasons & STRONG:
            continue
        first, second = (rows.get(name) for name in key.split("|"))
        if (
            not first
            or not second
            or not frappe.db.exists(CONTACT, first.name)
            or not frappe.db.exists(CONTACT, second.name)
        ):
            continue
        keep, duplicate = keeper(first, second)
        try:
            merge_contacts(keep.name, duplicate.name)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit each automatic duplicate contact merge
            merged += 1
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"OneChat duplicate merge: {key}")
    return merged


def on_contact_insert(doc, method=None):
    if not automatic():
        return
    frappe.enqueue(
        "onechat.inbox.duplicates.merge_all",
        queue="long",
        enqueue_after_commit=True,
        deduplicate=True,
        job_id="onechat-merge-duplicates",
    )


@frappe.whitelist()
def for_contact(contact: str):
    guard()
    check_visible(contact)
    row = frappe.db.get_value(CONTACT, contact, FIELDS, as_dict=True)
    if not row:
        return []
    skip = ignored()
    others = {}
    for kind, value in keys_of(row):
        if kind == "phone":
            candidates = frappe.get_all(
                CONTACT,
                filters={"wa_number": ["like", f"%{value}"], "name": ["!=", contact]},
                pluck="name",
            )
            candidates += frappe.get_all(
                CONTACT,
                filters={
                    "other_numbers": ["like", f"%{value}%"],
                    "name": ["!=", contact],
                },
                pluck="name",
            )
        elif kind == "email":
            candidates = frappe.get_all(
                CONTACT, filters={"email": value, "name": ["!=", contact]}, pluck="name"
            )
        elif kind == "record":
            doctype, name = value.split("::", 1)
            candidates = [
                other for other in links.contacts_for(doctype, name) if other != contact
            ]
        else:
            continue
        for name in candidates[:GROUP_LIMIT]:
            if pair_key(contact, name) not in skip:
                others.setdefault(name, set()).add(kind)
    return [
        {
            "name": name,
            "contact_name": frappe.db.get_value(CONTACT, name, "contact_name"),
            "reasons": [_(REASONS[kind]) for kind in sorted(kinds)],
        }
        for name, kinds in others.items()
    ]
