SHELL := bash -eu

default:
	@echo "Specify a target"

.PHONY: format
format:
	black gpsreceiver

.PHONY: type_check
type_check:
	mypy gpsreceiver
