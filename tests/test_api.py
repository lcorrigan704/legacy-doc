import pytest

from legacy_doc import ExtractionOptions, LegacyDocError, extract_text

from tests.fixtures import corrupt_fat_entry, make_doc_bytes


def test_rejects_non_ole_bytes() -> None:
    with pytest.raises(LegacyDocError, match="OLE"):
        extract_text(b"not a doc file")


def test_extracts_utf16_piece_table_text() -> None:
    result = extract_text(make_doc_bytes("Hello\rlegacy doc"))

    assert result.text == "Hello\nlegacy doc"
    assert result.parser == "legacy-doc"
    assert result.metadata["chars"] == 16
    assert result.metadata["bytes"] == 16
    assert result.metadata["ole_stream_count"] == 2


def test_extracts_compressed_cp1252_piece_table_text() -> None:
    result = extract_text(make_doc_bytes("Caf\xe9 legacy doc", compressed=True))

    assert result.text == "Caf\xe9 legacy doc"


def test_extracts_text_from_1table_stream() -> None:
    result = extract_text(make_doc_bytes("Uses 1Table", use_1table=True))

    assert result.text == "Uses 1Table"


def test_rejects_encrypted_word_document_flag() -> None:
    with pytest.raises(LegacyDocError, match="Encrypted"):
        extract_text(make_doc_bytes(encrypted=True))


def test_rejects_encrypted_package_stream() -> None:
    document = make_doc_bytes(extra_streams={"EncryptedPackage": b"opaque"})

    with pytest.raises(LegacyDocError, match="Encrypted"):
        extract_text(document)


def test_rejects_missing_piece_table() -> None:
    with pytest.raises(LegacyDocError, match="piece table"):
        extract_text(make_doc_bytes(include_piece_table=False))


def test_rejects_files_over_configured_size_limit() -> None:
    document = make_doc_bytes()

    with pytest.raises(LegacyDocError, match="file-size limit"):
        extract_text(document, options=ExtractionOptions(max_file_bytes=100))


def test_rejects_extracted_text_over_configured_size_limit() -> None:
    document = make_doc_bytes("large text")

    with pytest.raises(LegacyDocError, match="extracted text exceeds"):
        extract_text(document, options=ExtractionOptions(max_text_bytes=4))


def test_rejects_cyclic_fat_chain() -> None:
    document = corrupt_fat_entry(make_doc_bytes("A" * 300), sector=2, value=2)

    with pytest.raises(LegacyDocError, match="Cyclic OLE FAT chain"):
        extract_text(document)
