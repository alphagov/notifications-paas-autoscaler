.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: venv/bin/activate ## Create virtualenv if it does not exist

venv/bin/activate:
	test -d venv || virtualenv venv -p python3

.PHONY: dependencies
dependencies: venv ## Install build dependencies
	. venv/bin/activate && pip3 install -r requirements.txt

generate-manifest:
	@erb manifest.yml.erb

preview:
	$(eval export CF_SPACE=preview)
	$(eval export SQS_QUEUE_PREFIX=preview)
	$(eval export STATSD_ENABLED=True)
	$(eval export STATSD_PREFIX=preview)
	@true

staging:
	$(eval export CF_SPACE=staging)
	$(eval export SQS_QUEUE_PREFIX=staging)
	$(eval export CF_MIN_INSTANCE_COUNT=2)
	$(eval export STATSD_ENABLED=True)
	$(eval export STATSD_PREFIX=preview)
	@true

production:
	$(eval export CF_SPACE=production)
	$(eval export SQS_QUEUE_PREFIX=live)
	$(eval export CF_MIN_INSTANCE_COUNT=4)
	$(eval export STATSD_ENABLED=True)
	$(eval export STATSD_PREFIX=preview)
	@true

cf-push:
	$(if ${CF_SPACE},,$(error Must specify CF_SPACE))
	cf target -s ${CF_SPACE}
	cf push -f <(make generate-manifest)
