"""Dev entrypoint with a file-backed SQLite database."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from munshi.config import Settings
from munshi.db import Database
from munshi.service import create_app

if __name__ == "__main__":
    var = Path(__file__).resolve().parent / "var"
    var.mkdir(exist_ok=True)
    db_path = os.environ.get("MUNSHI_DB", str(var / "munshi.db"))
    db = Database(db_path)
    if not db.family("fam_devi"):
        db.seed_demo()
    app = create_app(db=db, settings=Settings.from_env())
    uvicorn.run(
        app,
        host=os.environ.get("MUNSHI_HOST", "127.0.0.1"),
        port=int(os.environ.get("MUNSHI_PORT", "8000")),
    )
