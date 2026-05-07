# WARNING: the vibes where strong in this one
from .builder import Builder
from .gen_types import CommentList, GenInt, GenBool, GenStr, GenAny, GenList, GenDict, GenCustom, GenValue
from ._section import Section, CustomSection
from ._field_data import FieldData
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class ProcessedField:
    key: str
    type_indicator: str
    default_value: Any
    value_type: Optional[str]
    min_length: Optional[int]
    max_length: Optional[int]
    key_type: Optional[str]
    parse_command: Optional[str]
    comment: Optional[str]
    config_value_type: Optional[str] = None


def build_python(builder: Builder) -> str:
    code_indent = builder.code_indent
    code_new_line = builder.code_new_line

    sections: dict[str, list[ProcessedField]] = {}
    custom_sections: dict[str, tuple[str, type | None]] = {}
    global_fields: list[ProcessedField] = []
    current_section = None
    imports = ["import math"]
    section_comments: dict[str, str | None] = {}
    invalid_identifier_fields: list[str] = []

    for imp in builder.import_statements:
        if imp not in imports:
            imports.append(imp)

    in_custom_section = False
    for entry in builder.line_data:
        if isinstance(entry, Section):
            in_custom_section = False
            current_section = entry.name
            section_comments[current_section] = entry.comment
            if current_section not in sections:
                sections[current_section] = []
        elif isinstance(entry, CustomSection):
            in_custom_section = True
            custom_sections[entry.name] = (
                entry.process_command, entry.expected_type)
        elif isinstance(entry, FieldData):
            field_info = _process_field(entry)
            if not field_info.key.isidentifier():
                invalid_identifier_fields.append(field_info.key)
            if current_section is None:
                global_fields.append(field_info)
            elif not in_custom_section:
                sections[current_section].append(field_info)

    lines = []
    lines.append("# auto generated")

    for imp in imports:
        lines.append(imp)

    lines.append("")
    lines.append(_generate_expected_classes(code_indent, code_new_line))
    lines.append("")
    lines.append(_generate_check_type(code_indent, code_new_line))
    lines.append("")
    lines.append(_generate_merge_expected(code_indent, code_new_line))
    lines.append("")
    lines.append(_generate_get_expected_map(
        sections, code_indent, code_new_line))
    lines.append("")
    lines.append(_generate_config_class(sections, custom_sections,
                 invalid_identifier_fields, code_indent, code_new_line, section_comments))

    return code_new_line.join(lines)


def _process_field(field_data: FieldData) -> ProcessedField:
    key = field_data.key
    val = field_data.val
    comment = field_data.comment

    if isinstance(val, GenInt):
        return ProcessedField(key, "field", val.value, "int", None, None, None, None, comment)
    elif isinstance(val, GenBool):
        return ProcessedField(key, "field", val.value, "bool", None, None, None, None, comment)
    elif isinstance(val, GenStr):
        return ProcessedField(key, "field", val.value, "str", None, None, None, None, comment)
    elif isinstance(val, GenAny):
        inner = val.value
        if isinstance(inner, GenInt):
            return ProcessedField(key, "field", inner.value, None, None, None, None, None, comment)
        elif isinstance(inner, GenBool):
            return ProcessedField(key, "field", inner.value, None, None, None, None, None, comment)
        elif isinstance(inner, GenStr):
            return ProcessedField(key, "field", inner.value, None, None, None, None, None, comment)
        return ProcessedField(key, "field", _get_default_from_gen(inner), None, None, None, None, None, comment)
    elif isinstance(val, GenList | CommentList):
        value_type = None
        if val.value_type:
            if val.value_type == GenInt:
                value_type = "int"
            elif val.value_type == GenBool:
                value_type = "bool"
            elif val.value_type == GenStr:
                value_type = "str"
        default_values = []
        if isinstance(val, GenList):
            default_values = [_get_default_from_gen(v) for v in val.values]
        return ProcessedField(key, "list", default_values, value_type, val.min_length, val.max_length, None, None, comment)
    elif isinstance(val, GenDict):
        key_type = None
        value_type = None
        if val.key_type:
            if val.key_type == GenStr:
                key_type = "str"
        if val.value_type:
            if val.value_type == GenInt:
                value_type = "int"
            elif val.value_type == GenStr:
                value_type = "str"
        default_dict = {k: _get_default_from_gen(
            v) for k, v in val.values.items()}
        return ProcessedField(key, "dict", default_dict, value_type, val.min_length, val.max_length, key_type, None, comment)
    elif isinstance(val, GenCustom):
        parse_command = val.parse_command
        config_value = val.config_value
        default_val = _get_default_from_gen(config_value)
        python_type = val.python_type
        config_value_type = _get_type_from_gen(config_value)
        return ProcessedField(key, "custom", default_val, python_type, None, None, None, parse_command, comment, config_value_type)

    return ProcessedField(key, "field", None, None, None, None, None, None, comment)


