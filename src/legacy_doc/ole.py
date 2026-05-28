from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable

from legacy_doc.exceptions import LegacyDocError
from legacy_doc.types import ExtractionOptions

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
END_OF_CHAIN = 0xFFFFFFFE
FREE_SECTOR = 0xFFFFFFFF
FAT_SECTOR = 0xFFFFFFFD
MINIFAT_SECTOR = 0xFFFFFFFC


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    object_type: int
    start_sector: int
    size: int


class OleReader:
    def __init__(self, data: bytes, *, options: ExtractionOptions) -> None:
        self.options = options
        if len(data) > options.max_file_bytes:
            raise LegacyDocError(".doc file exceeds parser file-size limit")
        if len(data) < 512 or data[:8] != OLE_MAGIC:
            raise LegacyDocError("Only OLE Compound File .doc files are supported")

        self.data = data
        if self._u16(0x1C) != 0xFFFE:
            raise LegacyDocError("Unsupported OLE byte order")

        sector_shift = self._u16(0x1E)
        mini_sector_shift = self._u16(0x20)
        if sector_shift not in {9, 12} or mini_sector_shift != 6:
            raise LegacyDocError("Unsupported OLE sector size")

        self.sector_size = 1 << sector_shift
        self.mini_sector_size = 1 << mini_sector_shift
        self.mini_stream_cutoff = self._u32(0x38)
        self.first_dir_sector = self._u32(0x30)
        self.first_minifat_sector = self._u32(0x3C)
        self.num_minifat_sectors = self._u32(0x40)
        first_difat_sector = self._u32(0x44)
        num_difat_sectors = self._u32(0x48)

        difat = [
            self._u32(offset)
            for offset in range(0x4C, 0x4C + 109 * 4, 4)
            if self._u32(offset) not in {FREE_SECTOR, END_OF_CHAIN}
        ]
        difat.extend(self._read_difat_chain(first_difat_sector, num_difat_sectors))

        self.fat = self._read_fat(difat)
        self.directory = self._read_directory()
        root = self._find_entry("Root Entry")
        self.mini_stream = self._read_regular_stream(root.start_sector, root.size)
        self.minifat = self._read_minifat()

    def read_stream(self, name: str, max_size: int | None = None) -> bytes:
        entry = self._find_entry(name)
        limit = max_size or self.options.max_file_bytes
        if entry.size > limit:
            raise LegacyDocError(f"OLE stream '{name}' exceeds parser limit")
        if entry.size < self.mini_stream_cutoff and entry.object_type == 2:
            return self._read_mini_stream(entry.start_sector, entry.size)
        return self._read_regular_stream(entry.start_sector, entry.size)

    def has_stream(self, name: str) -> bool:
        wanted = name.casefold()
        return any(entry.name.casefold() == wanted for entry in self.directory)

    def try_read_stream(self, name: str, max_size: int | None = None) -> bytes | None:
        if not self.has_stream(name):
            return None
        return self.read_stream(name, max_size=max_size)

    def list_streams(self) -> tuple[str, ...]:
        return tuple(entry.name for entry in self.directory if entry.object_type == 2)

    def _read_difat_chain(self, first_sector: int, count: int) -> list[int]:
        if count == 0 or first_sector in {FREE_SECTOR, END_OF_CHAIN}:
            return []
        result: list[int] = []
        sector = first_sector
        seen: set[int] = set()
        for _ in range(count):
            if sector in seen:
                raise LegacyDocError("Cyclic OLE DIFAT chain")
            seen.add(sector)
            raw = self._sector(sector)
            entries_per_sector = self.sector_size // 4
            result.extend(
                value
                for value in struct.unpack_from(f"<{entries_per_sector - 1}I", raw, 0)
                if value not in {FREE_SECTOR, END_OF_CHAIN}
            )
            sector = struct.unpack_from("<I", raw, self.sector_size - 4)[0]
            if sector == END_OF_CHAIN:
                break
        return result

    def _read_fat(self, fat_sectors: Iterable[int]) -> list[int]:
        fat: list[int] = []
        entries_per_sector = self.sector_size // 4
        for sector in fat_sectors:
            raw = self._sector(sector)
            fat.extend(struct.unpack_from(f"<{entries_per_sector}I", raw, 0))
        return fat

    def _read_minifat(self) -> list[int]:
        if self.num_minifat_sectors == 0 or self.first_minifat_sector in {
            FREE_SECTOR,
            END_OF_CHAIN,
        }:
            return []
        raw = self._read_regular_stream(
            self.first_minifat_sector,
            self.num_minifat_sectors * self.sector_size,
            exact_chain=False,
        )
        return list(struct.unpack_from(f"<{len(raw) // 4}I", raw, 0))

    def _read_directory(self) -> list[DirectoryEntry]:
        raw = self._read_regular_stream(
            self.first_dir_sector,
            self.options.max_file_bytes,
            exact_chain=False,
        )
        entries: list[DirectoryEntry] = []
        for offset in range(0, len(raw) - 127, 128):
            chunk = raw[offset : offset + 128]
            name_len = struct.unpack_from("<H", chunk, 64)[0]
            object_type = chunk[66]
            if object_type == 0 or name_len < 2:
                continue
            try:
                name = chunk[: name_len - 2].decode("utf-16le", errors="strict")
            except UnicodeDecodeError:
                continue
            entries.append(
                DirectoryEntry(
                    name=name,
                    object_type=object_type,
                    start_sector=struct.unpack_from("<I", chunk, 116)[0],
                    size=struct.unpack_from("<Q", chunk, 120)[0],
                )
            )
        if not entries:
            raise LegacyDocError("OLE directory is empty or unreadable")
        return entries

    def _read_regular_stream(
        self,
        start_sector: int,
        size: int,
        *,
        exact_chain: bool = True,
    ) -> bytes:
        if start_sector in {FREE_SECTOR, END_OF_CHAIN}:
            return b""
        chunks: list[bytes] = []
        sector = start_sector
        seen: set[int] = set()
        while sector != END_OF_CHAIN:
            if sector in seen:
                raise LegacyDocError("Cyclic OLE FAT chain")
            if len(seen) > self.options.max_chain_sectors:
                raise LegacyDocError("OLE FAT chain exceeds parser limit")
            seen.add(sector)
            chunks.append(self._sector(sector))
            if sector >= len(self.fat):
                raise LegacyDocError("OLE FAT chain references an invalid sector")
            next_sector = self.fat[sector]
            if next_sector in {FREE_SECTOR, FAT_SECTOR, MINIFAT_SECTOR}:
                raise LegacyDocError("OLE FAT chain references a non-data sector")
            sector = next_sector
            if exact_chain and len(chunks) * self.sector_size >= size:
                break
        return b"".join(chunks)[:size]

    def _read_mini_stream(self, start_sector: int, size: int) -> bytes:
        chunks: list[bytes] = []
        sector = start_sector
        seen: set[int] = set()
        while sector != END_OF_CHAIN:
            if sector in seen:
                raise LegacyDocError("Cyclic OLE MiniFAT chain")
            seen.add(sector)
            offset = sector * self.mini_sector_size
            end = offset + self.mini_sector_size
            if end > len(self.mini_stream):
                raise LegacyDocError("MiniFAT chain references an invalid mini sector")
            chunks.append(self.mini_stream[offset:end])
            if sector >= len(self.minifat):
                raise LegacyDocError("MiniFAT chain references an invalid sector")
            sector = self.minifat[sector]
            if sector in {FREE_SECTOR, FAT_SECTOR, MINIFAT_SECTOR}:
                raise LegacyDocError("MiniFAT chain references a non-data sector")
            if len(chunks) * self.mini_sector_size >= size:
                break
        return b"".join(chunks)[:size]

    def _find_entry(self, name: str) -> DirectoryEntry:
        wanted = name.casefold()
        for entry in self.directory:
            if entry.name.casefold() == wanted:
                return entry
        raise LegacyDocError(f"Required OLE stream '{name}' not found")

    def _sector(self, sector: int) -> bytes:
        start = 512 + sector * self.sector_size
        end = start + self.sector_size
        if sector < 0 or end > len(self.data):
            raise LegacyDocError("OLE sector index is outside the file")
        return self.data[start:end]

    def _u16(self, offset: int) -> int:
        return struct.unpack_from("<H", self.data, offset)[0]

    def _u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self.data, offset)[0]
