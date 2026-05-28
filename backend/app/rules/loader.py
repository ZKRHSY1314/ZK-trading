from pathlib import Path
from typing import Any

import yaml


def load_rule_config(path: str | Path = "configs/rules.yaml") -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
