from __future__ import annotations

import re
from pathlib import Path

INPUT_DIR = Path("data/vinfast_markdown")
OUTPUT_DIR = Path("data/vinfast_markdown_clean")

PAGE_HEADER_RE = re.compile(r"^##\s+Page\s+\d+\s*$", re.IGNORECASE)
DOT_LEADER_RE = re.compile(r"\.{8,}")


def has_alpha(text: str) -> bool:
    return any(char.isalpha() for char in text)


def should_drop_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if PAGE_HEADER_RE.match(stripped):
        return True
    if stripped.lower() == "_no extractable text on this page._":
        return True
    if DOT_LEADER_RE.search(stripped):
        return True
    if stripped.isdigit() and len(stripped) <= 4:
        return True

    is_heading_or_list = stripped.startswith("#") or stripped.startswith("-")
    if not is_heading_or_list and not has_alpha(stripped):
        return True
    return False


def normalize_whitespace(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def clean_markdown_text(text: str) -> str:
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    cleaned_lines: list[str] = []
    paragraph_parts: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_parts:
            paragraph = " ".join(paragraph_parts).strip()
            if paragraph:
                cleaned_lines.append(paragraph)
            paragraph_parts.clear()

    for raw in raw_lines:
        line = normalize_whitespace(raw)
        if should_drop_line(line):
            flush_paragraph()
            continue

        is_heading = line.startswith("#")
        is_list = line.startswith("-")

        if is_heading or is_list:
            flush_paragraph()
            cleaned_lines.append(line)
            continue

        paragraph_parts.append(line)

    flush_paragraph()

    deduped: list[str] = []
    previous = ""
    for line in cleaned_lines:
        if line == previous:
            continue
        deduped.append(line)
        previous = line

    # Keep markdown readable with blank lines between blocks.
    return "\n\n".join(deduped).strip() + "\n"


def main() -> int:
    if not INPUT_DIR.exists():
        print(f"Input folder not found: {INPUT_DIR}")
        return 1

    md_files = sorted(path for path in INPUT_DIR.glob("*.md") if path.is_file())
    if not md_files:
        print(f"No markdown files found in {INPUT_DIR}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for md_path in md_files:
        original = md_path.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_markdown_text(original)

        output_path = OUTPUT_DIR / md_path.name
        output_path.write_text(cleaned, encoding="utf-8")

        print(
            f"Cleaned: {md_path.name} | chars {len(original)} -> {len(cleaned)}"
        )

    print(f"\nDone. Cleaned {len(md_files)} files into {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
