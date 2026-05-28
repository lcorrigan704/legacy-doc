# legacy-doc

[![Downloads](https://static.pepy.tech/badge/legacy-doc)](https://pepy.tech/project/legacy-doc)

`legacy-doc` is a small, dependency-free Python library for extracting readable text from classic Microsoft Word `.doc` files.

It is intentionally narrow:

- supports OLE Compound File Word 97-2003 `.doc` files
- extracts normalized text from the Word piece table
- rejects encrypted, malformed, non-OLE, or unsafe files clearly
- does not execute macros, embedded objects, links, scripts, or external references
- does not use native binaries, LibreOffice, `antiword`, or third-party parsers

## Install

```bash
pip install legacy-doc
```

## Usage

```python
from legacy_doc import extract_text

with open("document.doc", "rb") as file:
    result = extract_text(file.read())

print(result.text)
print(result.metadata)
```

`metadata` always includes extracted text size fields and lightweight OLE
inventory fields. When present in the document's saved Word metadata, it can
also include values such as title, author, company, page count, word count,
character count, creation time, and last-saved time.

## API

```python
extract_text(document_bytes: bytes, *, options: ExtractionOptions | None = None) -> DocExtractionResult
```

`DocExtractionResult` contains:

- `text`: normalized extracted text
- `parser`: parser name
- `version`: parser version
- `metadata`: lightweight extraction metadata
- `warnings`: non-fatal parser warnings

Example metadata:

```python
{
    "chars": 1200,
    "bytes": 1225,
    "title": "Quarterly Notes",
    "author": "Liam Corrigan",
    "page_count": 4,
    "word_count": 210,
    "has_macros": False,
    "has_embedded_objects": False,
}
```

## Limitations

This is not a full Microsoft Word renderer. It aims to recover readable text safely from common legacy `.doc` files. Formatting fidelity, OCR, images, macros, tracked changes, and embedded object extraction are out of scope.

`page_count` is read from saved Word document metadata when available. It is
not recalculated by rendering the document, so it can be stale if the file was
saved without updating document statistics.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m build
python -m twine check dist/*
```

The test suite includes small generated OLE WordDocument fixtures and malformed corpus cases for parser limits, encryption markers, missing piece tables, and cyclic FAT chains.

## Security

`legacy-doc` treats input files as untrusted binary data. It performs bounded parsing, rejects encrypted documents, and never executes macros or embedded content. Report security issues privately before opening a public issue.
