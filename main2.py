from app import App
from elb_scaler import ElbScaler

App('notify-api', scalers=[ElbScaler('notify-paas-proxy')], limit=2000)
App('notify-delivery-worker-sender', scalers=[
    SqsScaler('notify-paas-proxy'),
    DbScaler('notify-paas-proxy'),
    ScheduledScaler('notify-paas-proxy'),
    ], limit=2000)
