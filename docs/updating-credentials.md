# Updating credentials

The application uses a user provided service to read the secret credentials it needs.

Edit the `credentials/<env>/notify-paas-auto-scaler/paas-environment` file in the notify-credentials repository, which has the following format:

```
{
  "aws_access_key_id": "...",
  "aws_secret_access_key": "...",
  "cf_username": "...",
  "cf_password": "..."
}
```

Next, update the PaaS user provided services:

```
cd .../notifications-aws/paas
make <env> update-services
```

When you change the service data you have to restage the application (or push it again):

```
cf restage notify-paas-autoscaler
```
