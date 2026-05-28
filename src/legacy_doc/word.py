from __future__ import annotations

import struct

from legacy_doc.exceptions import LegacyDocError
from legacy_doc.normalize import normalize_word_text
from legacy_doc.ole import OleReader
from legacy_doc.types import ExtractionOptions


def extract_word_text(document_bytes: bytes, *, options: ExtractionOptions) -> str:
    ole = OleReader(document_bytes, options=options)
    if ole.has_stream("EncryptedPackage"):
        raise LegacyDocError("Encrypted legacy .doc files are not supported")

    word_document = ole.read_stream("WordDocument")
    if len(word_document) < 0x44:
        raise LegacyDocError("WordDocument stream is too small")

    flags = _u16(word_document, 0x0A)
    if flags & 0x0100:
        raise LegacyDocError("Encrypted legacy .doc files are not supported")

    table_stream_name = "1Table" if flags & 0x0200 else "0Table"
    table_stream = ole.read_stream(table_stream_name)

    fc_min = _u32(word_document, 0x18)
    fc_mac = _u32(word_document, 0x1C)
    if fc_mac <= fc_min:
        raise LegacyDocError("Legacy .doc file does not contain readable text ranges")

    clx = _find_clx(table_stream)
    text = _extract_text_from_piece_table(word_document, clx, fc_min, fc_mac)
    text = normalize_word_text(text)
    if not text:
        raise LegacyDocError(".doc extraction produced no text")
    return text


def _find_clx(table_stream: bytes) -> bytes:
    for offset in range(len(table_stream) - 5):
        if table_stream[offset] != 0x02:
            continue
        length = _u32(table_stream, offset + 1)
        start = offset + 5
        end = start + length
        if length < 12 or end > len(table_stream):
            continue
        clx = table_stream[start:end]
        if _looks_like_piece_table(clx):
            return clx
    raise LegacyDocError("Word CLX piece table not found")


def _looks_like_piece_table(clx: bytes) -> bool:
    if len(clx) < 12 or (len(clx) - 4) % 12 != 0:
        return False
    piece_count = (len(clx) - 4) // 12
    cps = [_u32(clx, index * 4) for index in range(piece_count + 1)]
    return all(left <= right for left, right in zip(cps, cps[1:])) and cps[-1] > 0


def _extract_text_from_piece_table(
    word_document: bytes,
    clx: bytes,
    fc_min: int,
    fc_mac: int,
) -> str:
    piece_count = (len(clx) - 4) // 12
    cp_offsets = [_u32(clx, index * 4) for index in range(piece_count + 1)]
    pcd_offset = 4 * (piece_count + 1)
    text_parts: list[str] = []

    for index in range(piece_count):
        cp_start = cp_offsets[index]
        cp_end = cp_offsets[index + 1]
        if cp_end <= cp_start:
            continue

        pcd = clx[pcd_offset + index * 8 : pcd_offset + (index + 1) * 8]
        fc_encoded = _u32(pcd, 2)
        is_compressed = bool(fc_encoded & 0x40000000)
        fc = (fc_encoded & 0x3FFFFFFF) // 2 if is_compressed else fc_encoded
        char_count = cp_end - cp_start
        byte_count = char_count if is_compressed else char_count * 2

        if fc < fc_min or fc > fc_mac or fc + byte_count > len(word_document):
            continue

        raw = word_document[fc : fc + byte_count]
        if is_compressed:
            text_parts.append(raw.decode("cp1252", errors="replace"))
        else:
            text_parts.append(raw.decode("utf-16le", errors="replace"))

    return "".join(text_parts)


def _u16(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise LegacyDocError("Unexpected end of binary Word data")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise LegacyDocError("Unexpected end of binary Word data")
    return struct.unpack_from("<I", data, offset)[0]
