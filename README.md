# AFC — N.D.A.I (Nugget Data & AI Initiative)

Plateforme data open-source orchestrée avec **Docker** pour croiser les **ventes quotidiennes (CSV)** et les **retours clients de campagne KYC (API)** avec une **analyse de sentiment multilingue** et un **dashboard interactif** connecté à **PostgreSQL**.

## Architecture & Services

| Service | Conteneur | Rôle | Port |
| :--- | :--- | :--- | :--- |
| **db** | `afc_postgres` | Base PostgreSQL 16 (`afc_ndai`), tables brutes, vue `v_sales_campaigns` et feedbacks scorés | `5432` |
| **api** | `afc_feedback_api` | API de réception des feedbacks de campagne KYC | `8080` |
| **pipeline** | `afc_pipeline` | Job batch idempotent : ingestion CSV (`ingested_csv_rows`) + scoring sentiment (`cardiffnlp/twitter-xlm-roberta-base-sentiment`) avec cache Hugging Face | — |
| **dashboard** | `afc_dashboard` | Backend FastAPI + interface web (carte D3.js, graphiques Chart.js, filtres & verbatims KYC) | `8081` |

## Démarrage rapide

### 1. Lancer la stack
```powershell
docker compose up -d --build
docker compose ps
```

### 2. Injecter des données de test (CSV / API KYC)
Depuis le générateur `api_pusher` :
```powershell
python src\__main__.py PUSH 10
```

### 3. Exécuter la pipeline d'ingestion & de sentiment
```powershell
docker compose run --rm pipeline
```

### 4. Accéder au dashboard
Ouvrir **`http://localhost:8081`** dans le navigateur.

## Structure du dépôt
```text
afc-ndai-data/
├── docker-compose.yml
├── init.sql
├── api/
├── pipeline/
└── dashboard/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py
    └── static/
        └── index.html
```