import os
from datetime import date
from typing import List

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="AFC N.D.A.I Feedback API", version="0.1.0")


class FeedbackItem(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    feedback_date: date
    campaign_id: str = Field(..., min_length=1, max_length=32)
    comment: str = Field(..., min_length=1)


def get_db_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "afc_ndai"),
        user=os.getenv("POSTGRES_USER", "afc_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/afc/api", status_code=201)
def ingest_feedbacks(feedbacks: List[FeedbackItem]):
    if not feedbacks:
        raise HTTPException(status_code=400, detail="Feedback list cannot be empty")

    rows = [
        (item.username, item.feedback_date, item.campaign_id, item.comment)
        for item in feedbacks
    ]

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO campaign_feedbacks (username, feedback_date, campaign_id, comment)
                    VALUES (%s, %s, %s, %s)
                    """,
                    rows,
                )
            conn.commit()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}") from exc

    return {"inserted": len(rows)}