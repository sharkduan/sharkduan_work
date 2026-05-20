import argparse
import re
from pathlib import Path

import fitz
from ftfy import fix_text

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None


SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
NOISE_LINES = {
    "ARTICLEINPRESS",
    "ARTICLE IN PRESS",
    "Communications Biology",
    "Article in Press",
}


def normalize_text(text: str) -> str:
    text = fix_text(text)
    text = text.replace("\u00ad", "")
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            lines.append("")
            continue
        if line in NOISE_LINES:
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        lines.append(line)

    paragraphs = []
    buf = ""
    for line in lines:
        if not line:
            if buf:
                paragraphs.append(buf.strip())
                buf = ""
            continue
        if not buf:
            buf = line
            continue
        if buf.endswith("-") and line and line[0].islower():
            buf = buf[:-1] + line
        elif re.search(r"[.!?:;)]$", buf):
            paragraphs.append(buf.strip())
            buf = line
        else:
            buf += " " + line
    if buf:
        paragraphs.append(buf.strip())
    return "\n\n".join(paragraphs)


def markdownize(text: str) -> str:
    blocks = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue

        section = SECTION_RE.match(para)
        if section and len(para) < 120:
            level = 2 + section.group(1).count(".")
            blocks.append(f"{'#' * level} {section.group(1)} {section.group(2)}")
            continue

        if para in {
            "Abstract",
            "Keywords: Covalent drug design, diffusion model, reinforcement learning",
            "Data availability",
            "Code availability",
            "Acknowledgments",
            "Author contribution",
            "Competing interests",
            "References",
            "Figure captions",
        }:
            if para.startswith("Keywords:"):
                blocks.append(f"**{para}**")
            else:
                blocks.append(f"## {para}")
            continue

        if para.startswith("Fig. "):
            blocks.append(f"**{para}**")
            continue

        blocks.append(para)
    return "\n\n".join(blocks).strip() + "\n"


def clean_markdown(text: str) -> str:
    replacements = {
        "漏 The Author(s)": "© The Author(s)",
        "鈥燷": "†",
        "鈥?": "†",
        "鈥揮": "–",
        "ARTICLE IN PRESS \n\n": "",
        "\n\nARTICLE IN PRESS \n\n": "\n\n",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\n\*\*==> picture \[[^\n]+intentionally omitted <==\*\*\n", "\n", text)
    text = re.sub(r"\nARTICLE IN PRESS\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if pymupdf4llm is not None:
        extracted = pymupdf4llm.to_markdown(args.pdf)
        body = clean_markdown(fix_text(extracted))
    else:
        doc = fitz.open(args.pdf)
        page_texts = [page.get_text("text", sort=True) for page in doc]
        body = clean_markdown(markdownize(normalize_text("\n\n".join(page_texts))))

    frontmatter = """---
title: "De novo covalent drug generation with enhanced drug-likeness and safety"
authors: "Wenbo Zhang; Tianxiao Liu; Xiaoying Dong; Saisai Sun; Xiaojun Yao; Pengyong Li; Lin Gao"
journal: "Communications Biology"
date: "2026-02-17"
doi: "10.1038/s42003-026-09725-5"
zotero_parent_key: "7YMCLLHC"
zotero_attachment_key: "JL9IHCMF"
source_pdf: "papers/de-novo-covalent-drug-generation-enhanced-drug-likeness-safety.pdf"
---

"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(frontmatter + body, encoding="utf-8")


if __name__ == "__main__":
    main()
