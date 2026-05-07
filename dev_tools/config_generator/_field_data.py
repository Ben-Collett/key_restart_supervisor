from dataclasses import dataclass as _dataclass
from .gen_types import GenValue
from ._builder_entry import BuilderEntry


@_dataclass
class FieldData(BuilderEntry):
    key: str
    val: GenValue
    comment: str | None = None


class ExampleFieldData(BuilderEntry):
    key: str
    val: GenValue
    comment: str | None = None
