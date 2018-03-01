class App:
    def __init__(self, name, scaler_classes, **attributes):
        self.name = name
        self.attributes = attributes
        self.attributes['app_name'] = name
        self.scalers = []
        for scaler in scaler_classes:
            self.scalers.append(scaler(**self.attributes))

    def query_scalers(self):
        instance_counts = []
        for scaler in self.scalers:
            instance_counts = scaler.estimate_instance_count()
        return instance_counts

    def get_desired_instance_count(self):
        return max(self.query_scalers())
