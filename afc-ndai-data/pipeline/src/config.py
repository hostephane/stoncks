import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv("DB_HOST", "db")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME") or "afc_ndai"
    db_user: str = os.getenv("POSTGRES_USER") or os.getenv("DB_USER") or "afc_user"
    db_password: str = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD") or ""

    csv_input_dir: str = os.getenv("CSV_INPUT_DIR", "/app/incoming_csv")
    sentiment_model: str = os.getenv(
        "SENTIMENT_MODEL",
        "cardiffnlp/twitter-xlm-roberta-base-sentiment",
    )
    batch_size: int = int(os.getenv("SENTIMENT_BATCH_SIZE", "16"))

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )


settings = Settings()