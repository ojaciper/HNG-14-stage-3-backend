# Profiles Intelligence API — Stage 2

A queryable demographic intelligence engine built with FastAPI + PostgreSQL. Aggregates data from Genderize, Agify, and Nationalize APIs, stores 2026 seeded profiles, and exposes advanced filtering, sorting, pagination, and natural language querying.

---

## 📖 Overview

The **Intelligence Query Engine** is a production-ready demographic intelligence API that transforms raw profile data into a powerful, queryable engine. It enables marketing teams, product analysts, and growth analysts to segment users, identify patterns, and query large datasets using both traditional filters and natural language.

---

### Business Value

- **Marketing Teams**: Target specific demographics for campaigns
- **Product Teams**: Understand user demographics for feature planning
- **Growth Analysts**: Identify patterns and trends in user base
- **Data Scientists**: Extract insights from demographic data

---


## ✨ Features

| Feature | Status | Description |
|---------|--------|-------------|
| 🔍 Advanced Filtering | ✅ | 8+ filter parameters (gender, age, country, probability) |
| 🗣️ Natural Language Search | ✅ | Parse plain English into database queries |
| 📊 Sorting | ✅ | Sort by age, creation date, or probability scores |
| 📄 Pagination | ✅ | Configurable page size with max limit of 50 |
| 🔒 Input Validation | ✅ | Comprehensive validation with proper error codes |
| 🌐 CORS Enabled | ✅ | Cross-origin requests supported |
| 🗄️ PostgreSQL | ✅ | Production-ready database with strategic indexes |
| ⚡ High Performance | ✅ | Sub-100ms response times for filtered queries |

---

## 🛠️ Tech Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Web Framework | FastAPI | 0.104+ | High-performance API framework |
| Database | PostgreSQL | 12+ | Relational database |
| ORM | SQLAlchemy | 2.0+ | Database abstraction |
| Database Adapter | psycopg2-binary | 2.9+ | PostgreSQL connection |
| ASGI Server | Uvicorn | 0.24+ | Production server |
| Language | Python | 3.9+ | Core programming language |

---

## 🏗️ Architecture
┌─────────────────────────────────────────────────────────────┐
│ Client │
│ (Browser / API Tool) │
└─────────────────────┬───────────────────────────────────────┘
│ HTTP/HTTPS
▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Server │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Request │ │ Natural │ │ Response │ │
│ │ Validation │─▶│ Language │─▶│ Formatting │ │
│ │ │ │ Parser │ │ │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
│ SQLAlchemy ORM
▼
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ profiles Table │ │
│ │ • Indexed columns for fast queries │ │
│ │ • Composite indexes for common filters │ │
│ │ • Connection pooling for concurrency │ │
│ └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

---

## Project Structure

```
profiles-api/
├── api/
│   └── main.py          # FastAPI app (Vercel entrypoint)
├── seed_profiles.json    # 2026 seed profiles (bundled)
├── seed.py               # Standalone seed script
├── requirements.txt
├── vercel.json
└── README.md
```

---

## Endpoints

### `GET /api/profiles` — Advanced Filtered List

Supports all filters combinable in a single request. Returns paginated results.

#### Filter Parameters

| Parameter               | Type   | Description                              |
|-------------------------|--------|------------------------------------------|
| `gender`                | string | `male` or `female` (case-insensitive)    |
| `age_group`             | string | `child`, `teenager`, `adult`, `senior`   |
| `country_id`            | string | ISO 2-letter code, e.g. `NG`, `KE`      |
| `min_age`               | int    | Minimum age (inclusive)                  |
| `max_age`               | int    | Maximum age (inclusive)                  |
| `min_gender_probability`| float  | e.g. `0.9`                               |
| `min_country_probability`| float | e.g. `0.5`                               |

#### Sort Parameters

| Parameter | Values                                   | Default      |
|-----------|------------------------------------------|--------------|
| `sort_by` | `age`, `created_at`, `gender_probability`| `created_at` |
| `order`   | `asc`, `desc`                            | `asc`        |

#### Pagination Parameters

| Parameter | Default | Max |
|-----------|---------|-----|
| `page`    | 1       | —   |
| `limit`   | 10      | 50  |

**Example:**
```
GET /api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10
```

**Response:**
```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 43,
  "data": [
    {
      "id": "...",
      "name": "Emmanuel Touré",
      "gender": "male",
      "age": 38,
      "age_group": "adult",
      "country_id": "NG",
      "country_name": "Nigeria"
    }
  ]
}
```

---

### `GET /api/profiles/search` — Natural Language Query

Rule-based parser converts plain English into structured filters.

**Example queries:**

| Query                              | Interpreted As                                      |
|------------------------------------|-----------------------------------------------------|
| `young males`                      | gender=male + min_age=16 + max_age=24               |
| `females above 30`                 | gender=female + min_age=30                          |
| `people from nigeria`              | country_id=NG                                       |
| `adult males from kenya`           | gender=male + age_group=adult + country_id=KE       |
| `male and female teenagers above 17` | age_group=teenager + min_age=17                  |
| `senior females from south africa` | gender=female + age_group=senior + country_id=ZA    |
| `women under 25 from ghana`        | gender=female + max_age=25 + country_id=GH          |
| `men between 20 and 40`            | gender=male + min_age=20 + max_age=40               |

