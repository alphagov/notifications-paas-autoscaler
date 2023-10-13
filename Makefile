.DEFAULT_GOAL := help

CF_ORG ?= govuk-notify
SHELL := /bin/bash

CF_APP = notify-paas-autoscaler
CF_MANIFEST_PATH ?= /tmp/manifest.yml

NOTIFY_CREDENTIALS ?= ~/.notify-credentials

.PHONY: help
help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

generate-config:
	@$(if ${CF_SPACE},,$(error Must specify CF_SPACE))
	@echo "COOLDOWN_SECONDS_AFTER_SCALE_UP: 300" >> data.yml
	@echo "COOLDOWN_SECONDS_AFTER_SCALE_DOWN: 60" >> data.yml
	@echo "DEFAULT_SCHEDULE_SCALE_FACTOR: 0.6" >> data.yml
	@echo "DEFAULT_CPU_PERCENTAGE_THRESHOLD: 60" >> data.yml
	@jinja2 --strict --format=yml config.tpl.yml data.yml > config.yml

preview:
	@if [ -f data.yml ]; then rm data.yml; fi
	@echo "---" >> data.yml
	@echo "CF_SPACE: preview" >> data.yml
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_PERIODIC: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_PERIODIC: 1" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RECEIPTS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RECEIPTS: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SENDER: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SENDER: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_REPORTING: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_REPORTING: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_JOBS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_JOBS: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_BROADCASTS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_BROADCASTS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_API: 1" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RESEARCH: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RESEARCH: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_CALLBACK: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API_SMS_RECEIPTS: 1" >> data.yml
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
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 20" >> data.yml
	@echo "MIN_INSTANCE_COUNT_PERIODIC: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_PERIODIC: 5" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RECEIPTS: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RECEIPTS: 20" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SENDER: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SENDER: 20" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 25" >> data.yml
	@echo "MIN_INSTANCE_COUNT_REPORTING: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_REPORTING: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_JOBS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_JOBS: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_BROADCASTS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_BROADCASTS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API: 25" >> data.yml
	@echo "MIN_INSTANCE_COUNT_API: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RESEARCH: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RESEARCH: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 20" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 5" >> data.yml
	@echo "MAX_INSTANCE_COUNT_CALLBACK: 7" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 10" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API_SMS_RECEIPTS: 15" >> data.yml
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
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 35" >> data.yml
	@echo "MIN_INSTANCE_COUNT_PERIODIC: 6" >> data.yml
	@echo "MAX_INSTANCE_COUNT_PERIODIC: 9" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RECEIPTS: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RECEIPTS: 50" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SENDER: 18" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SENDER: 30" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 18" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 50" >> data.yml
	@echo "MIN_INSTANCE_COUNT_REPORTING: 3" >> data.yml
	@echo "MAX_INSTANCE_COUNT_REPORTING: 3" >> data.yml
	@echo "MIN_INSTANCE_COUNT_JOBS: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_JOBS: 25" >> data.yml
	@echo "MIN_INSTANCE_COUNT_BROADCASTS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_BROADCASTS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API: 35" >> data.yml
	@echo "MIN_INSTANCE_COUNT_API: 35" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RESEARCH: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RESEARCH: 60" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 20" >> data.yml
	@echo "MAX_INSTANCE_COUNT_CALLBACK: 45" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 5" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 10" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API_SMS_RECEIPTS: 15" >> data.yml
	@echo "MIN_INSTANCE_COUNT_HIGH: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_LOW: 2" >> data.yml
	@echo "SCHEDULE_SCALER_ENABLED: True" >> data.yml
	@echo "SQS_QUEUE_PREFIX: live" >> data.yml
	@echo "STATSD_ENABLED: True" >> data.yml
	@$(eval export CF_SPACE=production)

.PHONY: generate-manifest
generate-manifest:
	$(if ${CF_SPACE},,$(error Must specify CF_SPACE))

	$(if $(shell which gpg2), $(eval export GPG=gpg2), $(eval export GPG=gpg))
	$(if ${GPG_PASSPHRASE_TXT}, $(eval export DECRYPT_CMD=echo -n $$$${GPG_PASSPHRASE_TXT} | ${GPG} --quiet --batch --passphrase-fd 0 --pinentry-mode loopback -d), $(eval export DECRYPT_CMD=${GPG} --quiet --batch -d))

	@jinja2 --strict manifest.yml.j2 \
	    -D environment=${CF_SPACE} --format=json \
	    <(${DECRYPT_CMD} ${NOTIFY_CREDENTIALS}/credentials/${CF_SPACE}/${CF_APP}/paas-environment.gpg) 2>&1


