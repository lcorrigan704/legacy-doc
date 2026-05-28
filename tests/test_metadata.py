from __future__ import annotations

from datetime import datetime, timezone

from legacy_doc import extract_text

from tests.fixtures import (
    DOCUMENT_SUMMARY_INFORMATION_STREAM,
    SUMMARY_INFORMATION_STREAM,
    make_doc_bytes,
)


def test_extracts_summary_information_metadata() -> None:
    created_at = datetime(2026, 5, 28, 10, 30, tzinfo=timezone.utc)
    document = make_doc_bytes(
        "Metadata text",
        summary_properties={
            2: "Quarterly Notes",
            3: "Planning",
            4: "Liam Corrigan",
            5: "legacy,doc",
            6: "Example comment",
            7: "Normal.dot",
            8: "LC",
            9: "3",
            12: created_at,
            14: 7,
            15: 123,
            16: 456,
            18: "Microsoft Word",
        },
    )

    result = extract_text(document)

    assert result.metadata["has_summary_information"] is True
    assert result.metadata["title"] == "Quarterly Notes"
    assert result.metadata["subject"] == "Planning"
    assert result.metadata["author"] == "Liam Corrigan"
    assert result.metadata["last_author"] == "LC"
    assert result.metadata["page_count"] == 7
    assert result.metadata["word_count"] == 123
    assert result.metadata["character_count"] == 456
    assert result.metadata["application_name"] == "Microsoft Word"
    assert result.metadata["created_at"] == "2026-05-28T10:30:00+00:00"
    assert result.warnings == ()


def test_extracts_document_summary_information_metadata() -> None:
    document = make_doc_bytes(
        "Metadata text",
        document_summary_properties={
            5: 10,
            6: 4,
            14: "Jane Manager",
            15: "Example Ltd",
            17: 789,
        },
    )

    result = extract_text(document)

    assert result.metadata["has_document_summary_information"] is True
    assert result.metadata["line_count"] == 10
    assert result.metadata["paragraph_count"] == 4
    assert result.metadata["manager"] == "Jane Manager"
    assert result.metadata["company"] == "Example Ltd"
    assert result.metadata["character_count_with_spaces"] == 789
    assert result.warnings == ()


def test_missing_metadata_streams_are_reported_as_absent() -> None:
    result = extract_text(make_doc_bytes("Plain text"))

    assert result.metadata["has_summary_information"] is False
    assert result.metadata["has_document_summary_information"] is False
    assert "title" not in result.metadata
    assert result.warnings == ()


def test_malformed_metadata_stream_adds_warning_without_failing_text() -> None:
    document = make_doc_bytes(
        "Readable text",
        extra_streams={SUMMARY_INFORMATION_STREAM: b"not a property stream"},
    )

    result = extract_text(document)

    assert result.text == "Readable text"
    assert result.metadata["has_summary_information"] is True
    assert result.warnings == ("SummaryInformation stream could not be parsed",)


def test_inventory_metadata_detects_macros_and_embedded_objects() -> None:
    document = make_doc_bytes(
        "Inventory text",
        extra_streams={
            "VBA": b"macro marker",
            "ObjectPool": b"object marker",
        },
    )

    result = extract_text(document)

    assert result.metadata["has_macros"] is True
    assert result.metadata["has_embedded_objects"] is True
    assert result.metadata["ole_stream_count"] == 4


def test_malformed_document_summary_stream_adds_warning() -> None:
    document = make_doc_bytes(
        "Readable text",
        extra_streams={DOCUMENT_SUMMARY_INFORMATION_STREAM: b"bad"},
    )

    result = extract_text(document)

    assert result.text == "Readable text"
    assert result.metadata["has_document_summary_information"] is True
    assert result.warnings == (
        "DocumentSummaryInformation stream could not be parsed",
    )
