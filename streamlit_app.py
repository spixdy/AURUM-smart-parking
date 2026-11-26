"""Entry point for Streamlit (local, Docker and Streamlit Community Cloud).

Set "Main file path" to `streamlit_app.py` when deploying.
"""
import sys
from pathlib import Path

# make `import aurum` work no matter which directory Streamlit is launched from
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aurum.dashboard import main  # noqa: E402

main()