.PHONY: cf-deploy
cf-deploy: generate-config ## Deploys the app to Cloud Foundry
	$(if ${CF_SPACE},,$(error Must specify CF_SPACE))
	$(if ${CF_ORG},,$(error Must specify CF_ORG))
	cf target -s ${CF_SPACE} -o ${CF_ORG}
	@cf app --guid ${CF_APP} || exit 1

	# cancel any existing deploys to ensure we can apply manifest (if a deploy is in progress you'll see ScaleDisabledDuringDeployment)
	cf cancel-deployment ${CF_APP} || true

	# generate manifest (including secrets) and write it to CF_MANIFEST_PATH (in /tmp/)
	make -s CF_APP=${CF_APP} generate-manifest > ${CF_MANIFEST_PATH}
	# reads manifest from CF_MANIFEST_PATH
	cf push ${CF_APP} --strategy=rolling -f ${CF_MANIFEST_PATH}
	# delete old manifest file
	rm ${CF_MANIFEST_PATH}


.PHONY: bootstrap
bootstrap:
	pip install -r requirements_for_test.txt

.PHONY: test-data
test-data:
	@if [ -f data.yml ]; then rm data.yml; fi
	@echo "---" >> data.yml
	@echo "CF_SPACE: test" >> data.yml
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW: 20" >> data.yml
	@echo "MIN_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_TEMPLATE_PREVIEW_CELERY: 20" >> data.yml
	@echo "MIN_INSTANCE_COUNT_PERIODIC: 6" >> data.yml
	@echo "MAX_INSTANCE_COUNT_PERIODIC: 9" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RECEIPTS: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RECEIPTS: 20" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SENDER: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SENDER: 20" >> data.yml
	@echo "MIN_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 4" >> data.yml
	@echo "MAX_INSTANCE_COUNT_SAVE_API_NOTIFICATIONS: 25" >> data.yml
	@echo "MIN_INSTANCE_COUNT_REPORTING: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_REPORTING: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_JOBS: 1" >> data.yml
	@echo "MAX_INSTANCE_COUNT_JOBS: 2" >> data.yml
	@echo "MIN_INSTANCE_COUNT_BROADCASTS: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_BROADCASTS: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API: 25" >> data.yml
	@echo "MIN_INSTANCE_COUNT_API: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_RESEARCH: 2" >> data.yml
	@echo "MAX_INSTANCE_COUNT_RESEARCH: 30" >> data.yml
	@echo "MAX_INSTANCE_COUNT_HIGH: 20" >> data.yml
	@echo "MAX_INSTANCE_COUNT_LOW: 5" >> data.yml
	@echo "MAX_INSTANCE_COUNT_CALLBACK: 7" >> data.yml
	@echo "MAX_INSTANCE_COUNT_MEDIUM: 10" >> data.yml
	@echo "MAX_INSTANCE_COUNT_API_SMS_RECEIPTS: 15" >> data.yml
	@echo "MIN_INSTANCE_COUNT_HIGH: 4" >> data.yml
	@echo "MIN_INSTANCE_COUNT_LOW: 2" >> data.yml
	@echo "SCHEDULE_SCALER_ENABLED: True" >> data.yml
	@echo "SQS_QUEUE_PREFIX: test" >> data.yml
	@echo "STATSD_ENABLED: False" >> data.yml

	@$(eval export CONFIG_PATH=$(shell pwd)/config.yml)
	@$(eval export CF_SPACE=test)
	@make generate-config

.PHONY: test
test: test-data
	isort --check-only ./app ./tests
	flake8 app/ tests/ --max-line-length=120
	black --check .
	pytest
	rm config.yml data.yml

.PHONY: freeze-requirements
freeze-requirements: ## Pin all requirements including sub dependencies into requirements.txt
	pip install --upgrade pip-tools
	pip-compile requirements.in
