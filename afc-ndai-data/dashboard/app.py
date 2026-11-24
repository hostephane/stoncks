import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import psycopg
from psycopg.rows import dict_row

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME") or "afc_ndai"
DB_USER = os.getenv("POSTGRES_USER") or os.getenv("DB_USER") or "afc_user"
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD") or ""

DSN = (
    f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
    f"user={DB_USER} password={DB_PASSWORD}"
)

app = FastAPI(title="AFC N.D.A.I Dashboard")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/dashboard")
def get_dashboard_data(
    country: Optional[str] = None,
    product: Optional[str] = None,
    campaign_id: Optional[str] = None,
    sentiment: Optional[str] = None,
    days: Optional[int] = None,
    q: Optional[str] = None,
):
    sales_where = ["1=1"]
    sales_params: list = []

    if country and country != "ALL":
        sales_where.append("country = %s")
        sales_params.append(country)
    if product and product != "ALL":
        sales_where.append("product = %s")
        sales_params.append(product)
    if campaign_id and campaign_id != "ALL":
        sales_where.append("campaign_id = %s")
        sales_params.append(campaign_id)
    if days and days > 0:
        sales_where.append("sale_date >= CURRENT_DATE - (%s || ' days')::interval")
        sales_params.append(days)

    sales_where_sql = " AND ".join(sales_where)

    fb_where = ["1=1"]
    fb_params: list = []

    if campaign_id and campaign_id != "ALL":
        fb_where.append("campaign_id = %s")
        fb_params.append(campaign_id)
    if sentiment and sentiment != "ALL":
        fb_where.append("sentiment_label = %s")
        fb_params.append(sentiment)
    if days and days > 0:
        fb_where.append("feedback_date >= CURRENT_DATE - (%s || ' days')::interval")
        fb_params.append(days)
    if q and q.strip():
        fb_where.append("(comment ILIKE %s OR username ILIKE %s OR campaign_id ILIKE %s)")
        like_q = f"%{q.strip()}%"
        fb_params.extend([like_q, like_q, like_q])

    fb_where_sql = " AND ".join(fb_where)

    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # 1. KPIs Ventes
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(total_amount), 0)::float AS total_revenue,
                    COALESCE(SUM(quantity), 0)::int AS total_units,
                    COUNT(*)::int AS total_orders
                FROM v_sales_campaigns
                WHERE {sales_where_sql};
                """,
                sales_params,
            )
            sales_kpi = cur.fetchone()

            # 2. Ventes par Pays
            cur.execute(
                f"""
                SELECT
                    country,
                    COALESCE(SUM(total_amount), 0)::float AS revenue,
                    COALESCE(SUM(quantity), 0)::int AS units,
                    COUNT(*)::int AS orders
                FROM v_sales_campaigns
                WHERE {sales_where_sql}
                GROUP BY country
                ORDER BY revenue DESC;
                """,
                sales_params,
            )
            by_country = cur.fetchall()

            # 3. Ventes par Produit
            cur.execute(
                f"""
                SELECT
                    product,
                    COALESCE(SUM(total_amount), 0)::float AS revenue,
                    COALESCE(SUM(quantity), 0)::int AS units,
                    COUNT(*)::int AS orders
                FROM v_sales_campaigns
                WHERE {sales_where_sql}
                GROUP BY product
                ORDER BY revenue DESC;
                """,
                sales_params,
            )
            by_product = cur.fetchall()

            # 4. Evolution quotidienne des ventes
            cur.execute(
                f"""
                SELECT
                    sale_date::text AS date,
                    COALESCE(SUM(total_amount), 0)::float AS revenue,
                    COALESCE(SUM(quantity), 0)::int AS units
                FROM v_sales_campaigns
                WHERE {sales_where_sql}
                GROUP BY sale_date
                ORDER BY sale_date ASC;
                """,
                sales_params,
            )
            sales_trend = cur.fetchall()

            # 5. KPIs Sentiments KYC
            cur.execute(
                f"""
                SELECT
                    COUNT(*)::int AS total_feedbacks,
                    COUNT(*) FILTER (WHERE sentiment_label = 'positive')::int AS positive_cnt,
                    COUNT(*) FILTER (WHERE sentiment_label = 'neutral')::int AS neutral_cnt,
                    COUNT(*) FILTER (WHERE sentiment_label = 'negative')::int AS negative_cnt,
                    COALESCE(ROUND(AVG(sentiment_score)::numeric, 4), 0)::float AS avg_score
                FROM campaign_feedbacks
                WHERE {fb_where_sql};
                """,
                fb_params,
            )
            fb_kpi = cur.fetchone()

            # 6. Derniers commentaires KYC
            cur.execute(
                f"""
                SELECT
                    cf.id,
                    cf.username,
                    cf.feedback_date::text AS feedback_date,
                    cf.campaign_id,
                    cf.comment,
                    COALESCE(cf.sentiment_label, 'pending') AS sentiment_label,
                    COALESCE(cf.sentiment_score, 0)::float AS sentiment_score,
                    COALESCE(
                        (
                            SELECT STRING_AGG(DISTINCT rcp.product, ', ')
                            FROM raw_campaign_products rcp
                            WHERE rcp.campaign_id = cf.campaign_id
                        ),
                        'Campagne Générale'
                    ) AS products_linked
                FROM campaign_feedbacks cf
                WHERE {fb_where_sql}
                ORDER BY cf.feedback_date DESC, cf.id DESC
                LIMIT 100;
                """,
                fb_params,
            )
            feedbacks = cur.fetchall()

            # 7. Listes pour les filtres
            cur.execute("SELECT DISTINCT product FROM raw_sales ORDER BY product;")
            products = [r["product"] for r in cur.fetchall()]

            cur.execute("SELECT DISTINCT country FROM raw_sales ORDER BY country;")
            countries = [r["country"] for r in cur.fetchall()]

            cur.execute("SELECT DISTINCT campaign_id FROM campaign_feedbacks ORDER BY campaign_id;")
            campaigns = [r["campaign_id"] for r in cur.fetchall()]

    return {
        "sales_kpi": sales_kpi,
        "by_country": by_country,
        "by_product": by_product,
        "sales_trend": sales_trend,
        "feedback_kpi": fb_kpi,
        "feedbacks": feedbacks,
        "filters": {
            "products": products,
            "countries": countries,
            "campaigns": campaigns,
        },
    }