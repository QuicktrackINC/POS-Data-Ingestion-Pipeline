import sys
import os

# Ensure the backend directory is in the Python path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Ensure the api/ directory is at the front of sys.path so the generated prisma client is found
api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

# Vercel requires the FastAPI instance to be named `app`
from backend.main import app
