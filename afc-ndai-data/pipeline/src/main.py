import logging
import sys
import time
import psycopg
from src.config import settings
from src.ingest_csv import ingest_csv_files
from src.sentiment import MultilingualSentimentAnalyzer, run_sentiment_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("pipeline.main")


def wait_for_db(dsn: str, retries: int = 20, delay_sec: float = 2.0) -> psycopg.Connection:
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg.connect(dsn)
            logger.info("Connexion PostgreSQL etablie.")
            return conn
        except psycopg.OperationalError as exc:
            logger.warning(
                "PostgreSQL indisponible (tentative %d/%d) : %s",
                attempt,
                retries,
                exc,
            )
            time.sleep(delay_sec)
    raise RuntimeError("Impossible de se connecter a PostgreSQL apres plusieurs tentatives.")


def main() -> int:
    conn = wait_for_db(settings.dsn)
    try:
        csv_count = ingest_csv_files(conn, settings.csv_input_dir)
        analyzer = MultilingualSentimentAnalyzer(
            model_name=settings.sentiment_model,
            batch_size=settings.batch_size,
        )
        fb_count = run_sentiment_analysis(conn, analyzer)
        logger.info(
            "Pipeline termine avec succes (CSV inseres=%d, feedbacks analyses=%d).",
            csv_count,
            fb_count,
        )
        return 0
    except Exception:
        logger.exception("Erreur critique lors de l'execution du service pipeline.")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())