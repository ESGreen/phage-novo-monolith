# Content And Media Security

## Purpose

This document defines how V1 handles Markdown, rendered HTML, links, images, uploads, and media URLs.

The goal is to let admins and members write useful content without allowing unsafe HTML, script execution, or risky file uploads.

## Core Rules

- Markdown is allowed.
- Raw HTML is not trusted.
- Rendered Markdown must be sanitized before display.
- Member profile bios use Markdown.
- Content pages use Markdown.
- Dashboard pre/post content comes from Markdown content pages.
- V1 media uploads are image-only.
- V1 does not resize images.
- If an image needs resizing, resize it offline before upload.
- V1 does not store image width/height metadata.
- V1 uses one flat media folder.

## Recommended Libraries

Markdown rendering:

```text
markdown
```

HTML sanitization:

```text
bleach
```

Image validation:

```text
Pillow
```

Use Django upload handling for file upload plumbing.

## Markdown Fields

Markdown fields:

- `MemberProfile.bio_markdown`
- `ContentPage.body_markdown`

Markdown rendering should happen through one shared helper.

Example helper concept:

```text
render_markdown(markdown_text) -> safe_html
```

Rules:

- Do not render Markdown directly in templates.
- Do not mark Markdown output safe until after sanitization.
- Do not allow per-page sanitizer overrides in V1.

## Rendering Pipeline

The safe rendering pipeline should be:

1. Escape or neutralize raw HTML from the source Markdown.
2. Render Markdown to HTML with the shared Markdown configuration.
3. Sanitize the rendered HTML with the shared allowlist.
4. Mark only the sanitized HTML as safe for templates.

Raw HTML must not be trusted just because it appears in Markdown source.

## Allowed Markdown Features

Support normal Markdown:

- Headings.
- Paragraphs.
- Bold and italic text.
- Ordered and unordered lists.
- Blockquotes.
- Inline code.
- Code blocks.
- Links.
- Images.
- Horizontal rules.
- Pipe tables.

Pipe tables are the normal Markdown table syntax using `|` and `---` separators.

Raw HTML tables are not a V1 feature. Table HTML tags are allowed only so Markdown-generated pipe tables can render after raw HTML has been neutralized.

## Raw HTML

Raw HTML in Markdown should not be trusted.

Preferred behavior:

- Escape or neutralize raw HTML before Markdown rendering.
- Let the Markdown renderer produce HTML from Markdown syntax.
- Let the sanitizer strip any disallowed tags and attributes after rendering.
- Script/event/style content must not survive rendering.

Do not allow:

- `<script>`
- `<style>`
- `<iframe>`
- `<object>`
- `<embed>`
- Inline event handlers like `onclick`
- Arbitrary inline styles
- `javascript:` URLs
- `data:` URLs

## Sanitizer Allowlist

Allowed tags:

```text
a
p
br
strong
em
b
ul
ol
li
blockquote
code
pre
hr
h1
h2
h3
h4
h5
h6
img
table
tr
th
td
```

Table tags are included for Markdown pipe tables, not for hand-written raw HTML table editing.

Allowed attributes:

```text
a: href, title, rel, target
img: src, alt, title
th: align
td: align
```

Rules:

- Add `rel="noopener noreferrer"` to external links that open in a new tab.
- Do not allow `style`.
- Do not allow `class` in V1 unless needed later.
- Do not allow `id` in V1 unless needed later.

## Links

Allowed link protocols:

```text
http
https
mailto
```

Internal relative links are allowed.

Examples:

```text
/pages/arrival-info/
/menu/camp-info/
/2026/taxes/
https://example.com
mailto:person@example.com
```

Blocked protocols:

```text
javascript
file
ftp
```

## Images In Markdown

Images may reference:

- Uploaded media under `/media/...`.
- External `https://...` image URLs.

Rules:

- Prefer uploaded media for site-owned images.
- External images are allowed but can break if the remote site changes.
- Image output should be responsive with CSS.
- No custom Markdown image resizing syntax in V1.
- No raw HTML image sizing in V1.

## Media Uploads

V1 uploads are image-only.

Allowed file extensions:

```text
jpg
jpeg
png
gif
webp
```

Allowed MIME types:

```text
image/jpeg
image/png
image/gif
image/webp
```

Validation rules:

- Validate extension.
- Validate MIME/content type.
- Use Pillow to open and verify the image.
- Reject files that Pillow cannot identify as images.
- Reject SVG in V1 because it can contain scripts.
- Reject HTML, PDF, ZIP, Office docs, and arbitrary binary files.

## Upload Size Limits

Recommended V1 limit:

```text
max_image_upload_size_mb = 10
```

Rationale:

- Large enough for normal photos.
- Small enough to avoid accidental huge uploads.
- Admins can resize offline if needed.

## Stored Filenames

Stored filenames should include:

- Media database ID.
- Safe slugified original filename.
- Original safe extension.

Example:

```text
481-phage-map-2026.png
```

Rules:

- Do not trust the original filename.
- Strip path separators.
- Normalize unsafe characters.
- Avoid overwriting existing files.
- Store files in one flat media folder in V1.

## Media URLs

Uploaded files are served from:

```text
/media/<stored_filename>
```

Rules:

- `MediaItem.file_path` is relative to `media_root`.
- Do not store absolute local filesystem paths in Markdown.
- Admin UI should show/copy the `/media/...` URL.
- Markdown content can embed uploaded media using the `/media/...` URL.

## Delete Behavior

When admins delete a `MediaItem`:

- Delete the database record.
- Delete the file from disk.
- Do not soft-delete in V1.

Recovery comes from backups.

If deleted media is still referenced by Markdown, the page may show a broken image. Admins can fix the Markdown manually.

## Profile Photos

Profile photos use `MediaItem`.

Rules:

- Members can replace their profile photo.
- Members cannot self-delete profile photo in V1.
- Admins can change profile photos.
- Profile photo uploads follow the same image validation rules.

## Security Tests

Tests should verify:

- Unsafe HTML is escaped, stripped, or otherwise neutralized.
- Raw HTML tables are not trusted as an authoring feature.
- Markdown pipe tables render safely.
- Event attributes are stripped.
- `javascript:` links are blocked.
- `data:` links are blocked.
- Allowed Markdown renders correctly.
- Uploaded valid images are accepted.
- Non-images are rejected.
- SVG uploads are rejected.
- Oversized images are rejected.
- Stored filenames are safe.
- Deleting media deletes the file and database row.
