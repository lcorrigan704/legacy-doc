from legacy_doc.normalize import normalize_word_text


def test_removes_page_field_lines() -> None:
    text = "Before\rPAGE \\* MERGEFORMAT\rAfter"

    assert normalize_word_text(text) == "Before\nAfter"


def test_removes_numpages_field_lines() -> None:
    text = "Before\rNUMPAGES \\* MERGEFORMAT\rAfter"

    assert normalize_word_text(text) == "Before\nAfter"


def test_keeps_normal_lines() -> None:
    text = "Hello\rlegacy doc"

    assert normalize_word_text(text) == "Hello\nlegacy doc"