def _get_default_from_gen(gen_val: GenValue):
    if isinstance(gen_val, GenInt):
        return gen_val.value
    elif isinstance(gen_val, GenBool):
        return gen_val.value
    elif isinstance(gen_val, GenStr):
        return gen_val.value
    return None


def _get_type_from_gen(gen_val: GenValue) -> Optional[str]:
    if isinstance(gen_val, GenInt):
        return "int"
    elif isinstance(gen_val, GenBool):
        return "bool"
    elif isinstance(gen_val, GenStr):
        return "str"
    return None


def _format_value(value) -> str:
    if value is None:
        return "None"
    elif isinstance(value, bool):
        return "True" if value else "False"
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    elif isinstance(value, list):
        if not value:
            return "[]"
        items = [_format_value(v) for v in value]
        return "[" + ", ".join(items) + "]"
    elif isinstance(value, dict):
        if not value:
            return "{}"
        items = [f"{_format_value(k)}: {_format_value(
            v)}" for k, v in value.items()]
        return "{" + ", ".join(items) + "}"
    return str(value)


def _needs_quoting(key: str) -> bool:
    import re
    return bool(re.search(r'[^a-zA-Z0-9_-]', key))


def _format_key(key: str) -> str:
    if _needs_quoting(key):
        return repr(key)
    return f'"{key}"'


def _generate_expected_classes(indent: str, new_line: str) -> str:
    lines = []
    i = indent

    lines.append("class _ExpectedField:")
    lines.append(f"{i}def __init__(self, default_value=None, cftype=None):")
    lines.append(f"{i}{i}self.default_value = default_value")
    lines.append(f"{i}{i}self.cftype = cftype")
    lines.append("")
    lines.append("")
    lines.append("class _ExpectedList:")
    lines.append(
        f"{i}def __init__(self, default_value=None, cftype=None, min_length=0, max_length=math.inf):")
    lines.append(f"{i}{i}default_value = default_value or []")
    lines.append(f"{i}{i}self.default_value = default_value")
    lines.append(f"{i}{i}self.cftype = cftype")
    lines.append(f"{i}{i}self.min_length = min_length")
    lines.append(f"{i}{i}self.max_length = max_length")
    lines.append("")
    lines.append("")
    lines.append("class _ExpectedDict:")
    lines.append(
        f"{i}def __init__(self, default_value=None, key_type=None, value_type=None, min_length=0, max_length=math.inf):")
    lines.append(f"{i}{i}default_value = default_value or {{}}")
    lines.append(f"{i}{i}self.default_value = default_value")
    lines.append(f"{i}{i}self.key_type = key_type")
    lines.append(f"{i}{i}self.cftype = value_type")
    lines.append(f"{i}{i}self.min_length = min_length")
    lines.append(f"{i}{i}self.max_length = max_length")

    return new_line.join(lines)


def _generate_check_type(indent: str, new_line: str) -> str:
    lines = []
    i = indent

    lines.append("def _check_type(value, expected_type) -> bool:")
    lines.append(f"{i}if expected_type is None:")
    lines.append(f"{i}{i}return True")
    lines.append(f"{i}if expected_type == bool:")
    lines.append(f"{i}{i}return isinstance(value, bool)")
    lines.append(f"{i}if expected_type == int:")
    lines.append(
        f"{i}{i}return isinstance(value, int) and not isinstance(value, bool)")
    lines.append(f"{i}if expected_type == str:")
    lines.append(f"{i}{i}return isinstance(value, str)")
    lines.append(f"{i}if expected_type == float:")
    lines.append(
        f"{i}{i}return isinstance(value, (int, float)) and not isinstance(value, bool)")
    lines.append(f"{i}if expected_type == list:")
    lines.append(f"{i}{i}return isinstance(value, list)")
    lines.append(f"{i}if expected_type == dict:")
    lines.append(f"{i}{i}return isinstance(value, dict)")
    lines.append(f"{i}return isinstance(value, expected_type)")

    return new_line.join(lines)


