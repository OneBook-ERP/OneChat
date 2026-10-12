# Translating OneChat

OneChat can be used in three languages:

| Language | Code | File |
| --- | --- | --- |
| English | `en` | Built in, no file needed |
| Hindi | `hi` | `onechat/locale/hi.po` |
| Arabic | `ar` | `onechat/locale/ar.po` |

Each user picks their language in **Settings → Preferences → Language**. Arabic also switches the screen to right to left.

## The files

All translation files live in `onechat/locale`:

- `main.pot` is the list of every English sentence in OneChat. Don't translate this file; it's the template.
- `hi.po` and `ar.po` hold the translations. This is where you work.

Each entry in a `.po` file looks like this:

```po
#: frontend/src/components/Inbox/Composer.vue:212
msgid "Send message"
msgstr "संदेश भेजें"
```

- `msgid` is the English text. Never change it.
- `msgstr` is your translation. Leave it empty if you're not sure; OneChat then shows the English text.
- Lines starting with `#:` show where the text is used. Lines starting with `#.` explain what it is, for example "Label of a field".

## How to translate

1. Open `hi.po` or `ar.po` in [Poedit](https://poedit.net), which is free, or in any text editor.
2. Fill in the translations. Start with the screens people use most: Inbox, Contacts and Settings.
3. Save the file and send it to us, or open a pull request with the changed file. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Rules

- **Keep placeholders as they are.** `{0}`, `{1}` and so on are filled in by OneChat, for example a name or a number. They can move within the sentence, but don't change or remove them.

  ```po
  msgid "Assigned to {0}"
  msgstr "{0} को असाइन किया गया"
  ```

- **Keep HTML tags** such as `<b>` and `<br>` exactly as they are, around the matching words.
- **Don't translate product names:** OneChat, WhatsApp, Instagram, Meta, ERPNext, Frappe CRM.
- **Keep it short.** Buttons and menu items have little space. Use the everyday word people would say, not a formal or literal one.
- **Be consistent.** Translate the same English word the same way everywhere, for example "Conversation" or "Template".
- **Arabic:** write normally, right to left. Don't add direction marks; OneChat handles the direction.

## For developers

Run these on a bench where OneChat is installed.

| Task | Command |
| --- | --- |
| Refresh `main.pot` after adding or changing text | `bench generate-pot-file --app onechat` |
| Create a language file for the first time | `bench create-po-file hi --app onechat` |
| Add the new text from `main.pot` to `hi.po` and `ar.po` | `bench update-po-files --app onechat` |
| Load the translations so they show up | `bench compile-po-to-mo --app onechat --force`, then `bench clear-cache` |

Wrap every visible text in `_()` in Python and `__()` in the interface, or it can't be translated. The list of languages users can pick is `LANGUAGES` in `onechat/workspace/session.py`.
