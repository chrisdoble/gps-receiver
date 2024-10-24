SHELL := bash -eu

default:
	@echo "Specify a target"

.PHONY: format
format:
	isort --profile black gpsreceiver
	black gpsreceiver

.PHONY: type_check
type_check:
	mypy gpsreceiver
