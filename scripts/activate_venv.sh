#!/usr/bin/env bash

PROJECT_DIR="~/git/muilti-agents-ocp-builds"
VENV_PATH="$PROJECT_DIR/.venv"
REQ_FILE="$PROJECT_DIR/requirements.txt"

if [ ! -d "$VENV_PATH" ]; then
  echo "Virtual environment not found: $VENV_PATH"
  echo "Creating it now..."
  python3 -m venv "$VENV_PATH" || {
    echo "Failed to create virtual environment"
    return 1 2>/dev/null || exit 1
  }
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate" || {
  echo "Failed to activate virtual environment"
  return 1 2>/dev/null || exit 1
}

echo "Activated venv: $VENV_PATH"
python -m pip install --upgrade pip

if [ -f "$REQ_FILE" ]; then
  pip install -r "$REQ_FILE" || {
    echo "Failed to install requirements"
    return 1 2>/dev/null || exit 1
  }
  echo "Requirements installed from $REQ_FILE"
else
  echo "requirements.txt not found at $REQ_FILE"
fi

which python
echo "VIRTUAL_ENV=$VIRTUAL_ENV"
