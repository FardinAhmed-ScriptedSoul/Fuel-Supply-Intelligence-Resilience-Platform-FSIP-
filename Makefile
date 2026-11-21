# Hub convenience targets. Every target just calls a script, so `make` is optional on Windows.
.PHONY: help setup check code skills apply-kit kit-dry where list report update sprint eod selftest

help:
	@echo "setup check code skills | apply-kit kit-dry | where list | report update sprint eod | selftest"

setup:    ; bash scripts/setup.sh
check:    ; bash scripts/setup.sh --check
code:     ; bash scripts/setup.sh --code
skills:   ; bash scripts/setup.sh --skills
apply-kit: ; bash scripts/apply-kit.sh
kit-dry:  ; bash scripts/apply-kit.sh --dry-run
where:    ; bash scripts/plan.sh where
list:     ; bash scripts/plan.sh list
report:   ; bash scripts/report.sh daily
update:   ; bash scripts/report.sh update
sprint:   ; bash scripts/report.sh sprint
eod:      ; bash scripts/eod.sh

selftest:
	bash scripts/plan.sh where
	bash scripts/report.sh daily --stdout --no-gh | head -20
