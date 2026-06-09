import sys
import os

# Ensure the backend directory is in the Python path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Vercel requires the FastAPI instance to be named `app`
from backend.main import app
