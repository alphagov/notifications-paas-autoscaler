import logging
import sys

from app.autoscaler import Autoscaler
from app.config import config


logging.basicConfig(
    level=logging.WARNING,
    handlers=[
        logging.FileHandler('/home/vcap/logs/app.log'),
        logging.StreamHandler(sys.stdout),
    ])

autoscaler = Autoscaler()
autoscaler.run()
