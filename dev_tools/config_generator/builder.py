from dataclasses import dataclass as _dataclass, field as _field
from typing import Self
from .gen_types import CommentList, GenBool, GenInt, GenList, GenValue, GenStr, GenDict
from ._builder_entry import BuilderEntry
from ._config_data import NewLine, Comment
from ._field_data import FieldData
from ._section import Section, CustomSection


@_dataclass
class Builder:
    code_indent: str
    config_indent: str
    config_new_line: str
    code_new_line: str
    config_comment_sep: str
    line_data: list[BuilderEntry] = _field(default_factory=list)
    import_statements: list[str] = _field(default_factory=list)

    def new_line(self, line_count=1) -> Self:
        for _ in range(line_count):
            self._new_line()
        return self

    def add_field(self, key: str, value: GenValue, comment: str | None = None) -> Self:
        self.line_data.append(FieldData(key, value, comment))
        return self

    def add_bool(self, key: str, value: bool, comment: str | None = None) -> Self:
        self.add_field(key, GenBool(value), comment)
        return self

    def add_int(self, key: str, value: int, comment: str | None = None) -> Self:
        self.add_field(key, GenInt(value), comment)
        return self

    def add_str(self, key: str, value: str, comment: str | None = None) -> Self:
        self.add_field(key, GenStr(value), comment)
        return self

    def add_list(self, key: str, values: list[GenValue], value_type: type[GenValue] | None = None, max_length: int | None = None, min_length: int | None = None, comments: list[str] | None = None, comment: None | str = None) -> Self:
        self.add_field(key, GenList(values=values, min_length=min_length,
                       max_length=max_length, value_type=value_type, comments=comments), comment)
        return self

    def add_comment_list(self, key: str, comments: list[str | None], value_type: type[GenValue] | None = None, max_length: int | None = None, min_length: int | None = None,  comment: None | str = None) -> Self:
        self.add_field(key, CommentList(comments=comments, min_length=min_length,
                       max_length=max_length, value_type=value_type), comment)
        return self

    def add_dict(self, key: str, values: dict[str, GenValue], min_length: int | None = None, max_length: int | None = None, key_type: type[GenValue] | None = None,  value_type: type[GenValue] | None = None, comment: str | None = None) -> Self:
        self.add_field(key, GenDict(values=values, min_length=min_length,
                       max_length=max_length, key_type=key_type, value_type=value_type), comment)
        return self

    def add_section(self, name: str, comment: str | None = None) -> Self:
        self.line_data.append(Section(name, comment))
        return self

    def add_custom_section(self, name: str, process_command: str, expected_type: type[GenValue] | None = None) -> Self:
        self.line_data.append(CustomSection(
            name, process_command, expected_type))
        return self

    def comment(self, comment: str) -> Self:
        self.line_data.append(Comment(comment))
        return self

    def _new_line(self):
        self.line_data.append(NewLine())
