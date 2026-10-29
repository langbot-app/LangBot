"""ACP prompt content block conversion helpers."""

from __future__ import annotations

import base64
import binascii
import mimetypes
import typing
import urllib.parse


def _attachment_get(attachment: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(attachment, dict):
        return attachment.get(key, default)
    return getattr(attachment, key, default)


def _content_get(content: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(content, dict):
        return content.get(key, default)
    return getattr(content, key, default)


def _image_url_from_content(content: typing.Any) -> str:
    image_url = _content_get(content, "image_url")
    if isinstance(image_url, dict):
        return str(image_url.get("url") or "").strip()
    return str(getattr(image_url, "url", image_url) or "").strip()


def _base64_payload_and_mime(
    value: typing.Any,
    default_mime_type: str,
) -> tuple[str | None, str]:
    if not isinstance(value, str) or not value.strip():
        return None, default_mime_type

    payload = value.strip()
    mime_type = default_mime_type
    if payload.startswith("data:") and "," in payload:
        header, payload = payload.split(",", 1)
        if ";base64" not in header:
            return None, mime_type
        parsed_mime_type = header[5:].split(";", 1)[0].strip()
        if parsed_mime_type:
            mime_type = parsed_mime_type

    try:
        base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None, mime_type
    return payload, mime_type


def _content_type_from_name(name: typing.Any, default: str) -> str:
    if isinstance(name, str) and name:
        guessed, _ = mimetypes.guess_type(name)
        if guessed:
            return guessed
    return default


def _attachment_name(attachment: typing.Any, default: str) -> str:
    for key in ("name", "file_name", "platform_attachment_id", "id"):
        value = _attachment_get(attachment, key)
        if value:
            return str(value)
    return default


def _resource_uri(attachment: typing.Any, name: str) -> str:
    url = _attachment_get(attachment, "url")
    if url:
        return str(url)
    path = _attachment_get(attachment, "path")
    if path:
        return str(path)
    return f"langbot-input://{urllib.parse.quote(str(name), safe='')}"


def _resource_link_block(
    attachment: typing.Any,
    *,
    default_name: str,
    default_mime_type: str,
) -> dict[str, typing.Any] | None:
    uri = str(_attachment_get(attachment, "url") or _attachment_get(attachment, "path") or "").strip()
    if not uri:
        return None
    name = _attachment_name(attachment, default_name)
    mime_type = str(
        _attachment_get(attachment, "mime_type")
        or _attachment_get(attachment, "content_type")
        or _content_type_from_name(name, default_mime_type)
    )
    block: dict[str, typing.Any] = {
        "type": "resource_link",
        "uri": uri,
        "name": name,
        "mimeType": mime_type,
    }
    size = _attachment_get(attachment, "size") or _attachment_get(attachment, "size_bytes")
    if isinstance(size, int):
        block["size"] = size
    return block


def attachments_from_contents(contents: list[typing.Any]) -> list[dict[str, typing.Any]]:
    attachments: list[dict[str, typing.Any]] = []
    for item in contents or []:
        item_type = _content_get(item, "type")
        if item_type == "image_base64":
            content = _content_get(item, "image_base64")
            _, mime_type = _base64_payload_and_mime(content, "image/jpeg")
            attachments.append(
                {
                    "type": "image",
                    "name": "image",
                    "content": content,
                    "mime_type": mime_type,
                    "source": "content",
                }
            )
        elif item_type == "image_url":
            url = _image_url_from_content(item)
            if url:
                attachments.append(
                    {
                        "type": "image",
                        "name": "image",
                        "url": url,
                        "mime_type": _content_type_from_name(url, "image/*"),
                        "source": "content",
                    }
                )
        elif item_type == "file_base64":
            content = _content_get(item, "file_base64")
            name = _content_get(item, "file_name") or "file"
            _, mime_type = _base64_payload_and_mime(
                content,
                _content_type_from_name(name, "application/octet-stream"),
            )
            attachments.append(
                {
                    "type": "file",
                    "name": name,
                    "content": content,
                    "mime_type": mime_type,
                    "source": "content",
                }
            )
        elif item_type == "file_url":
            url = str(_content_get(item, "file_url") or "").strip()
            if url:
                name = _content_get(item, "file_name") or "file"
                attachments.append(
                    {
                        "type": "file",
                        "name": name,
                        "url": url,
                        "mime_type": _content_type_from_name(name, "application/octet-stream"),
                        "source": "content",
                    }
                )
    return attachments


def prompt_capabilities(initialize_result: dict[str, typing.Any]) -> dict[str, bool]:
    agent_capabilities = initialize_result.get("agentCapabilities")
    if not isinstance(agent_capabilities, dict):
        agent_capabilities = {}
    prompt_caps = agent_capabilities.get("promptCapabilities")
    if not isinstance(prompt_caps, dict):
        prompt_caps = {}
    return {
        "image": bool(prompt_caps.get("image")),
        "audio": bool(prompt_caps.get("audio")),
        "embedded_context": bool(prompt_caps.get("embeddedContext") or prompt_caps.get("embedded_context")),
    }


def _resource_block_from_attachment(
    attachment: typing.Any,
    *,
    default_name: str,
    default_mime_type: str,
) -> dict[str, typing.Any] | None:
    content = _attachment_get(attachment, "content")
    payload, mime_type = _base64_payload_and_mime(content, default_mime_type)
    if not payload:
        return None

    name = _attachment_name(attachment, default_name)
    mime_type = str(
        _attachment_get(attachment, "mime_type")
        or _attachment_get(attachment, "content_type")
        or mime_type
        or _content_type_from_name(name, default_mime_type)
    )
    resource: dict[str, typing.Any] = {
        "uri": _resource_uri(attachment, name),
        "mimeType": mime_type,
    }
    if mime_type.startswith("text/"):
        try:
            resource["text"] = base64.b64decode(payload, validate=True).decode("utf-8")
        except (UnicodeDecodeError, binascii.Error, ValueError):
            resource["blob"] = payload
    else:
        resource["blob"] = payload
    return {"type": "resource", "resource": resource}


def _image_block_from_attachment(
    attachment: typing.Any,
    *,
    default_name: str,
) -> dict[str, typing.Any] | None:
    name = _attachment_name(attachment, default_name)
    mime_type = str(
        _attachment_get(attachment, "mime_type")
        or _attachment_get(attachment, "content_type")
        or _content_type_from_name(name, "image/jpeg")
    )
    payload, parsed_mime_type = _base64_payload_and_mime(_attachment_get(attachment, "content"), mime_type)
    if not payload:
        return None
    return {
        "type": "image",
        "mimeType": parsed_mime_type or mime_type,
        "data": payload,
    }


def _audio_block_from_attachment(attachment: typing.Any) -> dict[str, typing.Any] | None:
    name = _attachment_name(attachment, "audio")
    mime_type = str(
        _attachment_get(attachment, "mime_type")
        or _attachment_get(attachment, "content_type")
        or _content_type_from_name(name, "audio/mpeg")
    )
    payload, parsed_mime_type = _base64_payload_and_mime(_attachment_get(attachment, "content"), mime_type)
    if not payload:
        return None
    return {
        "type": "audio",
        "mimeType": parsed_mime_type or mime_type,
        "data": payload,
    }


def _append_multimodal_note(
    blocks: list[dict[str, typing.Any]],
    omitted: dict[str, int],
) -> None:
    notes: list[str] = []
    if omitted.get("image"):
        notes.append(
            f"{omitted['image']} image attachment(s) were not sent because the ACP runtime "
            "did not advertise image prompt support and no URL link was available."
        )
    if omitted.get("audio"):
        notes.append(
            f"{omitted['audio']} audio attachment(s) were not sent because the ACP runtime "
            "did not advertise audio prompt support and no URL link was available."
        )
    if omitted.get("file"):
        notes.append(
            f"{omitted['file']} file attachment(s) were not embedded because the ACP runtime "
            "did not advertise embedded context support and no URL link was available."
        )
    if notes:
        blocks.append({"type": "text", "text": "LangBot attachment note: " + " ".join(notes)})


def _input_attachments(input_data: typing.Any) -> list[typing.Any]:
    attachments = list(_attachment_get(input_data, "attachments", []) or [])
    if attachments:
        return attachments
    return attachments_from_contents(list(_attachment_get(input_data, "contents", []) or []))


def has_acp_prompt_input(prompt_text: str, input_data: typing.Any) -> bool:
    return bool(prompt_text.strip() or _input_attachments(input_data))


def acp_prompt_blocks(
    prompt_text: str,
    input_data: typing.Any,
    prompt_caps: dict[str, bool],
) -> list[dict[str, typing.Any]]:
    blocks: list[dict[str, typing.Any]] = []
    if prompt_text.strip():
        blocks.append({"type": "text", "text": prompt_text})

    omitted: dict[str, int] = {"image": 0, "audio": 0, "file": 0}
    for attachment in _input_attachments(input_data):
        attachment_type = str(_attachment_get(attachment, "type") or "file").lower()

        if attachment_type == "image":
            block = _image_block_from_attachment(attachment, default_name="image")
            if block and prompt_caps.get("image"):
                blocks.append(block)
                continue
            link = _resource_link_block(attachment, default_name="image", default_mime_type="image/*")
            if link:
                blocks.append(link)
            elif block:
                omitted["image"] += 1
            continue

        if attachment_type in {"voice", "audio"}:
            block = _audio_block_from_attachment(attachment)
            if block and prompt_caps.get("audio"):
                blocks.append(block)
                continue
            link = _resource_link_block(attachment, default_name="audio", default_mime_type="audio/*")
            if link:
                blocks.append(link)
            elif block:
                omitted["audio"] += 1
            continue

        name = _attachment_name(attachment, "file")
        mime_type = str(
            _attachment_get(attachment, "mime_type")
            or _attachment_get(attachment, "content_type")
            or _content_type_from_name(name, "application/octet-stream")
        )
        block = _resource_block_from_attachment(
            attachment,
            default_name=name,
            default_mime_type=mime_type,
        )
        if block and prompt_caps.get("embedded_context"):
            blocks.append(block)
            continue
        link = _resource_link_block(attachment, default_name=name, default_mime_type=mime_type)
        if link:
            blocks.append(link)
        elif block:
            omitted["file"] += 1

    _append_multimodal_note(blocks, omitted)
    if not blocks:
        blocks.append({"type": "text", "text": "User input contains no text or supported attachments."})
    return blocks
