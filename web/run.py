"""
Run the Albion Navigator web server.
Usage: uv run python -m web.run
"""

import uvicorn
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from web.api import app

if __name__ == "__main__":
    uvicorn.run("web.api:app", host="127.0.0.1", port=8000, reload=True)
