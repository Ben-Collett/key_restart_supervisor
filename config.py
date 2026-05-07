# auto generated
import math

class _ExpectedField:
    def __init__(self, default_value=None, cftype=None):
        self.default_value = default_value
        self.cftype = cftype


class _ExpectedList:
    def __init__(self, default_value=None, cftype=None, min_length=0, max_length=math.inf):
        default_value = default_value or []
        self.default_value = default_value
        self.cftype = cftype
        self.min_length = min_length
        self.max_length = max_length


class _ExpectedDict:
    def __init__(self, default_value=None, key_type=None, value_type=None, min_length=0, max_length=math.inf):
        default_value = default_value or {}
        self.default_value = default_value
        self.key_type = key_type
        self.cftype = value_type
        self.min_length = min_length
        self.max_length = max_length

def _check_type(value, expected_type) -> bool:
    if expected_type is None:
        return True
    if expected_type == bool:
        return isinstance(value, bool)
    if expected_type == int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == str:
        return isinstance(value, str)
    if expected_type == float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == list:
        return isinstance(value, list)
    if expected_type == dict:
        return isinstance(value, dict)
    return isinstance(value, expected_type)

def _merge_expected(config_map: dict, expected_map: dict, ignored_sections=set(), ignored_keys=set()) -> dict:
    result = {}

    for section_name, section_expected in expected_map.items():
        result[section_name] = {}
        for field_name, field_expected in section_expected.items():
            result[section_name][field_name] = field_expected.default_value

    for section_name, section_config in config_map.items():
        if section_name not in expected_map:
            if section_name in ignored_sections:
                result[section_name] = section_config.copy()
            else:
                print(f"Unused section: {section_name}")
            continue

        if not isinstance(section_config, dict):
            print(f"Type error in section '{section_name}': expected dict, got {type(section_config).__name__}")
            continue

        for field_name, field_value in section_config.items():
            if field_name not in expected_map[section_name]:
                if field_name in ignored_keys or section_name in ignored_sections:
                    result[section_name][field_name] = field_value
                else:
                    print(f"Unused field: {section_name}.{field_name}")
                continue

            field_expected = expected_map[section_name][field_name]

            if isinstance(field_expected, _ExpectedField):
                if _check_type(field_value, field_expected.cftype):
                    result[section_name][field_name] = field_value
                else:
                    print(f"Type error: {section_name}.{field_name} expected {field_expected.cftype}, got {type(field_value).__name__}")

            elif isinstance(field_expected, _ExpectedList):
                if not isinstance(field_value, list):
                    print(f"Type error: {section_name}.{field_name} expected list, got {type(field_value).__name__}")
                elif field_expected.cftype and not all(_check_type(v, field_expected.cftype) for v in field_value):
                    print(f"Type error: {section_name}.{field_name} expected list of {field_expected.cftype}")
                elif not (field_expected.min_length <= len(field_value) <= field_expected.max_length):
                    print(f"Length error: {section_name}.{field_name} length {len(field_value)} not in range [{field_expected.min_length}, {field_expected.max_length}]")
                else:
                    result[section_name][field_name] = field_value

            elif isinstance(field_expected, _ExpectedDict):
                if not isinstance(field_value, dict):
                    print(f"Type error: {section_name}.{field_name} expected dict, got {type(field_value).__name__}")
                elif field_expected.key_type and not all(_check_type(k, field_expected.key_type) for k in field_value.keys()):
                    print(f"Type error: {section_name}.{field_name} expected dict with keys of {field_expected.key_type}")
                elif field_expected.cftype and not all(_check_type(v, field_expected.cftype) for v in field_value.values()):
                    print(f"Type error: {section_name}.{field_name} expected dict with values of {field_expected.cftype}")
                elif not (field_expected.min_length <= len(field_value) <= field_expected.max_length):
                    print(f"Length error: {section_name}.{field_name} length {len(field_value)} not in range [{field_expected.min_length}, {field_expected.max_length}]")
                else:
                    result[section_name][field_name] = field_value

    return result

def _get_expected_map():
    return {"bindings": {"restart": _ExpectedField("ctrl+windows+r", str), "help": _ExpectedField("ctrl+windows+h", str), "stop": _ExpectedField("ctrl+windows+q", str), "clear": _ExpectedField("ctrl+windows+k", str), "reload": _ExpectedField("ctrl+windows+l", str)}, "logging": {"help_info": _ExpectedList(["user", "command", "config", "restart", "stop", "clear", "help", "reload", "terminate"], str)}}

class Config:
    def __init__(self, config_map: dict | None = None):
        if not config_map:
            config_map = {}
        merged = _merge_expected(
            config_map, _get_expected_map()
        )
        self.bindings = BindingsSection(merged["bindings"])
        self.logging = LoggingSection(merged["logging"])

    def update(self, config_map: dict | None = None):
        if not config_map:
            config_map = {}
        merged = _merge_expected(
            config_map, _get_expected_map()
        )
        self.bindings.update(merged["bindings"])
        self.logging.update(merged["logging"])

class BindingsSection:
    def __init__(self, smap: dict):
        self.update(smap)

    def update(self, smap: dict):
        self.restart: str = smap["restart"]
        self.help: str = smap["help"]
        self.stop: str = smap["stop"]
        self.clear: str = smap["clear"]
        self.reload: str = smap["reload"]

class LoggingSection:
    def __init__(self, smap: dict):
        self.update(smap)

    def update(self, smap: dict):
        self.help_info: list[str] = smap["help_info"]
