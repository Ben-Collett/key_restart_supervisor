from config_generator import build_python, build_toml, Builder, GenStr
from pathlib import Path


def make_builder() -> Builder:
    builder = Builder(
        code_indent="    ",
        config_indent="  ",
        config_new_line="\n",
        code_new_line="\n",
        config_comment_sep=" ",
    )
    builder.comment(" all options shown are set to there default value")
    builder.new_line()
    builder.comment(" to disable a binding set it's value to an empty string")
    builder.comment(' ex: restart = ""')
    builder.add_section("bindings")

    builder.add_str("restart", "ctrl+windows+r")
    builder.add_str("help", "ctrl+windows+h")

    builder.add_str("stop", "ctrl+windows+q")
    builder.add_str("clear", "ctrl+windows+k")
    builder.add_str("reload", "ctrl+windows+l")
    builder.new_line()
    builder.add_section("supervisor")
    builder.add_bool("tty_restore", True)

    builder.new_line()
    builder.add_section("logging")

    help_info = ["user", "command", "config", "restart",
                 "stop", "clear", "help", "reload", "terminate"]

    values = [GenStr(info) for info in help_info]
    builder.add_list("help_info", values=values,
                     comments=[], value_type=GenStr)
    return builder


def example_config_path() -> str:
    return str(_root_dir()/"example_config.toml")


def python_path() -> str:
    return str(_root_dir()/"config.py")


def make_python(builder: Builder) -> str:
    return build_python(builder)


def make_toml(builder: Builder) -> str:
    return build_toml(builder)


def _root_dir():
    return Path(__file__).resolve().parent.parent
