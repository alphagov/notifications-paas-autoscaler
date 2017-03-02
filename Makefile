.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

generate-manifest:
	@erb manifest.yml.erb

preview:
	$(eval export CF_SPACE=preview)
	@true

staging:
	$(eval export CF_SPACE=staging)
	$(eval export CF_MIN_INSTANCE_COUNT=2)
	@true

production:
	$(eval export CF_SPACE=production)
	$(eval export CF_MIN_INSTANCE_COUNT=2)
	@true

cf-push:
	$(if ${CF_SPACE},,$(error Must specify CF_SPACE))
	cf target -s ${CF_SPACE}
	cf push -f <(make generate-manifest)
