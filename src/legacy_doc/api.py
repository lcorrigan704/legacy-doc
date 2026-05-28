from __future__ import annotations

from legacy_doc.exceptions import LegacyDocError
from legacy_doc.types import (
    DocExtractionResult,
    ExtractionOptions,
)
from legacy_doc.word import extract_word_document


def extract_text(
    document_bytes: bytes,
    *,
    options: ExtractionOptions | None = None,
) -> DocExtractionResult:
    options = options or ExtractionOptions()
    extraction = extract_word_document(document_bytes, options=options)
    text = extraction.text
    text_bytes = len(text.encode("utf-8"))
    if text_bytes > options.max_text_bytes:
        raise LegacyDocError(".doc extracted text exceeds parser limit")
    metadata = {
        "chars": len(text),
        "bytes": text_bytes,
        **extraction.metadata,
    }
    return DocExtractionResult(
        text=text,
        metadata=metadata,
        warnings=extraction.warnings,
    )