def _generate_merge_expected(indent: str, new_line: str) -> str:
    lines = []
    i = indent

    lines.append(
        "def _merge_expected(config_map: dict, expected_map: dict, ignored_sections=set(), ignored_keys=set()) -> dict:")
    lines.append(f"{i}result = {{}}")
    lines.append("")
    lines.append(
        f"{i}for section_name, section_expected in expected_map.items():")
    lines.append(f"{i}{i}result[section_name] = {{}}")
    lines.append(
        f"{i}{i}for field_name, field_expected in section_expected.items():")
    lines.append(
        f"{i}{i}{i}result[section_name][field_name] = field_expected.default_value")
    lines.append("")
    lines.append(f"{i}for section_name, section_config in config_map.items():")
    lines.append(f"{i}{i}if section_name not in expected_map:")
    lines.append(f"{i}{i}{i}if section_name in ignored_sections:")
    lines.append(f"{i}{i}{i}{i}result[section_name] = section_config.copy()")
    lines.append(f"{i}{i}{i}else:")
    lines.append(f'{i}{i}{i}{i}print(f"Unused section: {{section_name}}")')
    lines.append(f"{i}{i}{i}continue")
    lines.append("")
    lines.append(f"{i}{i}if not isinstance(section_config, dict):")
    lines.append(f'{i}{i}{
                 i}print(f"Type error in section \'{{section_name}}\': expected dict, got {{type(section_config).__name__}}")')
    lines.append(f"{i}{i}{i}continue")
    lines.append("")
    lines.append(
        f"{i}{i}for field_name, field_value in section_config.items():")
    lines.append(f"{i}{i}{i}if field_name not in expected_map[section_name]:")
    lines.append(f"{i}{i}{i}{
                 i}if field_name in ignored_keys or section_name in ignored_sections:")
    lines.append(f"{i}{i}{i}{i}{
                 i}result[section_name][field_name] = field_value")
    lines.append(f"{i}{i}{i}{i}else:")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Unused field: {{section_name}}.{{field_name}}")')
    lines.append(f"{i}{i}{i}{i}continue")
    lines.append("")
    lines.append(
        f"{i}{i}{i}field_expected = expected_map[section_name][field_name]")
    lines.append("")
    lines.append(f"{i}{i}{i}if isinstance(field_expected, _ExpectedField):")
    lines.append(
        f"{i}{i}{i}{i}if _check_type(field_value, field_expected.cftype):")
    lines.append(f"{i}{i}{i}{i}{
                 i}result[section_name][field_name] = field_value")
    lines.append(f"{i}{i}{i}{i}else:")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Type error: {{section_name}}.{{field_name}} expected {{field_expected.cftype}}, got {{type(field_value).__name__}}")')
    lines.append("")
    lines.append(f"{i}{i}{i}elif isinstance(field_expected, _ExpectedList):")
    lines.append(f"{i}{i}{i}{i}if not isinstance(field_value, list):")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Type error: {{section_name}}.{{field_name}} expected list, got {{type(field_value).__name__}}")')
    lines.append(f"{i}{i}{i}{
                 i}elif field_expected.cftype and not all(_check_type(v, field_expected.cftype) for v in field_value):")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Type error: {{section_name}}.{{field_name}} expected list of {{field_expected.cftype}}")')
    lines.append(f"{i}{i}{i}{
                 i}elif not (field_expected.min_length <= len(field_value) <= field_expected.max_length):")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Length error: {{section_name}}.{{field_name}} length {{len(field_value)}} not in range [{{field_expected.min_length}}, {{field_expected.max_length}}]")')
    lines.append(f"{i}{i}{i}{i}else:")
    lines.append(f"{i}{i}{i}{i}{
                 i}result[section_name][field_name] = field_value")
    lines.append("")
    lines.append(f"{i}{i}{i}elif isinstance(field_expected, _ExpectedDict):")
    lines.append(f"{i}{i}{i}{i}if not isinstance(field_value, dict):")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Type error: {{section_name}}.{{field_name}} expected dict, got {{type(field_value).__name__}}")')
    lines.append(f"{i}{i}{i}{
                 i}elif field_expected.key_type and not all(_check_type(k, field_expected.key_type) for k in field_value.keys()):")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Type error: {{section_name}}.{{field_name}} expected dict with keys of {{field_expected.key_type}}")')
    lines.append(f"{i}{i}{i}{
                 i}elif field_expected.cftype and not all(_check_type(v, field_expected.cftype) for v in field_value.values()):")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Type error: {{section_name}}.{{field_name}} expected dict with values of {{field_expected.cftype}}")')
    lines.append(f"{i}{i}{i}{
                 i}elif not (field_expected.min_length <= len(field_value) <= field_expected.max_length):")
    lines.append(f'{i}{i}{i}{i}{
                 i}print(f"Length error: {{section_name}}.{{field_name}} length {{len(field_value)}} not in range [{{field_expected.min_length}}, {{field_expected.max_length}}]")')
    lines.append(f"{i}{i}{i}{i}else:")
    lines.append(f"{i}{i}{i}{i}{
                 i}result[section_name][field_name] = field_value")
    lines.append("")
    lines.append(f"{i}return result")

    return new_line.join(lines)


