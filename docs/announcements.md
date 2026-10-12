# Announcements

OneChat shows a small announcement card in the bottom-right corner of the app. It is used for product news, offers, maintenance notices and "update available" messages.

Announcements are not stored in any site. Every OneChat site reads one public JSON file from the `announcements` branch of this repository:

```
https://raw.githubusercontent.com/OneBook-ERP/OneChat/announcements/announcements.json
```

Each site's server fetches the file at most every 15 minutes and serves it to its own users. Browsers never call GitHub directly, and nothing is ever sent back. It is a single GET request.

## One-time setup

The `announcements` branch holds only the feed. It is never merged into `develop`, `main` or the `version-*` branches, and they are never merged into it.

```bash
git checkout --orphan announcements
git rm -rf .
# add announcements.json, validate.py, README.md and .github/workflows/validate.yml
git add .
git commit -m "Announcements feed"
git push -u origin announcements
git checkout develop
```

The branch contains:

| File | Purpose |
| --- | --- |
| `announcements.json` | The feed every site reads |
| `validate.py` | Checks the feed for mistakes |
| `.github/workflows/validate.yml` | Runs the check on every push and pull request |
| `README.md` | Field reference for whoever edits the feed |

The repository must stay **public**. Raw files of a private repository need a token, and customer sites cannot read them.

Optionally, protect the branch so changes need a pull request with one approval.

## Publishing an announcement

1. On GitHub, switch to the `announcements` branch and open `announcements.json`.
2. Click the pencil icon, add or change an entry, and commit.
3. Wait for the **Validate announcements** check to turn green. If it is red, open it to see what to fix.
4. Sites show the change within about 20 minutes: up to 5 minutes of GitHub caching plus up to 15 minutes of OneChat caching.

To take an announcement down, set `"enabled": false` or delete the entry.

## File format

```json
{
  "updates": [
    { "versions": ["16"], "version": "1.4.0", "url": "https://github.com/OneBook-ERP/OneChat/releases" },
    { "versions": ["15"], "version": "1.3.2", "url": "https://github.com/OneBook-ERP/OneChat/releases" }
  ],
  "announcements": [
    {
      "id": "maintenance-2026-11-02",
      "title": "Scheduled maintenance",
      "body": "OneChat will be unavailable on Sunday from 2:00 to 2:30 am.",
      "theme": "warning",
      "starts_at": "2026-10-30 00:00:00",
      "ends_at": "2026-11-02 02:30:00"
    }
  ]
}
```

A plain list of announcements, without `updates`, also works.

### Announcement fields

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Unique and never reused. Dismissals are remembered by it |
| `title` | for cards | Headline |
| `body` | no | Text under the title |
| `type` | no | `card` (default), `image`, `video` or `html` |
| `theme` | no | `new`, `info`, `success`, `warning` or `ad`. Shown as a small coloured dot |
| `label` | no | Small text above the title, such as `Offer` or `Sponsored` |
| `media` | image, video | `{ "src": "https://…", "aspect": "16/9", "poster": "https://…" }`. Videos take YouTube or Vimeo links |
| `html`, `height`, `expanded_height` | html | A custom HTML banner and its heights in pixels |
| `action` | no | `{ "label": "Learn more", "url": "https://…" }` |
| `audience` | no | `Everyone` (default) or `Admins only` |
| `versions` | no | Frappe major versions it shows on, such as `["15", "16"]` |
| `min_version`, `max_version` | no | OneChat versions it shows on, inclusive, such as `"max_version": "1.3.9"` |
| `starts_at`, `ends_at` | no | Format `2026-12-31 23:59:59` |
| `dismissible` | no | `false` keeps it visible until it ends |
| `enabled` | no | `false` hides it without deleting it |

### Update fields

Each entry in `updates` describes the latest OneChat release for one Frappe major version. Admins on an older OneChat version see "OneChat 1.4.0 is available" until they update; agents never see it.

| Field | Required | Meaning |
| --- | --- | --- |
| `version` | yes | Latest OneChat version on that branch |
| `versions` | no | The Frappe major version, such as `["16"]`. Keep one entry per Frappe version, or one entry without `versions` for all |
| `title`, `body` | no | Custom text instead of the default |
| `url`, `label` | no | Release notes link and its button text (default "What's new") |

## Versions

There are two kinds of version, and they can be combined:

- **Frappe version** (`versions`): the site's Frappe major version, `15` or `16`.
- **OneChat app version** (`min_version`, `max_version`, and `updates[].version`): the value of `__version__` in `onechat/__init__.py`.

Versions are compared numerically, so `1.10.0` is newer than `1.9.0`.

## Release checklist

1. Bump `__version__` in `onechat/__init__.py` on the release branch.
2. Tag and publish the release.
3. On the `announcements` branch, set the `version` of that branch's `updates` entry to the new version.

## Rules

- Never reuse an `id`. Use readable ids such as `offer-diwali-2026`.
- Always set `ends_at` on offers and notices so they expire on their own.
- Remove expired entries about once a month. Git history keeps them.
- Only ever add new optional fields to the format. Never rename or remove fields, because older OneChat versions keep reading this file.

## Site settings

Each site can override the source in `site_config.json`:

```json
{ "onechat_announcement_source": "https://example.com/announcements.json" }
```

Set it to `""` to turn announcements off for that site. Any public URL that returns the JSON format above works.

### Private feed repository

If the feed lives in a private repository, give each site a read-only key:

1. Keep the feed in its **own** repository, never in the OneChat code repository. Any key you hand to customer sites can be read by their server admins, so it must not unlock your code.
2. In GitHub, create a fine-grained personal access token with **Only select repositories** set to the feed repository and **Contents: Read-only**. Give it a long expiry and note the date.
3. Add both settings to each site's `site_config.json`:

```json
{
  "onechat_announcement_source": "https://raw.githubusercontent.com/OneBook-ERP/onechat-announcements/main/announcements.json",
  "onechat_announcement_token": "github_pat_…"
}
```

The key is only sent to `raw.githubusercontent.com` and `api.github.com`. Before it expires, create a new one and update the sites. A public feed repository needs no key at all.

## Previewing

Open OneChat with `?preview_announcement` in the URL to see sample announcements of every type, without touching the live feed.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Nothing shows | The entry is `enabled`, inside its dates, and matches the site's versions and audience |
| Change not visible yet | Wait up to 20 minutes, or clear the site cache with `bench --site <site> clear-cache` |
| Feed broken after an edit | The **Validate announcements** check shows the exact problem. A broken file never breaks the app; it simply shows nothing |
| A user no longer sees an announcement | They dismissed it. Publish it again with a new `id` |
