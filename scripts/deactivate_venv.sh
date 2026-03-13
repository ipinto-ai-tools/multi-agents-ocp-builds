#!/usr/bin/env bash

if declare -f deactivate >/dev/null 2>&1; then
  deactivate
  echo "Virtual environment deactivated"
else
  echo "No active virtual environment found in this shell"
fi
