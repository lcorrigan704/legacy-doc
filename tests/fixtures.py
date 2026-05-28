from __future__ import annotations

import struct
from datetime import datetime, timezone
from math import ceil
from typing import Any

END_OF_CHAIN = 0xFFFFFFFE
FREE_SECTOR = 0xFFFFFFFF
FAT_SECTOR = 0xFFFFFFFD
SECTOR_SIZE = 512
SUMMARY_INFORMATION_STREAM = "\x05SummaryInformation"
DOCUMENT_SUMMARY_INFORMATION_STREAM = "\x05DocumentSummaryInformation"
VT_I2 = 0x0002
VT_I4 = 0x0003
VT_LPSTR = 0x001E
VT_FILETIME = 0x0040


def make_doc_bytes(
    text: str = "Hello legacy doc",
    *,
    compressed: bool = False,
    encrypted: bool = False,
    use_1table: bool = False,
    include_piece_table: bool = True,
    summary_properties: dict[int, Any] | None = None,
    document_summary_properties: dict[int, Any] | None = None,
    extra_streams: dict[str, bytes] | None = None,
) -> bytes:
    """Build a tiny Word 97-2003-like OLE file for parser regression tests."""
    flags = 0
    if encrypted:
        flags |= 0x0100
    if use_1table:
        flags |= 0x0200

    text_bytes = text.encode("cp1252") if compressed else text.encode("utf-16le")
    fc_min = 0x44
    fc_mac = fc_min + len(text_bytes)

    word_document = bytearray(fc_mac)
    struct.pack_into("<H", word_document, 0x0A, flags)
    struct.pack_into("<II", word_document, 0x18, fc_min, fc_mac)
    word_document[fc_min:fc_mac] = text_bytes

    table_stream = b"not a piece table"
    if include_piece_table:
        char_count = len(text)
        fc_encoded = (fc_min * 2) | 0x40000000 if compressed else fc_min
        piece_table = (
            struct.pack("<II", 0, char_count)
            + b"\x00\x00"
            + struct.pack("<I", fc_encoded)
            + b"\x00\x00"
        )
        table_stream = b"\x02" + struct.pack("<I", len(piece_table)) + piece_table

    table_name = "1Table" if use_1table else "0Table"
    streams = {
        "WordDocument": bytes(word_document),
        table_name: table_stream,
        **(extra_streams or {}),
    }
    if summary_properties is not None:
        streams[SUMMARY_INFORMATION_STREAM] = make_property_stream(summary_properties)
    if document_summary_properties is not None:
        streams[DOCUMENT_SUMMARY_INFORMATION_STREAM] = make_property_stream(
            document_summary_properties
        )
    return make_ole_file(streams)


def make_property_stream(properties: dict[int, Any]) -> bytes:
    properties = {1: 1252, **properties}
    values = bytearray()
    entries: list[tuple[int, int]] = []
    value_start = 8 + len(properties) * 8

    for property_id, value in properties.items():
        entries.append((property_id, value_start + len(values)))
        values.extend(_property_value(value))
        while len(values) % 4:
            values.append(0)

    section_size = value_start + len(values)
    section = bytearray()
    section.extend(struct.pack("<II", section_size, len(properties)))
    for property_id, offset in entries:
        section.extend(struct.pack("<II", property_id, offset))
    section.extend(values)

    header = bytearray()
    header.extend(struct.pack("<HHI", 0xFFFE, 0, 0))
    header.extend(b"\x00" * 16)
    header.extend(struct.pack("<I", 1))
    header.extend(b"\x00" * 16)
    header.extend(struct.pack("<I", 48))
    return bytes(header) + bytes(section)