def _generate_get_expected_map(sections: dict[str, list[ProcessedField]], indent: str, new_line: str) -> str:
    lines = []
    i = indent

    # Build compact single-line format with all keys quoted
    section_strs = []
    for section_name, fields in sections.items():
        field_strs = []
        for field in fields:
            key_str = _format_key(field.key)
            if field.type_indicator == "field":
                if field.value_type:
                    field_strs.append(f"{key_str}: _ExpectedField({
                                      _format_value(field.default_value)}, {field.value_type})")
                else:
                    field_strs.append(
                        f"{key_str}: _ExpectedField({_format_value(field.default_value)})")
            elif field.type_indicator == "list":
                parts = f"{key_str}: _ExpectedList({
                    _format_value(field.default_value)}"
                if field.value_type:
                    parts += f", {field.value_type}"
                if field.min_length is not None:
                    parts += f", min_length={field.min_length}"
                if field.max_length is not None:
                    parts += f", max_length={field.max_length}"
                parts += ")"
                field_strs.append(parts)
            elif field.type_indicator == "dict":
                parts = f"{key_str}: _ExpectedDict({
                    _format_value(field.default_value)}"
                if field.key_type:
                    parts += f", key_type={field.key_type}"
                if field.value_type:
                    parts += f", value_type={field.value_type}"
                if field.min_length is not None:
                    parts += f", min_length={field.min_length}"
                if field.max_length is not None:
                    parts += f", max_length={field.max_length}"
                parts += ")"
                field_strs.append(parts)
            elif field.type_indicator == "custom":
                if field.config_value_type:
                    field_strs.append(f"{key_str}: _ExpectedField({
                                      _format_value(field.default_value)}, {field.config_value_type})")
                else:
                    field_strs.append(f"{key_str}: _ExpectedField({
                                      _format_value(field.default_value)})")
        section_strs.append(
            f"{_format_key(section_name)}: {{{', '.join(field_strs)}}}")

    return_line = "{" + ", ".join(section_strs) + "}"

    lines.append("def _get_expected_map():")
    lines.append(f"{i}return {return_line}")

    return new_line.join(lines)


