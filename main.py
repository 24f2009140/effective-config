
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "true", "1", "yes", "on"
    }


def convert(key, value):
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return to_bool(value)
    return str(value)


def normalize_layer(layer):
    result = {}
    for key, value in layer.items():
        if value is None:
            continue

        key = str(key).lower()

        if key == "num_workers":
            key = "workers"

        result[key] = value

    return result


@app.get("/effective-config")
def effective_config(
    set: list[str] = Query(default=[])
):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    env_name = os.getenv("APP_ENV", "development")
    yaml_file = BASE_DIR / f"config.{env_name}.yaml"

    if yaml_file.exists():
        with open(yaml_file, "r", encoding="utf-8") as file:
            yaml_data = yaml.safe_load(file) or {}
        config.update(normalize_layer(yaml_data))

    # Layer 3: .env file
    env_file = dotenv_values(BASE_DIR / ".env")
    config.update(normalize_layer(env_file))

    # Layer 4: OS environment variables with APP_ prefix
    os_config = {}
    for name, value in os.environ.items():
        if name.startswith("APP_"):
            key = name[4:].lower()
            if key == "env":
                continue
            os_config[key] = value

    config.update(normalize_layer(os_config))

    # Layer 5: CLI-style query overrides
    for item in set:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip().lower()

        if key == "num_workers":
            key = "workers"

        if key:
            config[key] = value

    # Apply types after merging every layer
    result = {
        key: convert(key, value)
        for key, value in config.items()
    }

    # Never return the real secret
    if "api_key" in result:
        result["api_key"] = "****"

    return result
