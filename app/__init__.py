import app._compat  # noqa: F401 - Patch pydantic v1 for Python 3.14 before langfuse import

# Load environment variables early (for local dev; Railway provides them automatically)
from dotenv import load_dotenv
load_dotenv()
