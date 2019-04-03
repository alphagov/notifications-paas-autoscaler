# Notify PaaS Autoscaler

Autoscaling agent for the Notify PaaS applications.

Runs every `SCHEDULE_INTERVAL_SECONDS` (currently 5 seconds) interval, checks some metrics and sets the desired instance count accordingly.

## Installation

You need Ruby installed to generate the manifest template.

```
make <env> cf-push
```

Where env can be preview, staging or production.

## Scheduled scaling

The Autoscaler can scale the worker applications based on a schedule defined in the `schedule.yml` file.

The format of the file is:

```
name-of-the-app:
  <workdays|weekends>:
      - HH:MM-HH:MM
      - HH:MM-HH:MM
      - ...
name-of-another-app:
  <workdays|weekends>:
      - HH:MM-HH:MM
      - ...
```

For example, if you need to schedule the research worker to scale on weekends between
9 in the morning and 2 in the afternoon you would add this to the `schedule.yml`:

```
notify-delivery-worker-research:
  weekends:
    - 09:00-14:00
```

The Autoscaler will scale the specified apps to the number of instances equal to `SCHEDULED_SCALE_FACTOR` * `max_instance_count`
unless some other metric requires the instance to scale to a higher number (e.g. a large scheduled job)


## Debugging

Depending on the problem you're facing you can use different approaches to get more information about it:

1. You can see any events related to the Autoscaler app using `cf events notify-paas-autoscaler`. This
will show you deployments or restarts
1. You can tail the logs with `cf logs notify-paas-autoscaler` or, if Autoscaler has crashed, look into the latest logs with `cf logs notify-paas-autoscaler --latest`
1. You can also log onto the box with `cf ssh notify-paas-autoscaler` and see if there are any exceptions logged in
`/home/vcap/logs/app.log`


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


## Running tests

### Virtualenv

```
mkvirtualenv -p /usr/local/bin/python3 notifications-paas-autoscaler
```
