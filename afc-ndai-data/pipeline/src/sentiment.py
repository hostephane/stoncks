import logging
from typing import Tuple
import psycopg
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


class MultilingualSentimentAnalyzer:
    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Chargement du modele sentiment (%s) sur %s...", model_name, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    @staticmethod
    def _normalize_label(raw_label: str) -> str:
        lbl = raw_label.lower().strip()
        if "pos" in lbl or lbl in {"4 stars", "5 stars"}:
            return "positive"
        if "neg" in lbl or lbl in {"1 star", "2 stars"}:
            return "negative"
        return "neutral"

    def predict_batch(self, texts: list[str]) -> list[Tuple[str, float, str]]:
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**encoded)
            probs = torch.softmax(outputs.logits, dim=-1)
            scores, indices = torch.max(probs, dim=-1)

        id2label = self.model.config.id2label
        results: list[Tuple[str, float, str]] = []
        for idx, score in zip(indices.tolist(), scores.tolist()):
            raw_lbl = id2label.get(idx, str(idx))
            norm_lbl = self._normalize_label(raw_lbl)
            # NUMERIC(5, 4) supporte max 0.9999
            clamped_score = min(round(float(score), 4), 0.9999)
            results.append((norm_lbl, clamped_score, raw_lbl))
        return results


def run_sentiment_analysis(conn: psycopg.Connection, analyzer: MultilingualSentimentAnalyzer) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, comment
            FROM campaign_feedbacks
            WHERE sentiment_label IS NULL
              AND comment IS NOT NULL
              AND BTRIM(comment) <> ''
            ORDER BY id ASC;
            """
        )
        rows = cur.fetchall()

    if not rows:
        logger.info("Aucun nouveau feedback a analyser.")
        return 0

    total_updated = 0
    for start in range(0, len(rows), analyzer.batch_size):
        chunk = rows[start : start + analyzer.batch_size]
        ids = [r[0] for r in chunk]
        texts = [str(r[1]) for r in chunk]

        preds = analyzer.predict_batch(texts)

        with conn.cursor() as cur:
            for fb_id, (label, score, _) in zip(ids, preds):
                cur.execute(
                    """
                    UPDATE campaign_feedbacks
                    SET sentiment_label = %s,
                        sentiment_score = %s
                    WHERE id = %s;
                    """,
                    (label, score, fb_id),
                )
        conn.commit()
        total_updated += len(chunk)

    logger.info("Analyse de sentiment terminee : %d feedback(s) mis a jour.", total_updated)
    return total_updated