import logging
import math

from app.base_scalers import PaasBaseScaler
from app.config import config


class CpuScaler(PaasBaseScaler):
    def __init__(self, app_name, min_instances, max_instances, **kwargs):
        super().__init__(app_name, min_instances, max_instances)
        self.threshold = kwargs.get('threshold', config['SCALERS']['DEFAULT_CPU_PERCENTAGE_THRESHOLD'])

    def _get_desired_instance_count(self):
        logging.debug('Processing {}'.format(self.app_name))
        total_cpu = sum(self._get_cpu_percentages())
        logging.debug('Total CPU percentage: {}'.format(total_cpu))
        desired_instance_count = int(math.ceil(total_cpu / float(self.threshold)))

        return desired_instance_count

    def _get_cpu_percentages(self):
        paas_app = self.paas_client.get_app_stats(self.app_name)
        return (instance['stats']['usage']['cpu']*100 for instance in paas_app.values())
