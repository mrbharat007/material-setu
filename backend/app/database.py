import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

# Load .env from backend/ or repo root
env_path_backend = Path(__file__).resolve().parents[1] / ".env"
env_path_root = Path(__file__).resolve().parents[2] / ".env"
if env_path_backend.exists():
    load_dotenv(dotenv_path=env_path_backend)
elif env_path_root.exists():
    load_dotenv(dotenv_path=env_path_root)
else:
    load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:9950@127.0.0.1:5432/material_setu",
)


def get_connection():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )
