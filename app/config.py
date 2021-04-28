import logging
import os
from pathlib import Path

import yaml

from app.exceptions import CannotLoadConfig


def read_config():
    config_path = Path(os.environ.get('CONFIG_PATH', './../config.yml')).resolve()
    try:
        with open(config_path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        msg = "Could not load config from path {}: {}".format(config_path, str(e))
        logging.critical(msg)
        raise CannotLoadConfig(msg)


config = read_config()
