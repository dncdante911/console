import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "license.db"
API_TOKEN = os.getenv("LICENSE_API_TOKEN", "change-me")

app = FastAPI(title="MiniHost License Server")


class IssueRequest(BaseModel):
    api_token: str
    license_key: str
    max_activations: int = 1


class ValidateRequest(BaseModel):
    license_key: str
    machine_id: str


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                license_key TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'active',
                max_activations INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT NOT NULL,
                machine_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(license_key, machine_id)
            )
            """
        )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/issue")
def issue_license(body: IssueRequest):
    if body.api_token != API_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO licenses(license_key, status, max_activations) VALUES(?, 'active', ?)",
            (body.license_key.strip(), body.max_activations),
        )
    return {"status": "ok", "license_key": body.license_key}


@app.post("/api/v1/revoke")
def revoke_license(body: IssueRequest):
    if body.api_token != API_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE licenses SET status = 'revoked' WHERE license_key = ?", (body.license_key.strip(),))
    return {"status": "ok"}


@app.post("/api/v1/validate")
def validate(body: ValidateRequest):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        license_row = conn.execute(
            "SELECT * FROM licenses WHERE license_key = ?",
            (body.license_key.strip(),),
        ).fetchone()
        if not license_row:
            return {"valid": False, "message": "license not found"}
        if license_row["status"] != "active":
            return {"valid": False, "message": "license revoked"}

        conn.execute(
            "INSERT OR IGNORE INTO activations(license_key, machine_id) VALUES(?, ?)",
            (body.license_key.strip(), body.machine_id.strip()),
        )
        count_row = conn.execute(
            "SELECT COUNT(*) AS c FROM activations WHERE license_key = ?",
            (body.license_key.strip(),),
        ).fetchone()
        if count_row["c"] > int(license_row["max_activations"]):
            return {"valid": False, "message": "activation limit exceeded"}

    return {"valid": True, "message": "license active"}
