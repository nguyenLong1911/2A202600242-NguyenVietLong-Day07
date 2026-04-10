from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

INPUT_DIR = Path("Vinfast")
OUTPUT_DIR = Path("data/vinfast_markdown")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def convert_pdf_to_markdown(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))

    lines: list[str] = [
        f"# {pdf_path.stem}",
        "",
        f"- Source PDF: {pdf_path.name}",
        f"- Total pages: {len(reader.pages)}",
        "",
    ]

    for page_index, page in enumerate(reader.pages, start=1):
        page_text = normalize_text(page.extract_text() or "")
        lines.append(f"## Page {page_index}")
        lines.append("")
        if page_text:
            lines.append(page_text)
        else:
            lines.append("_No extractable text on this page._")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    if not INPUT_DIR.exists():
        print(f"Input folder not found: {INPUT_DIR}")
        return 1

    pdf_files = sorted(path for path in INPUT_DIR.rglob("*.pdf") if path.is_file())
    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failed_files: list[tuple[str, str]] = []

    for pdf_path in pdf_files:
        try:
            markdown = convert_pdf_to_markdown(pdf_path)
            output_path = OUTPUT_DIR / f"{pdf_path.stem}.md"
            output_path.write_text(markdown, encoding="utf-8")
            success_count += 1
            print(f"Converted: {pdf_path} -> {output_path}")
        except Exception as exc:
            failed_files.append((str(pdf_path), str(exc)))
            print(f"Failed: {pdf_path} ({exc})")

    print(f"\nDone. Converted {success_count}/{len(pdf_files)} PDFs.")
    if failed_files:
        print("Failed files:")
        for file_name, error in failed_files:
            print(f"- {file_name}: {error}")

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
