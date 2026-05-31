from pathlib import Path
from typing import Any

import yaml


def load_rule_config(path: str | Path = "configs/rules.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists() and not config_path.is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        config_path = backend_root / config_path
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
