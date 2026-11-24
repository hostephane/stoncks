-- Table 1 : Ventes (alignée sur sales.csv)
CREATE TABLE IF NOT EXISTS raw_sales (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    sale_date DATE NOT NULL,
    country VARCHAR(64) NOT NULL,
    product VARCHAR(128) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2 : Mapping Campagne / Produit (alignée sur campaign_product.csv)
CREATE TABLE IF NOT EXISTS raw_campaign_products (
    campaign_id VARCHAR(32) NOT NULL,
    product VARCHAR(128) NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campaign_id, product)
);

-- Table 3 : Retours Campagne KYC (alignée sur le JSON de api_pusher PUSH)
CREATE TABLE IF NOT EXISTS campaign_feedbacks (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    feedback_date DATE NOT NULL,
    campaign_id VARCHAR(32) NOT NULL,
    comment TEXT NOT NULL,
    sentiment_label VARCHAR(20),
    sentiment_score NUMERIC(5, 4),
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index utiles pour le dashboard (filtres par pays, produit, campagne, date)
CREATE INDEX IF NOT EXISTS idx_sales_country ON raw_sales(country);
CREATE INDEX IF NOT EXISTS idx_sales_product ON raw_sales(product);
CREATE INDEX IF NOT EXISTS idx_sales_date ON raw_sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_feedbacks_campaign ON campaign_feedbacks(campaign_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_date ON campaign_feedbacks(feedback_date);