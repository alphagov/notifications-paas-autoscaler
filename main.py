import logging
import sys

from app.autoscaler import Autoscaler

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/home/vcap/logs/app.log'),
        logging.StreamHandler(sys.stdout),
    ])

autoscaler = Autoscaler()
autoscaler.run()
