# StickerHub

[简体中文](readme/README_zh_Hans.md)

A serverless sticker / image host for LangBot. Images are persisted in the
plugin's own **plugin storage** (content-addressed, so identical uploads share
one blob), and the plugin returns a **stable URL** for each stored sticker —
usable from a human reply (the management page) and from AI replies alike.

## Features

- **Serverless image host**: no external service. Bytes live in plugin storage,
  the catalogue is a set of per-sticker metadata rows, and the served copy is
  written to the plugin `assets/stickers/` directory (see
  `materialize_to_assets`).
- **Stable URLs**: `{public_base_url}/api/v1/plugins/langbot-team/StickerHub/assets/stickers/<slug>-<sha12>.<ext>`.
  The filename is derived from the sticker name and the content SHA-256, so the
  same sticker returns the same URL every time it is fetched. The LangBot asset
  route is public on a single-Workspace deployment, so IM platforms and the AI
  can pull the bytes directly.
- **Human replies**: the management page (`components/pages/hub/`) uploads from
  a file picker or an image URL, shows a gallery, and copies the URL.
- **No base64 on the hot path**: the gallery renders `item.url` directly
  (`loading="lazy"`, `decoding="async"`), so a page of stickers costs zero
  preview round trips. `/image` remained the fallback when a served file is
  missing (for example because `materialize_to_assets` is off).
- **Chunked upload**: the page posts the file in 256 KiB base64 slices to
  `/upload/*`, so one page-api request body never grows with the image.
- **Sandbox-safe UI**: the page runs in a `blob:` iframe with
  `sandbox="allow-scripts allow-forms"` — an opaque origin with no modals. Copy
  therefore falls back clipboard → `execCommand` → an in-page sheet and clears
  through an in-page dialog, and asset URLs are made absolute against
  `location.ancestorOrigins[0]` so both the clipboard and `<img>` work.
- **Cheap listing**: one key scan plus one metadata read per sticker serves both
  `/list` and the following `/stats`, instead of two full scans and an extra
  read per row.
- **AI replies**: four Tools let a model store and fetch stickers, and return the
  stable URL as a string.
- **Stable cross-plugin interface**: `stickerhub_get_sticker_url` is the
  contract other plugins call; see [Integration](#integration-with-humantakeover).
- **Per-installation isolation**: stores are scoped by
  `instance:workspace:installation`, so several Workspaces can share one
  shared-runtime object graph safely.
- **Bounded storage**: `max_stickers` evicts the oldest entries when the cap is
  exceeded; every write is bounded by `max_sticker_mb`.
- **No event-loop stalls**: remote downloads and asset writes run on worker
  threads, and remote responses are streamed and size-checked incrementally.

## Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `public_base_url` | string | `""` | Optional public base URL of this LangBot instance. When set, returned URLs are absolute; when empty, a relative `/api/v1/plugins/...` path is returned. |
| `max_sticker_mb` | integer | `8` | Reject images larger than this. Matches the HumanTakeover 8 MiB message budget. |
| `max_stickers` | integer | `2000` | Oldest stickers are evicted once storage exceeds this count. |
| `materialize_to_assets` | boolean | `true` | Also write new stickers to `assets/stickers/` so the public asset route can serve them. |

## Storage layout

ALL plugin storage keys are scoped by the installation, e.g.
`sh:<instance>:<workspace>:<installation>:...`.

| Key | Value |
|-----|-------|
| `sh:<scope>:meta:<slug>` | JSON metadata: slug, name, mime, ext, size, SHA-256, filename, timestamps, source |
| `sh:<scope>:blob:<sha256>` | Raw image bytes, shared by every sticker with that hash |
| `sh:<scope>:upload:<session>:000000` | Upload session marker (`created_at`) |
| `sh:<scope>:upload:<session>:<n>` | One raw upload chunk, `n` counting from 1 |

Adding a sticker writes one new metadata key and, on the first upload of a
hash, one blob key. Updating a sticker rewrites only its metadata row. Deleting
a sticker removes its metadata and, when nothing else references the hash, its
blob. This keeps hot-path work proportional to the change instead of rewriting a
global index.

## Public Page endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/stats` | GET | Count, bytes and per-mime breakdown |
| `/list` | GET | Paginated gallery (`limit`, `offset`) |
| `/item` | GET | One sticker metadata + stable URL (`name`) |
| `/image` | GET | Preview fallback (`name`); add `with_data` for the base64 bytes |
| `/add` | POST | Store from `url` or `data_url` (`name` required) |
| `/upload/begin` | POST | Open a chunked upload session |
| `/upload/chunk` | POST | Append one base64 slice (`session`, `index`, `data`) |
| `/upload/finish` | POST | Assemble the session and store it (`session`, `name`, optional `mime`) |
| `/upload/abort` | POST | Drop an abandoned session (`session`) |
| `/delete` | POST | Remove one sticker (`name`) |
| `/clear` | DELETE | Remove every sticker in this installation |

## Tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `stickerhub_add_sticker` | `name`, optional `url` or `data_url` | JSON `{"ok": true, "sticker": {…}}` |
| `stickerhub_get_sticker_url` | `name` | The stable URL string |
| `stickerhub_list_stickers` | optional `limit` | JSON `{"ok": true, "total", "items": [{name, uri, mime, size}]}` |
| `stickerhub_delete_sticker` | `name` | JSON `{"ok": bool}` |

`stickerhub_get_sticker_url` returns a bare URL string on success and a string
starting with `error:` when the sticker is missing or the call is malformed.

## Integration with HumanTakeover

The plugin exposes the stable interface as a Tool. From HumanTakeover's
execution context:

```python
url = await self.plugin.call_tool(
    "stickerhub_get_sticker_url",
    {"name": sticker_name},
    session,
    query_id,
)
if url and not url.startswith("error:"):
    components.append(platform_message.Image(url=url))
```

`call_tool` requires the `plugin_tools` capability for HumanTakeover's
installation grants. HumanTakeover can also call
`self.plugin.call_tool("stickerhub_add_sticker", {"name", "data_url"})` to
register a sticker before replying.

When both plugins run in the same worker, the Python API is available directly:

| Method | Purpose |
|--------|---------|
| `await add_sticker(name, data, mime, source=...)` | Store bytes, return metadata + URL |
| `await add_sticker_from_url(name, url)` | Bounded remote download + store |
| `await add_sticker_from_base64(name, data_url)` | Store a `data:` URL / base64 |
| `await get_sticker(name)` / `await media_url(name)` | Metadata / stable URL |
| `await list_stickers(limit, offset)` | Paginated page |
| `await delete_sticker(name)` / `await clear_stickers()` | Removal |
| `await sticker_image(name)` | base64 preview (Page / adapters without a public host) |

## Testing

```bash
cd plugins/misc/StickerHub
python -m pytest tests -q
```

The suite drives the real plugin object against a stub Host that records plugin
storage actions, and covers content addressing, deduplication, size limits,
eviction, pagination, installation isolation, URL stability, the Page endpoints
and the tool contract.
