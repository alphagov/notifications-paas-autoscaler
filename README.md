# Notify PaaS Autoscaler

Autoscaling agent for the Notify PaaS applications.

Runs every few seconds, checks some metrics and sets the desired instance count accordingly. See [the config file](config.tpl.yml) for global and per-app settings. See [the Makefile](Makefile) for per-environment settings.

## To test the application

```
# install dependencies
make bootstrap

make test
```

## Further documentation

- [Updating PaaS credentials](docs/updating-credentials.md)
