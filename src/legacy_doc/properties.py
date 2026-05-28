from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone
from typing import Any

from legacy_doc.exceptions import LegacyDocError

SUMMARY_INFORMATION_STREAM = "\x05SummaryInformation"
DOCUMENT_SUMMARY_INFORMATION_STREAM = "\x05DocumentSummaryInformation"

VT_I2 = 0x0002
VT_I4 = 0x0003
VT_BOOL = 0x000B
VT_UI4 = 0x0013
VT_LPSTR = 0x001E
VT_LPWSTR = 0x001F
VT_FILETIME = 0x0040

SUMMARY_PROPERTIES = {
    2: "title",
    3: "subject",
    4: "author",
    5: "keywords",
    6: "comments",
    7: "template",
    8: "last_author",
    9: "revision_number",
    11: "last_printed_at",
    12: "created_at",
    13: "last_saved_at",
    14: "page_count",
    15: "word_count",
    16: "character_count",
    18: "application_name",
}

DOCUMENT_SUMMARY_PROPERTIES = {
    5: "line_count",
    6: "paragraph_count",
    14: "manager",
    15: "company",
    17: "character_count_with_spaces",
}


def parse_summary_information(data: bytes) -> dict[str, object]:
    return _parse_property_stream(data, SUMMARY_PROPERTIES)


def parse_document_summary_information(data: bytes) -> dict[str, object]:
    return _parse_property_stream(data, DOCUMENT_SUMMARY_PROPERTIES)


def _parse_property_stream(data: bytes, property_names: dict[int, str]) -> dict[str, object]:
    if len(data) < 48:
        raise LegacyDocError("OLE property stream is too small")
    if _u16(data, 0) != 0xFFFE:
        raise LegacyDocError("Unsupported OLE property stream byte order")

    section_count = _u32(data, 24)
    if section_count < 1:
        raise LegacyDocError("OLE property stream does not contain sections")

    section_offset = _u32(data, 44)
    if section_offset >= len(data):
        raise LegacyDocError("OLE property section offset is outside the stream")

    return _parse_property_section(data, section_offset, property_names)


def _parse_property_section(
    data: bytes,
    section_offset: int,
    property_names: dict[int, str],
) -> dict[str, object]:
    if section_offset + 8 > len(data):
        raise LegacyDocError("OLE property section is truncated")

    section_size = _u32(data, section_offset)
    property_count = _u32(data, section_offset + 4)
    section_end = section_offset + section_size
    if section_end > len(data):
        raise LegacyDocError("OLE property section is truncated")
    table_end = section_offset + 8 + property_count * 8
    if table_end > section_end:
        raise LegacyDocError("OLE property table is truncated")

    property_offsets: dict[int, int] = {}
    for index in range(property_count):
        entry_offset = section_offset + 8 + index * 8
        property_id = _u32(data, entry_offset)
        value_offset = _u32(data, entry_offset + 4)
        absolute_offset = section_offset + value_offset
        if absolute_offset + 4 > section_end:
            raise LegacyDocError("OLE property value is outside the section")
        property_offsets[property_id] = absolute_offset

    codepage = 1252
    if 1 in property_offsets:
        codepage_property = _parse_typed_property(
            data,
            property_offsets[1],
            section_end,
            codepage,
        )
        if isinstance(codepage_property, int):
            codepage = codepage_property

    properties: dict[int, Any] = {}
    for property_id, absolute_offset in property_offsets.items():
        properties[property_id] = _parse_typed_property(
            data,
            absolute_offset,
            section_end,
            codepage,
        )

    result: dict[str, object] = {}
    for property_id, name in property_names.items():
        value = properties.get(property_id)
        if value not in {None, ""}:
            result[name] = value
    return result


def _parse_typed_property(
    data: bytes,
    offset: int,
    section_end: int,
    codepage: int,
) -> object | None:
    value_type = _u16(data, offset)
    value_offset = offset + 4

    if value_type == VT_I2:
        return _i16(data, value_offset)
    if value_type == VT_I4:
        return _i32(data, value_offset)
    if value_type == VT_UI4:
        return _u32(data, value_offset)
    if value_type == VT_BOOL:
        return _i16(data, value_offset) != 0
    if value_type == VT_FILETIME:
        return _parse_filetime(_u64(data, value_offset))
    if value_type == VT_LPSTR:
        return _parse_lpstr(data, value_offset, section_end, codepage)
    if value_type == VT_LPWSTR:
        return _parse_lpwstr(data, value_offset, section_end)
    return None


def _parse_lpstr(data: bytes, offset: int, section_end: int, codepage: int) -> str:
    byte_count = _u32(data, offset)
    start = offset + 4
    end = start + byte_count
    if end > section_end:
        raise LegacyDocError("OLE LPSTR property is truncated")
    raw = data[start:end].rstrip(b"\x00")
    encoding = "utf-16le" if codepage == 1200 else f"cp{codepage}"
    try:
        return raw.decode(encoding, errors="replace")
    except LookupError:
        return raw.decode("cp1252", errors="replace")


def _parse_lpwstr(data: bytes, offset: int, section_end: int) -> str:
    char_count = _u32(data, offset)
    start = offset + 4
    end = start + char_count * 2
    if end > section_end:
        raise LegacyDocError("OLE LPWSTR property is truncated")
    raw = data[start:end]
    if raw.endswith(b"\x00\x00"):
        raw = raw[:-2]
    return raw.decode("utf-16le", errors="replace")


def _parse_filetime(value: int) -> str | None:
    if value == 0:
        return None
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return (epoch + timedelta(microseconds=value // 10)).isoformat()


def _u16(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise LegacyDocError("Unexpected end of OLE property stream")
    return struct.unpack_from("<H", data, offset)[0]


def _i16(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise LegacyDocError("Unexpected end of OLE property stream")
    return struct.unpack_from("<h", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise LegacyDocError("Unexpected end of OLE property stream")
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise LegacyDocError("Unexpected end of OLE property stream")
    return struct.unpack_from("<i", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    if offset + 8 > len(data):
        raise LegacyDocError("Unexpected end of OLE property stream")
    return struct.unpack_from("<Q", data, offset)[0]
