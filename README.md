# MedicusLabs v2 - Medical Data Aggregation Platform

A simplified, high-performance platform for aggregating, searching, and analyzing medical data from multiple sources including ClinicalTrials.gov, PubMed, FDA FAERS, and medical forums. Built with FastAPI, React, and PostgreSQL.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Git
- 4GB+ RAM recommended
- 10GB+ disk space for data storage

### Initial Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd medicuslabs-v2
```

2. **Create environment file:**
```bash
cp .env.example .env
# Edit .env if needed (default values work for local development)
```

3. **Build and start services:**
```bash
docker-compose up -d --build
```

4. **Access the platform:**
- **Frontend**: http://localhost:3000
- **Admin Portal**: http://localhost:3000/admin (default: admin/admin123)
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

## 🏗 Architecture

### Simplified Stack
- **Frontend**: React + TypeScript (port 3000)
- **Backend**: FastAPI + Python 3.11 (port 8000)
- **Database**: PostgreSQL 15 + pgvector (port 5432)

That's it! No Redis, no Celery, no message queues. Just three lean containers.

### Key Features
- **Unified Search**: Single endpoint with keyword search and metadata filtering
- **Direct Scraper Execution**: Scrapers run inline via FastAPI BackgroundTasks
- **Admin Portal**: Manage sources, diseases, and monitor scraping jobs
- **Real-time Search**: PostgreSQL full-text search with sub-second queries
- **Flexible Metadata**: JSONB storage for source-specific fields

## 📁 Project Structure

```
medicuslabs-v2/
├── backend/
│   ├── api/
│   │   ├── scrapers.py          # Scraper triggers (BackgroundTasks)
│   │   ├── search_unified.py    # Main search endpoint (~400 lines)
│   │   ├── metadata.py          # Field metadata
│   │   └── admin/               # Admin endpoints (Dashboard, Sources, Diseases)
│   ├── core/
│   │   ├── auth.py             # JWT authentication
│   │   ├── config.py           # Settings
│   │   └── database.py         # DB connection
│   ├── models/
│   │   └── database.py         # Document, Source, Disease models
│   └── scrapers/
│       ├── base.py             # Base scraper
│       ├── clinicaltrials.py   # ClinicalTrials.gov
│       ├── pubmed.py           # PubMed
│       ├── faers.py            # FDA FAERS
│       ├── reddit.py           # Reddit medical subs
│       └── web.py              # Generic web scraper
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── admin/          # Admin interface
│       │   ├── DiseaseDataByType.tsx
│       │   └── filters/
│       └── hooks/
├── database/
│   ├── schema.sql              # Main schema
│   └── migrations/             # Database migrations
└── docker-compose.yml          # 3 services: postgres, api, frontend
```

## 🔌 API Endpoints

### Core Search
- `GET /health` - Health check
- `POST /api/search/unified` - Main search endpoint
- `GET /api/search/filters` - Available filters (sources, diseases, categories)

### Scrapers
- `GET /api/scrapers/sources` - List all sources
- `POST /api/scrapers/trigger` - Trigger scraping job (runs in background)
- `GET /api/scrapers/jobs` - List scraping jobs
- `GET /api/scrapers/jobs/{job_id}` - Get job status

### Admin (JWT Protected)
- `POST /api/admin/login` - Admin authentication
- `GET /api/admin/dashboard/stats` - Dashboard statistics
- `GET /api/admin/sources` - Manage data sources
- `GET /api/admin/diseases` - Manage diseases

## 🔐 Admin Authentication

Default credentials: `admin` / `admin123`

Change password via environment variable:
```bash
# Generate bcrypt hash
python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"

# Add to .env
ADMIN_PASSWORD_HASH=<bcrypt-hash>
```

## 🧬 Data Sources

| Source | Type | Documents Available |
|--------|------|---------------------|
| ClinicalTrials.gov | Trials | 600K+ |
| PubMed | Publications | 35M+ |
| FDA FAERS | Adverse Events | 20M+ |
| Reddit Medical | Community | 10+ subreddits |
| Web Scraper | Custom | Configurable |

## 🛠 Development

### Basic Commands
```bash
# Start all services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f api
docker-compose logs -f frontend
docker-compose logs -f postgres

# Restart a service
docker-compose restart api

# Access database
docker-compose exec postgres psql -U medical_user -d medical_data

# Access API shell
docker-compose exec api bash
```

### Manual Scraping
```bash
# Trigger via API (requires admin token)
curl -X POST http://localhost:8000/api/scrapers/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "PubMed",
    "disease_ids": [1],
    "options": {"max_results": 100}
  }'
```

## 🔍 Search Examples

### Keyword Search
```bash
curl -X POST http://localhost:8000/api/search/unified \
  -H "Content-Type: application/json" \
  -d '{
    "q": "diabetes treatment",
    "limit": 50
  }'
```

### Filtered Search
```bash
curl -X POST http://localhost:8000/api/search/unified \
  -H "Content-Type: application/json" \
  -d '{
    "q": "cancer",
    "sources": ["PubMed", "ClinicalTrials.gov"],
    "diseases": ["Lung Cancer"],
    "metadata": {
      "phase": {"$gte": 3}
    },
    "limit": 50
  }'
```

## 🚀 Performance

- **Search Latency**: ~200ms average
- **Documents**: Scalable to millions with partitioning
- **Concurrent Users**: 100+ supported
- **Database**: Indexed for common queries

## 📝 What Changed (Cleanup)

This version removes complexity while keeping core functionality:

**Removed:**
- ❌ Redis (caching layer)
- ❌ Celery (task queue)
- ❌ Flower (Celery monitoring)
- ❌ Nginx (reverse proxy)
- ❌ Hybrid/semantic search (vector embeddings)
- ❌ Jobs/Schedules admin pages

**Kept:**
- ✅ All scrapers (ClinicalTrials, PubMed, FAERS, Reddit, Web)
- ✅ Full-text search with PostgreSQL
- ✅ Admin portal (Dashboard, Sources, Diseases)
- ✅ Keyword + metadata filtering
- ✅ JSONB metadata storage
- ✅ Background task execution

**How scrapers work now:**
- Triggered via API endpoint
- Run in background via FastAPI BackgroundTasks
- Update job status in database
- Simple, no external queue needed

## 🆘 Troubleshooting

### Services won't start
```bash
# Check what's using ports
lsof -i :3000  # Frontend
lsof -i :8000  # API
lsof -i :5432  # PostgreSQL

# Clean restart
docker-compose down -v
docker-compose up -d --build
```

### No search results
```bash
# Check if documents exist
docker-compose exec postgres psql -U medical_user -d medical_data -c "SELECT COUNT(*) FROM documents;"

# Trigger test scrape via admin portal
# Or use API to trigger scraping
```

### Database issues
```bash
# Check database is ready
docker-compose exec postgres pg_isready

# View tables
docker-compose exec postgres psql -U medical_user -d medical_data -c "\dt"

# Run migrations manually
docker-compose exec postgres psql -U medical_user -d medical_data -f /docker-entrypoint-initdb.d/schema.sql
```

## 📄 License

MIT License - see LICENSE file for details.

---

*Simple, fast, and maintainable. Built for real-world medical research.*
