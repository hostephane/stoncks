import hashlib
import logging
from pathlib import Path
import pandas as pd
import psycopg

logger = logging.getLogger(__name__)


def ensure_ingestion_tracking(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ingested_csv_rows (
                row_hash TEXT PRIMARY KEY,
                source_file TEXT NOT NULL,
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
    conn.commit()


def _compute_row_hash(row: pd.Series, source_file: str) -> str:
    payload = f"{source_file}|" + "|".join(
        "" if pd.isna(v) else str(v).strip() for v in row.values
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ingest_sales_df(conn: psycopg.Connection, df: pd.DataFrame, file_name: str) -> int:
    required_cols = [
        "username",
        "sale_date",
        "country",
        "product",
        "quantity",
        "unit_price",
        "total_amount",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.warning("Fichier %s ignore (sales) : colonnes manquantes %s", file_name, missing)
        return 0

    df = df.copy()
    df["username"] = df["username"].astype(str).str.strip()
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="raise").dt.date
    df["country"] = df["country"].astype(str).str.strip()
    df["product"] = df["product"].astype(str).str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="raise").astype(int)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="raise")
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="raise")

    inserted = 0
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            row_hash = _compute_row_hash(row, file_name)
            cur.execute(
                """
                INSERT INTO ingested_csv_rows (row_hash, source_file)
                VALUES (%s, %s)
                ON CONFLICT (row_hash) DO NOTHING
                RETURNING row_hash;
                """,
                (row_hash, file_name),
            )
            if cur.fetchone() is None:
                continue

            cur.execute(
                """
                INSERT INTO raw_sales (
                    username, sale_date, country, product, quantity, unit_price, total_amount
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    row["username"],
                    row["sale_date"],
                    row["country"],
                    row["product"],
                    int(row["quantity"]),
                    float(row["unit_price"]),
                    float(row["total_amount"]),
                ),
            )
            inserted += 1

    conn.commit()
    return inserted


def _ingest_campaign_products_df(
    conn: psycopg.Connection, df: pd.DataFrame, file_name: str
) -> int:
    # Accepte campaign_id ou campaign / product
    if "campaign_id" not in df.columns and "campaign" in df.columns:
        df = df.rename(columns={"campaign": "campaign_id"})

    if "campaign_id" not in df.columns or "product" not in df.columns:
        logger.warning(
            "Fichier %s ignore (campaign_products) : colonnes attendues campaign_id, product (trouvees : %s)",
            file_name,
            list(df.columns),
        )
        return 0

    df = df.copy()
    df["campaign_id"] = df["campaign_id"].astype(str).str.strip()
    df["product"] = df["product"].astype(str).str.strip()
    df = df[(df["campaign_id"] != "") & (df["product"] != "")].drop_duplicates(
        subset=["campaign_id", "product"]
    )

    inserted = 0
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            cur.execute(
                """
                INSERT INTO raw_campaign_products (campaign_id, product)
                VALUES (%s, %s)
                ON CONFLICT (campaign_id, product) DO NOTHING;
                """,
                (row["campaign_id"], row["product"]),
            )
            inserted += cur.rowcount

    conn.commit()
    return inserted


def ingest_csv_files(conn: psycopg.Connection, csv_dir: str) -> int:
    folder = Path(csv_dir)
    if not folder.exists():
        logger.warning("Dossier CSV introuvable : %s", csv_dir)
        return 0

    csv_files = sorted(folder.rglob("*.csv"))
    if not csv_files:
        logger.info("Aucun fichier CSV trouve dans %s", csv_dir)
        return 0

    ensure_ingestion_tracking(conn)
    total_inserted = 0

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        if df.empty:
            continue

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        name_lower = csv_path.name.lower()

        if "campaign" in name_lower and "product" in name_lower:
            count = _ingest_campaign_products_df(conn, df, csv_path.name)
            logger.info("CSV %s -> raw_campaign_products : %d ligne(s) inseree(s).", csv_path.name, count)
            total_inserted += count
        elif "sale" in name_lower or "quantity" in df.columns:
            count = _ingest_sales_df(conn, df, csv_path.name)
            logger.info("CSV %s -> raw_sales : %d ligne(s) inseree(s).", csv_path.name, count)
            total_inserted += count
        else:
            logger.info("CSV %s ignore (type non reconnu).", csv_path.name)

    return total_inserted