class App:
    def __init__(self, name, scaler_classes, **scaler_details):
        self.name = name
        self.scaler_details = scaler_details
        self.scaler_details['app_name'] = name
        self.scalers = []
        for scaler in scaler_classes:
            self.scalers.append(scaler(**self.scaler_details))

    def query_scalers(self):
        desired_instance_counts = []
        for scaler in self.scalers:
            desired_instance_counts.append(scaler.get_desired_instance_count())
        return desired_instance_counts

    def get_desired_instance_count(self):
        return max(self.query_scalers())
