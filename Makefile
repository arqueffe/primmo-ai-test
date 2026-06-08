SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -ExecutionPolicy Bypass -Command

VENV := .venv
PYTHON := $(VENV)\Scripts\python.exe
PIP := $(VENV)\Scripts\pip.exe
UVICORN := $(VENV)\Scripts\uvicorn.exe

.PHONY: setup run

setup:
	if (!(Test-Path "$(PYTHON)")) { python -m venv "$(VENV)" }
	& "$(PYTHON)" -m pip install --upgrade pip
	& "$(PIP)" install -r app/requirements.txt
	& "$(PIP)" install -e .\kg-gen

run: setup
	$$env:PYTHONPATH = "$$PWD;$$PWD\app"
	& "$(UVICORN)" app.main:app --reload