# Notify PaaS Autoscaler

Autoscaling agent for the Notify PaaS applications.

Runs every few seconds, checks some metrics and sets the desired instance count accordingly. See [the config file](config.tpl.yml) for global and per-app settings. See [the Makefile](Makefile) for per-environment settings.

## To test the application

```
# install dependencies
make bootstrap

make test
```

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
