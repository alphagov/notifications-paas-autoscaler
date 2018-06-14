.DEFAULT_GOAL := help
GIT_COMMIT ?= $(shell git rev-parse HEAD)
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

generate-config:
	@$(if ${CF_SPACE},,$(error Must specify CF_SPACE))
	@echo "COOLDOWN_SECONDS_AFTER_SCALE_UP: 300" >> data.yml
	@echo "COOLDOWN_SECONDS_AFTER_SCALE_DOWN: 60" >> data.yml
	@echo "DEFAULT_SCHEDULE_SCALE_FACTOR: 0.6" >> data.yml
	@jinja2 --strict --format=yml config.tpl.yml data.yml > config.yml

.PHONY: docker-build
docker-build:
	docker build --pull \
		--build-arg HTTP_PROXY="${HTTP_PROXY}" \
		--build-arg HTTPS_PROXY="${HTTP_PROXY}" \
		--build-arg NO_PROXY="${NO_PROXY}" \
		-t govuk/notify-paas-autoscaler:${GIT_COMMIT} \
		.

.PHONY: test-with-docker
test-with-docker: docker-build
	docker run --rm \
		-e COVERALLS_REPO_TOKEN=${COVERALLS_REPO_TOKEN} \
		-e CIRCLECI=1 \
		-e CI_BUILD_NUMBER=${BUILD_NUMBER} \
		-e CI_BUILD_URL=${BUILD_URL} \
		-e CI_NAME=${CI_NAME} \
		-e CI_BRANCH=${GIT_BRANCH} \
		-e CI_PULL_REQUEST=${CI_PULL_REQUEST} \
		-e http_proxy="${http_proxy}" \
		-e https_proxy="${https_proxy}" \
		-e NO_PROXY="${NO_PROXY}" \
		govuk/notify-paas-autoscaler:${GIT_COMMIT} \
		make test


preview:
	@if [ -f data.yml ]; then rm data.yml; fi
	@echo "---" >> data.yml
	@echo "CF_SPACE: preview" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 1" >> data.yml
	@echo "MIN_INSTANCE_COUNT_HIGH: 1" >> data.yml
	@echo "MIN_INSTANCE_COUNT_LOW: 1" >> data.yml
	@echo "SCHEDULE_SCALER_ENABLED: False" >> data.yml
	@echo "SQS_QUEUE_PREFIX: preview" >> data.yml
	@echo "STATSD_ENABLED: True" >> data.yml
	@$(eval export CF_SPACE=preview)

staging:
	@if [ -f data.yml ]; then rm data.yml; fi
	@echo "---" >> data.yml
	@echo "CF_SPACE: staging" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 20" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 5" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 10" >> data.yml
	@echo "MIN_INSTANCE_COUNT_HIGH: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_LOW: 2" >> data.yml
	@echo "SCHEDULE_SCALER_ENABLED: False" >> data.yml
	@echo "SQS_QUEUE_PREFIX: staging" >> data.yml
	@echo "STATSD_ENABLED: True" >> data.yml
	@$(eval export CF_SPACE=staging)

production:
	@if [ -f data.yml ]; then rm data.yml; fi
	@echo "---" >> data.yml
	@echo "CF_SPACE: production" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 20" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 5" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 10" >> data.yml
	@echo "MIN_INSTANCE_COUNT_HIGH: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_LOW: 2" >> data.yml
	@echo "SCHEDULE_SCALER_ENABLED: True" >> data.yml
	@echo "SQS_QUEUE_PREFIX: live" >> data.yml
	@echo "STATSD_ENABLED: True" >> data.yml
	@$(eval export CF_SPACE=production)

cf-push: generate-config
	$(if ${CF_SPACE},,$(error Must specify CF_SPACE))
	cf target -s ${CF_SPACE}
	cf unbind-service notify-paas-autoscaler notify-db
	cf push -f manifest.yml

.PHONY: flake8
flake8:
	flake8 app/ tests/ --max-line-length=120

.PHONY: test
test: flake8
	@$(eval export CONFIG_PATH=$(shell pwd)/config.yml)
	@$(eval export STATSD_PREFIX=test)
	@$(eval export CF_SPACE=test)
	@if [ -f data.yml ]; then rm data.yml; fi
	@echo "---" >> data.yml
	@echo "CF_SPACE: test" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 20" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 5" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 10" >> data.yml
	@echo "MIN_INSTANCE_COUNT_HIGH: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_LOW: 2" >> data.yml
	@echo "SCHEDULE_SCALER_ENABLED: True" >> data.yml
	@echo "SQS_QUEUE_PREFIX: test" >> data.yml
	@echo "STATSD_ENABLED: False" >> data.yml
	@make generate-config
	pytest -v --cov=app/ tests/
	# run specific test with debugger
	# pytest -s tests/test_autoscaler.py::TestScale::test_scale_paas_app_fewer_instances_recent_scale_up
