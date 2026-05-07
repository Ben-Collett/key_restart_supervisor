from ._builder_entry import BuilderEntry
from dataclasses import dataclass as _dataclass


class NewLine(BuilderEntry):
    pass


@_dataclass
class Comment(BuilderEntry):
    value: str
