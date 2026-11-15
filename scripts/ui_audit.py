#!/usr/bin/env python3
"""Static consistency checks for BottleNeck's shared UI contract."""
from __future__ import annotations

import re
import sys
import tomllib
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InterfaceParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.buttons: list[dict[str, str]] = []
        self.dialogs: list[dict[str, str]] = []
        self.images_missing_alt: list[str] = []
        self._button: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: (value or "") for key, value in attrs}
        if attr.get("id"):
            self.ids.append(attr["id"])
        if tag == "button":
            self._button = {**attr, "_text": ""}
        if tag == "img" and "alt" not in attr:
            self.images_missing_alt.append(attr.get("src", "<inline image>"))
        if attr.get("role") == "dialog":
            self.dialogs.append(attr)

    def handle_data(self, data: str) -> None:
        if self._button is not None:
            self._button["_text"] += data.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button is not None:
            self.buttons.append(self._button)
            self._button = None


def strip_root_blocks(css: str) -> str:
    return re.sub(r":root\s*\{[^}]*\}", "", css, flags=re.S)


def main() -> int:
    errors: list[str] = []
    html_path = ROOT / "index.html"
    html = html_path.read_text(encoding="utf-8")
    parser = InterfaceParser()
    parser.feed(html)

    duplicates = [key for key, count in Counter(parser.ids).items() if count > 1]
    if duplicates:
        errors.append("Duplicate HTML IDs: " + ", ".join(duplicates))
    for button in parser.buttons:
        if button.get("type") not in {"button", "submit", "reset"}:
            errors.append(f"Static button lacks explicit type: {button}")
            break
        if not (button.get("_text", "").strip() or button.get("aria-label") or button.get("title")):
            errors.append(f"Static button has no accessible name: {button}")
            break
    for dialog in parser.dialogs:
        if dialog.get("aria-modal") != "true" or not dialog.get("aria-labelledby"):
            errors.append(f"Dialog lacks modal semantics or accessible title: {dialog}")
    if parser.images_missing_alt:
        errors.append("Images without alt text: " + ", ".join(parser.images_missing_alt))
    if 'class="skip-link"' not in html or 'id="pageContent"' not in html:
        errors.append("Skip link or main content target is missing")

    app_js = (ROOT / "static/app.js").read_text(encoding="utf-8")
    css_files = [ROOT / "static/styles.css", ROOT / "static/design-system.css"]
    css_text = "\n".join(path.read_text(encoding="utf-8") for path in css_files)
    css_without_roots = "\n".join(strip_root_blocks(path.read_text(encoding="utf-8")) for path in css_files)

    if re.search(r"\b(?:window\.)?(?:prompt|confirm|alert)\s*\(", app_js):
        errors.append("Native prompt/confirm/alert calls remain in the application")
    if re.search(r"addEventListener\(\s*['\"][^'\"]+['\"]\s*,\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)", app_js):
        errors.append("Empty event listener remains in application JavaScript")
    if "function trapDialogFocus" not in app_js or "setOverlayBackground(true)" not in app_js:
        errors.append("Shared dialog focus/inert lifecycle is incomplete")
    if "aria-current" not in app_js or "normalizeButtonTypes" not in app_js:
        errors.append("Navigation/button interaction contract is incomplete")
    if "prefers-reduced-motion" not in css_text:
        errors.append("Reduced-motion support is missing")
    if "--presence-fallback-color" not in css_text:
        errors.append("Presence fallback color token is missing")

    raw_color_literals = re.findall(r"#[0-9a-fA-F]{3,8}\b", css_without_roots)
    if raw_color_literals:
        errors.append(f"Raw color literals outside :root: {len(raw_color_literals)}")

    tiny_fonts: list[tuple[str, str]] = []
    for path in css_files:
        css = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?i)(?:font-size|font)\s*:\s*([^;{}]+)", css):
            sizes = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)px", match.group(1))
            if any(float(size) < 10.5 for size in sizes):
                line = css.count("\n", 0, match.start()) + 1
                tiny_fonts.append((path.name, f"line {line}: {match.group(0).strip()}"))
    if tiny_fonts:
        errors.append("Text below 10.5px: " + "; ".join(f"{name} {detail}" for name, detail in tiny_fonts[:8]))

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    main_py = (ROOT / "main.py").read_text(encoding="utf-8")
    version_sources = {
        "pyproject.toml": version,
        "main.py": re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)', main_py).group(1),
        "static/app.js": re.search(r"const VERSION = ['\"]([^'\"]+)", app_js).group(1),
    }
    if any(value != version for value in version_sources.values()):
        errors.append("Version mismatch: " + repr(version_sources))
    if f"?v={version}" not in html or f"v{version}" not in html:
        errors.append("HTML title or static cache keys do not match package version")

    dynamic_buttons = list(re.finditer(r"<button\b([^>]*)>(.*?)</button>", app_js, flags=re.S))
    unnamed_dynamic_buttons: list[int] = []
    for match in dynamic_buttons:
        attrs, body = match.groups()
        visible_text = re.sub(r"<[^>]*>", "", body)
        visible_text = re.sub(r"\$\{[^}]*\}", "", visible_text).strip()
        if not visible_text and "${" not in body and not re.search(r"\baria-label\s*=|\btitle\s*=", attrs):
            unnamed_dynamic_buttons.append(app_js.count("\n", 0, match.start()) + 1)
    if unnamed_dynamic_buttons:
        errors.append("Dynamic button(s) without text or accessible names at lines: " + ", ".join(map(str, unnamed_dynamic_buttons[:12])))

    if "max-height: min(74dvh, 760px)" not in css_text or "max-height: calc(100dvh - 24px)" not in css_text:
        errors.append("Dialog sizing does not account for desktop zoom and mobile viewport height")
    if "@media (min-width: 561px) and (max-width: 1300px)" not in css_text or "@media (max-width: 560px)" not in css_text:
        errors.append("Compact and phone top-bar breakpoints are incomplete")
    if "chat-workspace-v8 .chat-message-feed { flex: 1 1 auto; min-height: 0" not in css_text:
        errors.append("Mobile chat feed can force the composer below the viewport")
    if "--role-default-color: var(--ink-soft)" not in css_text:
        errors.append("Default role color must remain neutral; creator violet is reserved for the credit signature")
    if "max-width: 100%; overflow-x: clip" not in css_text:
        errors.append("Phone viewport horizontal overflow guard is missing")

    print(f"BottleNeck UI audit v{version}")
    print(f"HTML IDs: {len(parser.ids)} unique; static buttons: {len(parser.buttons)}; dialogs: {len(parser.dialogs)}")
    print(f"CSS files: {len(css_files)}; text-size floor: 10.5px; raw colors outside :root: {len(raw_color_literals)}")
    print(f"Dynamic buttons checked: {len(dynamic_buttons)}; unnamed: {len(unnamed_dynamic_buttons)}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: shared UI contract checks are clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
