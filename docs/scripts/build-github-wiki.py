#!/usr/bin/env python3
"""Build a GitHub Wiki-compatible mirror from the Mintlify MDX sources."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit

LANGUAGES = {"zh": "简体中文", "en": "English", "ja": "日本語"}
NAVIGATION_LANGUAGE_CODES = {"cn": "zh", "en": "en", "jp": "ja"}
DOC_EXTENSIONS = (".md", ".mdx", ".html")
CALLOUTS = {"Info": "NOTE", "Note": "NOTE", "Tip": "TIP", "Warning": "WARNING"}
MOVED_SECTIONS = {"platforms", "models", "pipelines", "knowledge", "mcp"}


def page_name(path: PurePosixPath) -> str:
    return path.with_suffix("").as_posix().replace("/", "-")


def extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    metadata: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, text[end + 5 :]


def resolve_doc_target(source: PurePosixPath, target: str) -> str | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("#"):
        return None
    raw_path = parsed.path
    if not raw_path:
        return None
    resolved = PurePosixPath(raw_path.lstrip("/")) if raw_path.startswith("/") else source.parent / raw_path
    parts: list[str] = []
    for part in resolved.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)
    if not parts or parts[0] not in LANGUAGES:
        return None
    normalized = PurePosixPath(*parts)
    suffix = normalized.suffix.lower()
    if suffix in DOC_EXTENSIONS:
        normalized = normalized.with_suffix("")
    elif suffix:
        return None
    # Mintlify redirects these sections from their old deploy location. Apply the
    # same redirect in the flat Wiki mirror so historical source links still work.
    if len(normalized.parts) >= 3 and normalized.parts[1] == "deploy" and normalized.parts[2] in MOVED_SECTIONS:
        normalized = PurePosixPath(normalized.parts[0], "usage", *normalized.parts[2:])
    return urlunsplit(("", "", page_name(normalized), parsed.query, parsed.fragment))


def rewrite_url(source: PurePosixPath, target: str, *, image: bool = False) -> str:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith(("#", "mailto:")):
        return target
    if image:
        path = parsed.path.lstrip("/") if parsed.path.startswith("/") else (source.parent / parsed.path).as_posix()
        return urlunsplit(("https", "raw.githubusercontent.com", f"/langbot-app/langbot-docs/main/{path}", parsed.query, parsed.fragment))
    return resolve_doc_target(source, target) or target


def convert_callouts(text: str) -> str:
    pattern = re.compile(
        r"<(Info|Note|Tip|Warning)(?:\s+title=(?:\"([^\"]*)\"|'([^']*)'))?\s*>(.*?)</\1>",
        re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        component = match.group(1)
        title = match.group(2) or match.group(3) or ""
        body = match.group(4).strip()
        lines = [f"> [!{CALLOUTS[component]}]"]
        if title:
            lines.append(f"> **{title}**")
        lines.extend(">" if not line else f"> {line}" for line in body.splitlines())
        return "\n".join(lines)

    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(replace, text)
    return text


def convert_mdx(source: PurePosixPath, text: str) -> tuple[str, str]:
    metadata, body = extract_frontmatter(text)
    title = metadata.get("title") or source.stem.replace("-", " ").title()
    body = convert_callouts(body)
    body = re.sub(
        r'<Accordion\s+title=(?:"([^"]*)"|\'([^\']*)\')\s*>',
        lambda m: f"\n<details>\n<summary><strong>{m.group(1) or m.group(2)}</strong></summary>\n",
        body,
    )
    body = body.replace("</Accordion>", "\n</details>")
    body = re.sub(r"</?AccordionGroup\s*>", "", body)
    body = re.sub(
        r"(!\[[^\]]*\]\()([^)\s]+)([^)]*\))",
        lambda m: m.group(1) + rewrite_url(source, m.group(2), image=True) + m.group(3),
        body,
    )
    body = re.sub(
        r"(?<!!)\[([^\]]+)\]\(([^)\s]+)([^)]*)\)",
        lambda m: f"[{m.group(1)}]({rewrite_url(source, m.group(2))}{m.group(3)})",
        body,
    )
    body = re.sub(
        r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'])',
        lambda m: m.group(1) + rewrite_url(source, m.group(2), image=True) + m.group(3),
        body,
        flags=re.IGNORECASE,
    )
    body = body.replace("<br />", "<br>")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return title, f"# {title}\n\n{body}\n"


def discover_documents(root: Path) -> list[Path]:
    return sorted(path for language in LANGUAGES for path in (root / language).rglob("*.mdx"))


def render_page_items(
    items: list[object], titles: dict[str, str], *, indent: int = 0
) -> tuple[list[str], set[str]]:
    lines: list[str] = []
    included: set[str] = set()
    prefix = " " * indent
    for item in items:
        if isinstance(item, str):
            source_name = item.removesuffix(".mdx").removesuffix(".md")
            title = titles.get(source_name)
            if title:
                lines.append(f"{prefix}- [{title}]({page_name(PurePosixPath(source_name))})")
                included.add(source_name)
        elif isinstance(item, dict) and not item.get("hidden"):
            group = item.get("group")
            children = item.get("pages", [])
            if group and isinstance(children, list):
                child_lines, child_pages = render_page_items(children, titles, indent=indent + 2)
                if child_lines:
                    lines.append(f"{prefix}- **{group}**")
                    lines.extend(child_lines)
                    included.update(child_pages)
    return lines, included


def build_sidebar(root: Path, titles: dict[str, str]) -> str:
    navigation_path = root / "docs.json"
    if not navigation_path.is_file():
        lines = ["## LangBot Documentation", ""]
        for language, label in LANGUAGES.items():
            lines.extend((f"### {label}", ""))
            lines.extend(
                f"- [{title}]({page_name(PurePosixPath(source))})"
                for source, title in titles.items()
                if source.startswith(f"{language}/")
            )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    navigation = json.loads(navigation_path.read_text(encoding="utf-8"))["navigation"]["languages"]
    nav_by_language = {
        NAVIGATION_LANGUAGE_CODES[item["language"]]: item
        for item in navigation
        if item.get("language") in NAVIGATION_LANGUAGE_CODES
    }
    lines = ["## LangBot Documentation", "", "[Home](Home)", ""]
    for language, label in LANGUAGES.items():
        language_nav = nav_by_language.get(language, {})
        open_attribute = " open" if language == "zh" else ""
        lines.extend((f"<details{open_attribute}>", f"<summary><strong>{label}</strong></summary>", ""))
        included: set[str] = set()
        for tab_index, tab in enumerate(language_nav.get("tabs", [])):
            tab_lines: list[str] = []
            tab_pages: set[str] = set()
            for group in tab.get("groups", []):
                group_lines, group_pages = render_page_items(group.get("pages", []), titles, indent=2)
                if group_lines:
                    tab_lines.append(f"- **{group['group']}**")
                    tab_lines.extend(group_lines)
                    tab_pages.update(group_pages)
            if tab_lines:
                tab_open = " open" if language == "zh" and tab_index == 0 else ""
                lines.extend((f"<details{tab_open}>", f"<summary>{tab['tab']}</summary>", ""))
                lines.extend(tab_lines)
                lines.extend(("", "</details>", ""))
                included.update(tab_pages)

        unlisted = sorted(
            (source, title)
            for source, title in titles.items()
            if source.startswith(f"{language}/") and source not in included
        )
        if unlisted:
            lines.extend(("<details>", "<summary>Other pages</summary>", ""))
            lines.extend(f"- [{title}]({page_name(PurePosixPath(source))})" for source, title in unlisted)
            lines.extend(("", "</details>", ""))
        lines.extend(("</details>", ""))
    return "\n".join(lines).rstrip() + "\n"


def build(root: Path, output: Path) -> int:
    documents = discover_documents(root)
    if not documents:
        raise SystemExit("No MDX documents found")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    index: dict[str, list[tuple[str, str]]] = {language: [] for language in LANGUAGES}
    titles: dict[str, str] = {}
    for path in documents:
        source = PurePosixPath(path.relative_to(root).as_posix())
        title, converted = convert_mdx(source, path.read_text(encoding="utf-8"))
        name = page_name(source)
        (output / f"{name}.md").write_text(converted, encoding="utf-8")
        index[source.parts[0]].append((name, title))
        titles[source.with_suffix("").as_posix()] = title
    home = [
        "# LangBot Documentation",
        "",
        "This GitHub Wiki is automatically synchronized from [langbot-app/langbot-docs](https://github.com/langbot-app/langbot-docs).",
        "",
    ]
    for language, label in LANGUAGES.items():
        pages = index[language]
        guide_name = f"{language}-insight-guide"
        guide = next(((name, title) for name, title in pages if name == guide_name), pages[0])
        home.extend((f"## {label}", "", f"[{guide[1]}]({guide[0]})", ""))
    (output / "Home.md").write_text("\n".join(home).rstrip() + "\n", encoding="utf-8")
    (output / "_Sidebar.md").write_text(build_sidebar(root, titles), encoding="utf-8")
    (output / "_Footer.md").write_text(
        "Automatically synchronized from [langbot-app/langbot-docs](https://github.com/langbot-app/langbot-docs).\n",
        encoding="utf-8",
    )
    return len(documents)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("dist/github-wiki"))
    args = parser.parse_args()
    count = build(args.root.resolve(), args.output.resolve())
    print(f"Built {count} GitHub Wiki pages in {args.output}")


if __name__ == "__main__":
    main()
