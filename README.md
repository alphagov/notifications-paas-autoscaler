# Notify PaaS Autoscaler

Autoscaling agent for the Notify PaaS applications.

Runs every `SCHEDULE_INTERVAL` (currently 5 seconds) interval, checks some metrics and sets the desired instance count accordingly.

## Installation

You need Ruby installed to generate the manifest template.

```
make <env> cf-push
```

Where env can be preview, staging or production.

## Authentication credentials

The application uses a user provided service to read the secret credentials it needs.

Edit the ```credentials/<env>/paas/service/paas-auto-scaler``` file in the notify-credentials repository, which has the following format:

```
{
  "aws_access_key_id": "...",
  "aws_secret_access_key": "...",
  "cf_username": "...",
  "cf_password": "..."
}
```

Update the PaaS user provided services:

```
cd .../notifications-aws/paas
make <env> update-services
```

When you change the service data you have to restage the application (or push it again):

```
cf restage notify-paas-autoscaler
```


## Runnning tests

### Virtualenv

```
mkvirtualenv -p /usr/local/bin/python3 notifications-paas-autoscaler
```
