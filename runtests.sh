#!/usr/bin/env bash
# Test runner script with useful pytest options
COVERAGE_ARGS='--cov --cov-report=term --cov-report=html'

# Run unit tests first (and with multiprocessing) to fail quickly if there are issues
pytest tests/unit --numprocesses=auto $COVERAGE_ARGS
pytest tests/integration --cov-append $COVERAGE_ARGS
