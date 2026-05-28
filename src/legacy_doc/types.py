from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

PARSER_NAME = "legacy-doc"
PARSER_VERSION = "0.2.0"


@dataclass(frozen=True)
class ExtractionOptions:
    max_file_bytes: int = 25 * 1024 * 1024
    max_text_bytes: int = 5 * 1024 * 1024
    max_chain_sectors: int = 200_000


@dataclass(frozen=True)
class DocExtractionResult:
    text: str
    parser: str = PARSER_NAME
    version: str = PARSER_VERSION
    metadata: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
