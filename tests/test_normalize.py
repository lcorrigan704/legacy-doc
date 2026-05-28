from legacy_doc.normalize import normalize_word_text


def test_removes_page_field_lines() -> None:
    text = "Before\rPAGE \\* MERGEFORMAT 1\rAfter"

    assert normalize_word_text(text) == "Before\nAfter"


def test_removes_numpages_field_lines() -> None:
    text = "Before\rNUMPAGES \\* MERGEFORMAT12\rAfter"

    assert normalize_word_text(text) == "Before\nAfter"


def test_removes_combined_page_count_field_line() -> None:
    text = "Before\rPAGE \\* MERGEFORMAT 1 of NUMPAGES \\* MERGEFORMAT12\rAfter"

    assert normalize_word_text(text) == "Before\nAfter"


def test_removes_page_count_field_line_with_separators() -> None:
    text = "Before\rPAGE \\* MERGEFORMAT1 / NUMPAGES \\* MERGEFORMAT 12\rAfter"

    assert normalize_word_text(text) == "Before\nAfter"


def test_keeps_normal_lines() -> None:
    text = "Hello\rlegacy doc"

    assert normalize_word_text(text) == "Hello\nlegacy doc"
