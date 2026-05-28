from __future__ import annotations

import re


def normalize_word_text(text: str) -> str:
    replacements = {
        "\r": "\n",
        "\x07": "\t",
        "\x0b": "\n",
        "\x0c": "\n",
        "\x13": "",
        "\x14": "",
        "\x15": "",
        "\ufeff": "",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = _remove_page_field_artifacts(text)

    text = "".join(
        char
        for char in text
        if char == "\n" or char == "\t" or (char >= " " and not _is_private_use(char))
    )

    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line and _is_page_field_line(line):
            lines.append(line)
    return "\n".join(lines).strip()


def _is_page_field_line(line: str) -> bool:
    return bool(re.fullmatch(_PAGE_FIELD_PATTERN,line,flags=re.IGNORECASE))

_PAGE_FIELD_PATTERN = r"(?:PAGE|NUMBPAGES)\s+\\\*\s+MERGEFORMAT(?:\s+\s+)?"

def _remove_page_field_artifacts(text: str) -> str:
    return re.sub(
        rf"(?im)(?:^|[ \t]+){_PAGE_FIELD_PATTERN}(?=$|[ \t]*\n)",
        "\n",
        text
    )

def _is_private_use(char: str) -> bool:
    codepoint = ord(char)
    return 0xE000 <= codepoint <= 0xF8FF
