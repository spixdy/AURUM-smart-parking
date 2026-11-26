# Windows PowerShell: create the virtual environment and install dependencies.
$ErrorActionPreference = "Stop"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m aurum.model train
Write-Host "Done. Activate with:  .\.venv\Scripts\Activate.ps1   then:  streamlit run streamlit_app.py"
