from dataclasses import dataclass as _dataclass
from ._builder_entry import BuilderEntry
from .gen_types import GenValue


@_dataclass
class Section(BuilderEntry):
    name: str
    comment: str | None = None


@_dataclass
class CustomSection(BuilderEntry):
    name: str
    process_command: str
    expected_type: type[GenValue] | None = None
    comment: str | None = None