**NL Rules:**
- Gender: `male/males/man/men/boys` → `male`; `female/females/woman/women/girls` → `female`
- `"young"` → min_age=16, max_age=24 (not a stored age group, parsing-only)
- `"above X"` / `"over X"` → min_age=X
- `"below X"` / `"under X"` → max_age=X
- `"between X and Y"` → min_age=X, max_age=Y
- `"children/teenagers/adults/seniors"` → age_group filter
- `"from [country]"` / `"in [country]"` → country_id lookup (supports full names and aliases)
- Queries with no interpretable filters return `400: Unable to interpret query`

Supports same `page`, `limit`, `sort_by`, `order` params as the list endpoint.

---

### `POST /api/profiles` — Create Profile

```json
{ "name": "ella" }
```
Calls Genderize + Agify + Nationalize, stores result. Returns existing record if name already exists.

### `GET /api/profiles/{id}` — Get by UUID

Returns full profile including `sample_size`, `gender_probability`, `country_probability`, `created_at`.

### `DELETE /api/profiles/{id}` — Delete

Returns `204 No Content`.

---

## Data Model

| Field                | Type         | Notes                                            |
|----------------------|--------------|--------------------------------------------------|
| `id`                 | UUID v7      | Primary key, timestamp-based                     |
| `name`               | VARCHAR UNIQUE | Person's full name                             |
| `gender`             | VARCHAR      | `male` or `female`                               |
| `gender_probability` | FLOAT        | Confidence score from Genderize                  |
| `sample_size`        | INT          | Genderize `count` field (renamed)                |
| `age`                | INT          | Exact age from Agify                             |
| `age_group`          | VARCHAR      | `child` (0–12), `teenager` (13–19), `adult` (20–59), `senior` (60+) |
| `country_id`         | VARCHAR(2)   | ISO 2-letter code, highest probability country   |
| `country_name`       | VARCHAR      | Full country name                                |
| `country_probability`| FLOAT        | Probability of top country from Nationalize      |
| `created_at`         | TIMESTAMP    | UTC ISO 8601, auto-generated                     |

---

## Local Development

### Prerequisites
- Python 3.10+

### Setup

```bash
git clone <your-repo-url>
cd profiles-api

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Run (SQLite, seeded automatically on startup)

```bash
uvicorn api.index:app --reload --port 8000
```

Or seed manually:
```bash
python3 seed.py
```

### Test examples

```bash
# All profiles (paginated)
curl "http://localhost:8000/api/profiles"

# Combined filter + sort + paginate
curl "http://localhost:8000/api/profiles?gender=male&country_id=NG&sort_by=age&order=desc&page=1&limit=10"

# Natural language search
curl "http://localhost:8000/api/profiles/search?q=young+males+from+nigeria"
curl "http://localhost:8000/api/profiles/search?q=senior+females+from+south+africa"
curl "http://localhost:8000/api/profiles/search?q=adult+males+from+kenya&limit=5"
```

---

## Deployment (Vercel + Neon)

### Step 1 — Create a free Neon PostgreSQL database

1. Go to [neon.tech](https://neon.tech) → sign up (free tier available)
2. Create a new project
3. Copy the **Connection string**: `postgresql://user:pass@host.neon.tech/dbname?sslmode=require`

### Step 2 — Seed the Neon database

```bash
DATABASE_URL="postgresql://..." python3 seed.py
```

Output: `✅ Seed complete: 2026 inserted, 0 skipped`  
Re-running is safe — duplicates are skipped.

### Step 3 — Push to public GitHub

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<username>/profiles-api.git
git push -u origin main
```

### Step 4 — Deploy on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New → Project**
2. Import your GitHub repository
3. Add environment variable:
   ```
   DATABASE_URL = postgresql://user:pass@host.neon.tech/dbname?sslmode=require
   ```
4. Click **Deploy**

Live URL: `https://<your-project>.vercel.app`

### Step 5 — Verify

```bash
curl "https://<your-project>.vercel.app/api/profiles?limit=1"
# → {"status":"success","page":1,"limit":1,"total":2026,"data":[...]}

curl "https://<your-project>.vercel.app/api/profiles/search?q=adult+males+from+nigeria"
```

---

## Error Responses

All errors follow this structure:
```json
{ "status": "error", "message": "<description>" }
```

| Status | Condition |
|--------|-----------|
| `400`  | Missing/empty parameter or uninterpretable NL query |
| `422`  | Invalid parameter type |
| `404`  | Profile not found |
| `502`  | External API (Genderize/Agify/Nationalize) failure |
| `500`  | Internal server error |

## CORS

`Access-Control-Allow-Origin: *` is set on every response via both `CORSMiddleware` and an HTTP middleware fallback.