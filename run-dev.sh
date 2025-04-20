#!/bin/bash
echo "Watching for changes and auto-reloading..."

source venv/bin/activate

exec watchmedo auto-restart \
  --directory=./ \
  --pattern="*.py" \
  --recursive \
  -- bash -c 'export FLASK_DEBUG=1 && python run.py'