#!/usr/bin/env bash
# Linux/macOS: create the virtual environment and install dependencies.
set -euo pipefail
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m aurum.model train
echo "Done. Activate with:  source .venv/bin/activate   then:  streamlit run streamlit_app.py"
