VENV := .venv

ifeq ($(OS),Windows_NT)
SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -ExecutionPolicy Bypass -Command
PYTHON := $(VENV)\Scripts\python.exe
BOOTSTRAP_PYTHON := python
KG_GEN_PATH := .\kg-gen
VENV_CREATE := if (!(Test-Path "$(PYTHON)")) { $(BOOTSTRAP_PYTHON) -m venv "$(VENV)" }
RUN_APP := & "$(PYTHON)" -m uvicorn app.main:app --reload
else
SHELL := /bin/sh
.SHELLFLAGS := -ec
PYTHON := $(VENV)/bin/python
BOOTSTRAP_PYTHON := python3
KG_GEN_PATH := ./kg-gen
VENV_CREATE := test -x "$(PYTHON)" || $(BOOTSTRAP_PYTHON) -m venv "$(VENV)"
RUN_APP := "$(PYTHON)" -m uvicorn app.main:app --reload
endif

.PHONY: setup run serve

setup:
	$(VENV_CREATE)
	"$(PYTHON)" -m pip install --upgrade pip
	"$(PYTHON)" -m pip install -r app/requirements.txt
	"$(PYTHON)" -m pip install -e "$(KG_GEN_PATH)"

run: setup
	$(RUN_APP)

serve:
	$(RUN_APP)