from __future__ import annotations

from legacy_doc.exceptions import LegacyDocError
from legacy_doc.types import (
    PARSER_NAME,
    PARSER_VERSION,
    DocExtractionResult,
    ExtractionOptions,
)
from legacy_doc.word import extract_word_text


def extract_text(
    document_bytes: bytes,
    *,
    options: ExtractionOptions | None = None,
) -> DocExtractionResult:
    options = options or ExtractionOptions()
    text = extract_word_text(document_bytes, options=options)
    text_bytes = len(text.encode("utf-8"))
    if text_bytes > options.max_text_bytes:
        raise LegacyDocError(".doc extracted text exceeds parser limit")
    return DocExtractionResult(
        text=text,
        metadata={
            "chars": len(text),
            "bytes": text_bytes,
        },
    )
