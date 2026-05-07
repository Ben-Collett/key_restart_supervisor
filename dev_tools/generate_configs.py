# Generates example_config.toml using gen_thing
from gen_common import make_builder, example_config_path, python_path, make_python, make_toml


def generate_files():
    builder = make_builder()

    # Generate TOML and write to file
    toml_content = make_toml(builder)
    with open(example_config_path(), "w") as f:
        f.write(toml_content)
    print("Generated example_config.toml successfully")
    python_content = make_python(builder)
    with open(python_path(), "w") as f:
        f.write(python_content)
    print("Generated config.py successfully")


if __name__ == "__main__":
    generate_files()
