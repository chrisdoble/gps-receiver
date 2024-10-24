SHELL := bash -eu

.PHONY: default
default:
	@echo "Specify a target"

.PHONY: clean
clean:
	rm -fr .mypy_cache
	find gpsreceiver -name __pycache__ -exec rm -fr {} \; -prune

.PHONY: format
format:
	isort --profile black gpsreceiver
	black gpsreceiver

.PHONY: type_check
type_check:
	mypy gpsreceiver