def _generate_config_class(sections: dict[str, list[ProcessedField]], custom_sections: dict, invalid_identifier_fields: list, indent: str, new_line: str, section_comments: dict) -> str:
    lines = []
    i = indent

    section_names = [s for s in sections.keys() if s]
    has_custom = len(custom_sections) > 0

    lines.append("class Config:")
    lines.append(f"{i}def __init__(self, config_map: dict | None = None):")
    lines.append(f"{i}{i}if not config_map:")
    lines.append(f"{i}{i}{i}config_map = {{}}")
    lines.append(f"{i}{i}merged = _merge_expected(")
    lines.append(f"{i}{i}{i}config_map, _get_expected_map()")
    # Build additional arguments for _merge_expected
    merge_args = []
    if invalid_identifier_fields:
        merge_args.append(f"ignored_keys={invalid_identifier_fields}")
    if custom_sections:
        ignored_sections = set(custom_sections.keys())
        merge_args.append(f"ignored_sections={ignored_sections}")
    if merge_args:
        lines.append(f"{i}{i}{i}, {', '.join(merge_args)}")
    lines.append(f"{i}{i})")

    # Initialize regular sections
    for section_name in section_names:
        class_name = _section_class_name(section_name)
        lines.append(f'{i}{i}self.{section_name} = {
                     class_name}(merged["{section_name}"])')

    # Initialize custom sections in __init__
    for cs_name, (process_command, expected_type) in custom_sections.items():
        if expected_type == GenDict:
            lines.append(f'{i}{i}self.{cs_name}: dict = {
                         process_command.replace("$map", "merged")}')
        else:
            lines.append(f'{i}{i}self.{cs_name} = {
                         process_command.replace("$map", "merged")}')

    lines.append("")

    lines.append(f'{i}def update(self, config_map: dict | None = None):')
    lines.append(f'{i}{i}if not config_map:')
    lines.append(f'{i}{i}{i}config_map = {{}}')
    lines.append(f"{i}{i}merged = _merge_expected(")
    lines.append(f"{i}{i}{i}config_map, _get_expected_map()")
    # Build additional arguments for _merge_expected
    merge_args = []
    if invalid_identifier_fields:
        merge_args.append(f"ignored_keys={invalid_identifier_fields}")
    if custom_sections:
        ignored_sections = set(custom_sections.keys())
        merge_args.append(f"ignored_sections={ignored_sections}")
    if merge_args:
        lines.append(f"{i}{i}{i}, {', '.join(merge_args)}")
    lines.append(f"{i}{i})")

    # Update regular sections
    for section_name in section_names:
        class_name = _section_class_name(section_name)
        lines.append(
            f'{i}{i}self.{section_name}.update(merged["{section_name}"])')

    # Update custom sections in update
    for cs_name, (process_command, expected_type) in custom_sections.items():
        if expected_type == GenDict:
            lines.append(f'{i}{i}self.{cs_name}: dict = {
                         process_command.replace("$map", "merged")}')
        else:
            lines.append(f'{i}{i}self.{cs_name} = {
                         process_command.replace("$map", "merged")}')

    lines.append("")

    for section_name in section_names:
        fields = sections[section_name]
        class_name = _section_class_name(section_name)
        lines.append(f"class {class_name}:")
        lines.append(f"{i}def __init__(self, smap: dict):")
        lines.append(f"{i}{i}self.update(smap)")
        lines.append("")
        lines.append(f"{i}def update(self, smap: dict):")
        for field in fields:
            if not field.key.isidentifier():
                continue
            if field.type_indicator == "custom":
                type_hint = ""
                if field.value_type:
                    type_hint = f": {field.value_type}"
                lines.append(f"{i}{i}self.{field.key}{type_hint} = {
                             field.parse_command.replace('$value', 'smap[\"' + field.key + '\"]')}")
            elif field.type_indicator == "list":
                type_hint = f": list[{
                    field.value_type}]" if field.value_type else ": list"
                lines.append(f"{i}{i}self.{field.key}{
                             type_hint} = smap[\"{field.key}\"]")
            elif field.type_indicator == "dict":
                key_type_str = field.key_type if field.key_type else "str"
                val_type_str = field.value_type if field.value_type else "any"
                lines.append(f"{i}{i}self.{field.key}: dict[{key_type_str}, {
                             val_type_str}] = smap[\"{field.key}\"]")
            else:
                type_hint = f": {field.value_type}" if field.value_type else ""
                lines.append(f"{i}{i}self.{field.key}{
                             type_hint} = smap[\"{field.key}\"]")
        lines.append("")

    return new_line.join(lines)


def _section_class_name(section_name: str) -> str:
    return section_name.capitalize() + "Section"
