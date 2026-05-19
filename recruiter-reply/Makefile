VENV := .venv
PYTHON := $(VENV)/bin/python

.PHONY: all auth

all: credentials.json $(VENV) token.json

credentials.json:
	@echo "Error: credentials.json not found."
	@echo "Download OAuth2 credentials from Google Cloud Console and save to:"
	@echo "  ~/.claude/skills/recruiter-reply/credentials.json"
	@echo "See README.md for instructions."
	@exit 1

$(VENV):
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

token.json: $(VENV)
	$(PYTHON) gmail_helper.py auth

auth:
	$(PYTHON) gmail_helper.py auth