def make_ole_file(streams: dict[str, bytes]) -> bytes:
    sector_payloads: list[bytes] = [b"", b""]
    stream_locations: dict[str, tuple[int, int]] = {}
    fat_entries = [END_OF_CHAIN, FAT_SECTOR]

    for name, payload in streams.items():
        start_sector = len(sector_payloads)
        sector_count = max(1, ceil(len(payload) / SECTOR_SIZE))
        stream_locations[name] = (start_sector, len(payload))
        padded = payload.ljust(sector_count * SECTOR_SIZE, b"\x00")
        for index in range(sector_count):
            sector_payloads.append(
                padded[index * SECTOR_SIZE : (index + 1) * SECTOR_SIZE]
            )
            current_sector = start_sector + index
            next_sector = (
                END_OF_CHAIN if index == sector_count - 1 else current_sector + 1
            )
            fat_entries.append(next_sector)

    directory = bytearray()
    directory.extend(_directory_entry("Root Entry", 5, END_OF_CHAIN, 0))
    for name, (start_sector, size) in stream_locations.items():
        directory.extend(_directory_entry(name, 2, start_sector, size))
    directory_payload = bytes(directory)
    directory_sector_count = max(1, ceil(len(directory_payload) / SECTOR_SIZE))
    directory_payload = directory_payload.ljust(
        directory_sector_count * SECTOR_SIZE,
        b"\x00",
    )
    sector_payloads[0] = directory_payload[:SECTOR_SIZE]
    if directory_sector_count > 1:
        first_extra_directory_sector = len(sector_payloads)
        fat_entries[0] = first_extra_directory_sector
        for index in range(1, directory_sector_count):
            sector_payloads.append(
                directory_payload[index * SECTOR_SIZE : (index + 1) * SECTOR_SIZE]
            )
            current_sector = first_extra_directory_sector + index - 1
            next_sector = (
                END_OF_CHAIN
                if index == directory_sector_count - 1
                else current_sector + 1
            )
            fat_entries.append(next_sector)
    sector_payloads[1] = struct.pack(
        "<128I",
        *fat_entries[:128],
        *([FREE_SECTOR] * (128 - len(fat_entries[:128]))),
    )

    header = bytearray(SECTOR_SIZE)
    header[:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<H", header, 0x1A, 3)
    struct.pack_into("<H", header, 0x1C, 0xFFFE)
    struct.pack_into("<H", header, 0x1E, 9)
    struct.pack_into("<H", header, 0x20, 6)
    struct.pack_into("<I", header, 0x2C, 1)
    struct.pack_into("<I", header, 0x30, 0)
    struct.pack_into("<I", header, 0x38, 0)
    struct.pack_into("<I", header, 0x3C, END_OF_CHAIN)
    struct.pack_into("<I", header, 0x40, 0)
    struct.pack_into("<I", header, 0x44, END_OF_CHAIN)
    struct.pack_into("<I", header, 0x48, 0)
    struct.pack_into("<I", header, 0x4C, 1)
    for offset in range(0x50, 0x4C + 109 * 4, 4):
        struct.pack_into("<I", header, offset, FREE_SECTOR)

    return bytes(header) + b"".join(sector_payloads)


def corrupt_fat_entry(document: bytes, sector: int, value: int) -> bytes:
    data = bytearray(document)
    fat_offset = SECTOR_SIZE + SECTOR_SIZE + sector * 4
    struct.pack_into("<I", data, fat_offset, value)
    return bytes(data)


def _property_value(value: Any) -> bytes:
    if isinstance(value, datetime):
        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        filetime = int((value.astimezone(timezone.utc) - epoch).total_seconds() * 10**7)
        return struct.pack("<HHQ", VT_FILETIME, 0, filetime)
    if isinstance(value, str):
        raw = value.encode("cp1252") + b"\x00"
        return struct.pack("<HHI", VT_LPSTR, 0, len(raw)) + raw
    if isinstance(value, int):
        if -32768 <= value <= 32767:
            return struct.pack("<HHh", VT_I2, 0, value)
        return struct.pack("<HHi", VT_I4, 0, value)
    raise TypeError(f"Unsupported property fixture value: {value!r}")


def _directory_entry(name: str, object_type: int, start_sector: int, size: int) -> bytes:
    raw = bytearray(128)
    encoded_name = name.encode("utf-16le") + b"\x00\x00"
    raw[: len(encoded_name)] = encoded_name
    struct.pack_into("<H", raw, 64, len(encoded_name))
    raw[66] = object_type
    struct.pack_into("<III", raw, 68, FREE_SECTOR, FREE_SECTOR, FREE_SECTOR)
    struct.pack_into("<I", raw, 116, start_sector)
    struct.pack_into("<Q", raw, 120, size)
    return bytes(raw)
