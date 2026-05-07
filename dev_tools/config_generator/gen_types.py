from dataclasses import dataclass as _dataclass


class GenValue:
    pass


@_dataclass
class GenInt(GenValue):
    value: int


@_dataclass
class GenAny(GenValue):
    value: GenValue


@_dataclass
class GenStr(GenValue):
    value: str


@_dataclass
class GenBool(GenValue):
    value: bool


@_dataclass
class GenDict(GenValue):
    values: dict[str, GenValue]
    min_length: int | None = None
    max_length: int | None = None
    key_type: type[GenValue] | None = None
    value_type: type[GenValue] | None = None


@_dataclass
class GenList(GenValue):
    values: list[GenValue]
    min_length: int | None = None
    max_length: int | None = None
    value_type: type[GenValue] | None = None
    comments: list[str] | None = None


@_dataclass
class CommentList(GenValue):
    comments: list[str | None]
    value_type: type[GenValue] | None = None
    min_length: int | None = None
    max_length: int | None = None


@_dataclass
class GenCustom(GenValue):
    parse_command: str
    config_value: GenValue
    python_type: str
    code_type: str | None = None
