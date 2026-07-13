.PHONY: handoff-validate handoff-list

handoff-validate:
	python tools/verify_handoff.py

handoff-list:
	python tools/print_authorization.py
