from .builder import Builder, Comment, CustomSection, FieldData,  NewLine, Section
from .gen_types import CommentList, GenAny, GenBool, GenDict, GenInt, GenList, GenValue, GenCustom, GenStr


def _append_comment(value: str, comment_separator: str, comment: str | None):
    if comment:
        value = f"{value}{comment_separator}#{comment}"
    return value


def _needs_quotes(key: str) -> bool:
    for ch in key:
        if not ch.isalnum() and ch != "_" and ch != "_":
            return True
    return False


def _sanitize_key(key: str) -> str:
    """
    escape all quotes
    wrap string in quotes if there is any non-alnum non _ or - characters
    """
    key = key.replace('"', '\\"')
    if _needs_quotes(key):
        key = f'"{key}"'
    return key


def _gen_list_to_str(gl: GenList, builder: Builder) -> str:
    values = []
    for val in gl.values:
        values.append(_gen_val_to_str(val, builder))

    if gl.comments is None:
        return "[" + ", ".join(values) + "]"

    lines = ["["]
    comments = gl.comments
    com_sep = builder.config_comment_sep
    indent = builder.config_indent

    for i, val in enumerate(values):
        comment_part = ""
        if i < len(comments):
            comment_part = f"{com_sep}#{comments[i]}"

        lines.append(f"{indent}{val},{comment_part}")
    lines.append("]")

    new_line = builder.config_new_line
    return new_line.join(lines)


def _gen_dict_to_str(gd: GenDict, builder: Builder):
    parts = []
    for k, v in gd.values.items():
        key = _sanitize_key(k)
        value = _gen_val_to_str(v, builder)
        parts.append(f"{key} = {value}")

    return "{" + ", ".join(parts) + "}"


def _wrap_with(s: str, ch: str):
    return f'{ch}{s}{ch}'


def _comment_list(val: CommentList, builder: Builder):
    lines = ["["]
    indent = builder.config_indent
    for comment in val.comments:
        if comment:
            lines.append(f"{indent}#{comment}")
        else:
            lines.append("")
    lines.append("]")
    return builder.config_new_line.join(lines)


def _gen_val_to_str(val: GenValue, builder: Builder) -> str:

    if isinstance(val, GenStr):
        return _wrap_with(val.value.replace('"', '\\"'), '"')
    elif isinstance(val, GenBool):
        return str(val.value).lower()
    elif isinstance(val, GenInt):
        return str(val.value)
    elif isinstance(val, GenList):
        return _gen_list_to_str(val, builder)
    elif isinstance(val, CommentList):
        return _comment_list(val, builder)
    elif isinstance(val, GenDict):
        return _gen_dict_to_str(val, builder)
    elif isinstance(val, GenCustom):
        return _gen_val_to_str(val.config_value, builder)
    elif isinstance(val, GenAny):
        return _gen_val_to_str(val.value, builder)

    assert False, f"can't convert this to a string {val}"


def build_toml(builder: Builder) -> str:
    lines = []
    com_sep = builder.config_comment_sep
    for entry in builder.line_data:
        if isinstance(entry, NewLine):
            lines.append("")
        elif isinstance(entry, Comment):
            lines.append(f"#{entry.value}")
        elif isinstance(entry, Section | CustomSection):
            sec = f"[{entry.name}]"
            comment = entry.comment
            commented = _append_comment(sec, com_sep, comment)
            lines.append(commented)
        elif isinstance(entry, FieldData):
            key = _sanitize_key(entry.key)
            val = _gen_val_to_str(entry.val, builder)
            line = f"{key} = {val}"

            comment = entry.comment
            comment = _append_comment(line, com_sep, comment)
            lines.append(line)

    return builder.config_new_line.join(lines)
