import app


class App:
    def __init__(self, name, min_instances, max_instances, scalers):
        self.name = name
        self.scalers = []
        for scaler in scalers:
            scaler_cls = getattr(app, scaler["type"])
            self.scalers.append(scaler_cls(name, min_instances, max_instances, **scaler))

    def query_scalers(self):
        desired_instance_counts = []
        for scaler in self.scalers:
            desired_instance_counts.append(scaler.get_desired_instance_count())
        return desired_instance_counts

    def get_desired_instance_count(self):
        return max(self.query_scalers())

    def refresh_cf_info(self, cf_attributes):
        self.cf_attributes = cf_attributes
