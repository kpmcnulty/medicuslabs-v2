# MedicusLabs v2 - Medical Data Aggregation Platform

A high-performance platform for aggregating, searching, and analyzing medical data from multiple sources including ClinicalTrials.gov, PubMed, FDA FAERS, and medical forums. Built with FastAPI, React, and PostgreSQL.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Git
- 4GB+ RAM recommended
- 10GB+ disk space for data storage

### Initial Setup (First Time Only)

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

3. **Build and start all services:**
```bash
make build    # Build all Docker images
make up       # Start all services
```

4. **Run database migrations:**
```bash
# Wait for PostgreSQL to be ready (check with: make logs-postgres)
make migrate  # Creates tables and indexes
```

5. **Initialize data (optional but recommended):**
```bash
# Add initial diseases and sources
docker exec -it medical_data_api python -c "
from models.database import Disease, Source
from core.database import SessionLocal
db = SessionLocal()

# Add common diseases
diseases = ['Diabetes', 'Cancer', 'Heart Disease', 'COVID-19', 'Alzheimer Disease']
for name in diseases:
    db.add(Disease(name=name, category='Common'))
db.commit()

# Enable existing sources
sources = db.query(Source).all()
for source in sources:
    source.is_active = True
db.commit()
"
```

### Accessing the Platform
- **Frontend**: http://localhost:3000
- **Admin Portal**: http://localhost:3000/admin (see [Admin Authentication](#admin-authentication))
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

### Daily Operations

```bash
# Start services
make up

# Stop services (preserves data)
make down

# View logs
make logs          # All services
make logs-api      # API logs
make logs-frontend # Frontend logs

# Clean restart (WARNING: removes all data)
make clean
make build
make up
```

## 🔐 Admin Authentication

### Default Credentials
- **Username**: `admin`
- **Password**: `admin123`

### Changing the Admin Password

For security, you should change the default password immediately after setup:

```bash
# Run the secure password reset script
docker exec -it medical_data_api python reset_admin_password.py
```

The script will prompt you for:
- Username (default: admin)
- New password (minimum 6 characters)
- Password confirmation

### Managing Admin Users

```bash
# List existing admin users
docker exec -it medical_data_api python reset_admin_password.py list

# Reset password for specific user
docker exec -it medical_data_api python reset_admin_password.py
```

### Security Notes
- Passwords are stored as bcrypt hashes in the database
- No password reset endpoints are exposed via API for security
- Password changes require server access via `docker exec`
- JWT tokens expire after 24 hours (configurable)

## 📊 Current Status - Phase 1.5 (Active Development)

### ✨ Recent Updates

#### **Infrastructure Improvements**
- **Optimized Search**: Query builder with smart field search and defaults
- **Performance**: Added database indexes for sorting and filtering
- **Data Export**: CSV and XLSX export functionality
- **Enhanced Scrapers**: FAERS integration, improved PubMed parsing
- **Standardized Dates**: Consistent date handling across all sources

#### **UI/UX Enhancements**
- **Split Table View**: Separate tables by document type for better organization
- **Smart Column Search**: Type-aware filtering (e.g., ">=3" for Phase 3+ trials)
- **Modal Expansion**: Detailed document view in modal overlay
- **Pagination**: Client-side pagination with customizable page sizes
- **Responsive Design**: Mobile-friendly interface

### 🆕 Admin Portal & Simplified Configuration

#### **Admin Portal** (http://localhost:3000/admin)
- **Dashboard**: Real-time statistics, job monitoring, system health
- **Sources Management**: Configure data sources with visual indicators
  - 🔗 **Linked Sources**: Fixed to specific diseases (e.g., r/MultipleSclerosis)
  - 🔍 **Search Sources**: Search for disease terms (e.g., PubMed)
- **Disease Management**: Configure search terms and synonyms
  - Tag-based search term editor
  - Visual search preview: "term1 OR term2 OR term3"
  - Disease merging for duplicates
- **Job Monitoring**: Track scraping jobs and trigger manual runs
- **JWT Authentication**: Secure admin access

#### **Simplified Source Configuration**
- **One Config Source**: Eliminated confusing dual-config system
- **Clear Association Methods**:
  - **Linked**: Source covers specific diseases only
  - **Search**: Source searches for configured disease terms
- **Visual Clarity**: Icons and descriptions make behavior obvious
- **KISS Principle**: Minimal complexity, maximum clarity

### 🎯 Dynamic Search Interface

#### **Unified Search Page** (`/api/search-unified`)
- **Smart Query Builder**: Visual query construction with field-specific operators
- **Type-Aware Search**: Numeric comparisons for phases, text search for titles
- **Split Table View**: Separate tables for each document type
- **Column Customization**: Show/hide columns, resize, reorder
- **Advanced Filtering**: 
  - Clinical Trials: Phase, Status, Sponsor, Enrollment
  - Publications: Journal, Authors, Publication Type, Citations
  - FAERS Reports: Event terms, Drug names, Outcomes
- **Export Options**: Download results as CSV or XLSX

### ✅ Implemented Features

#### **Core Features**
- **Unified Search**: Single endpoint (`/api/search-unified`) handles all document types
- **Smart Filtering**: Query builder with field-specific operators and validation
- **Data Export**: CSV/XLSX export with all metadata preserved
- **Real-time Updates**: WebSocket support for live data updates (planned)
- **Responsive Tables**: TanStack Table v8 with virtualization for large datasets

#### **Active Data Sources**
- **ClinicalTrials.gov**: 600K+ trials with full metadata
- **PubMed**: 35M+ biomedical articles (limited by API rate)
- **FDA FAERS**: 20M+ adverse event reports
- **Reddit Medical**: 10+ medical subreddits (r/diabetes, r/cancer, etc.)
- **Web Scraper**: Generic scraper for medical websites

#### **Infrastructure**
- **PostgreSQL 15**: Partitioned tables for scalability
- **pgvector**: Semantic search capabilities (embeddings ready)
- **Redis**: Caching and task queue
- **Celery**: Distributed task processing
- **Docker Compose**: One-command deployment

### 🎯 Sprint Plan - Next Steps

See [UNIFIED_SPRINT_PLAN.md](./UNIFIED_SPRINT_PLAN.md) for detailed roadmap.

#### **Sprint 0: Core Infrastructure** (1 week)
- Elasticsearch integration for sub-100ms search
- Advanced caching with Redis cluster
- Storage optimization and compression
- Database partitioning for scale

#### **Sprint 1: Data Acquisition** (2 weeks)
- Scale to 500K+ documents
- RSS aggregation from 500+ medical sources
- Web crawling infrastructure
- Bulk data imports (PubMed FTP, etc.)

#### **Sprint 2: AI & Intelligence** (3 weeks)
- Semantic search with embeddings
- Medical NER extraction
- GPT-4/Claude integration
- Knowledge graph construction

## 🛠 Development Commands

### Docker Operations
```bash
make build          # Build all Docker images
make up             # Start all services
make down           # Stop all services
make logs           # View logs from all services
make logs-api       # View API logs specifically
make logs-frontend  # View frontend logs specifically
make ps             # Show running containers
make clean          # Stop and remove all data
```

### Database Operations
```bash
make shell-db       # Open PostgreSQL shell
make migrate        # Run database migrations
make backup         # Backup database (if configured)

# Manual migration example
docker exec -it medical_data_postgres psql -U postgres -d medical_data -f /docker-entrypoint-initdb.d/migrations/002_sorting_optimization_indexes.sql
```

### Development Tools
```bash
make shell-api      # Open shell in API container
make test           # Run tests (pytest)
make lint           # Run linters (ruff, black, mypy)
make format         # Auto-format code

# Trigger scrapers manually
docker exec -it medical_data_api python -c "
from tasks.scrapers import scrape_clinicaltrials
scrape_clinicaltrials.delay('diabetes', max_results=10)
"
```

## 🔌 API Endpoints

### Core Search API
- `GET /health` - Health check
- `POST /api/search-unified` - **Primary search endpoint** with query builder support
- `GET /api/metadata-fields` - Get searchable fields for query builder
- `GET /api/diseases` - List all diseases with document counts
- `GET /api/sources` - List all active sources

### Legacy Search API (being phased out)
- `POST /api/search/` - Basic search
- `POST /api/search/enhanced` - Enhanced search
- `GET /api/search/filters/enhanced` - Filter options

### Scraper Management
- `GET /api/scrapers/sources` - List all data sources
- `POST /api/scrapers/scrape` - Trigger scraping job
- `GET /api/scrapers/jobs` - View scraping jobs status

### Admin API (Protected - Requires JWT)
- `POST /api/admin/login` - Admin authentication
- `GET /api/admin/dashboard/stats` - Dashboard statistics
- `GET /api/admin/sources` - List sources with configuration
- `POST /api/admin/sources` - Create new source
- `PATCH /api/admin/sources/{id}` - Update source configuration
- `POST /api/admin/sources/{id}/trigger-scrape` - Trigger source scraping
- `GET /api/admin/diseases` - List diseases with search terms
- `POST /api/admin/diseases` - Create new disease
- `PATCH /api/admin/diseases/{id}` - Update disease search terms
- `POST /api/admin/diseases/{id}/merge/{target_id}` - Merge diseases
- `GET /api/admin/jobs` - List crawl jobs with status

### Query Builder Fields
The unified search supports field-specific queries:

#### Clinical Trials
- `phase`: Numeric (1-4) - e.g., "phase >= 3"
- `status`: Text - "Recruiting", "Completed", etc.
- `enrollment`: Numeric - e.g., "enrollment > 100"
- `sponsor`: Text search in sponsor name

#### Publications
- `journal`: Text search
- `authors`: Text search in author names
- `publication_type`: "Clinical Trial", "Review", etc.
- `mesh_terms`: Medical subject headings

#### FAERS Reports
- `event_terms`: Adverse event descriptions
- `drug_names`: Medication names
- `outcomes`: "Death", "Hospitalization", etc.

## 🏗 Architecture

### Technology Stack
- **Frontend**: React 19 + TypeScript + TanStack Table v8
- **Backend**: FastAPI + Python 3.11 + SQLAlchemy 2.0
- **Database**: PostgreSQL 15 + pgvector extension
- **Task Queue**: Celery + Redis
- **Search**: PostgreSQL FTS (Elasticsearch ready)
- **Deployment**: Docker Compose

### Key Features
- **Unified Search Interface**: Single endpoint for all document types
- **Smart Query Builder**: Field-aware search with type validation
- **Scalable Architecture**: Partitioned tables, ready for millions of documents
- **Export Capabilities**: CSV/XLSX export with full metadata
- **Real-time Updates**: Admin dashboard with live statistics
- **Extensible Scrapers**: Easy to add new data sources

## 📁 Project Structure

```
medicuslabs-v2/
├── backend/                    # FastAPI application
│   ├── api/                   # API endpoints
│   │   ├── admin/            # Admin portal endpoints
│   │   ├── search_unified.py # Main search endpoint
│   │   ├── search_by_type.py # Search by document type
│   │   └── metadata.py       # Field metadata
│   ├── core/                 # Core utilities
│   │   ├── auth.py          # JWT authentication
│   │   ├── config.py        # Settings
│   │   └── database.py      # DB connection
│   ├── models/               # SQLAlchemy models
│   │   └── database.py      # Document, Source, Disease
│   ├── scrapers/            # Data collection
│   │   ├── base.py          # Base scraper class
│   │   ├── clinicaltrials.py
│   │   ├── pubmed.py
│   │   ├── faers.py
│   │   ├── reddit.py
│   │   └── web.py
│   └── tasks/               # Celery tasks
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/      
│   │   │   ├── admin/       # Admin interface
│   │   │   ├── DynamicDataTable.tsx
│   │   │   ├── QueryBuilder.tsx
│   │   │   └── metadata/    # Type-specific views
│   │   └── hooks/           
│   │       └── useOptimizedSearch.ts
├── database/                
│   ├── schema.sql          # Main schema
│   └── migrations/         # Index optimizations
├── docker-compose.yml      
├── Makefile               # Dev commands
├── CLAUDE.md              # AI instructions
└── UNIFIED_SPRINT_PLAN.md # Development roadmap
```

## 🔍 Usage Examples

### Quick Search
```bash
# After setup, navigate to http://localhost:3000
# Use the query builder to search for:
- "phase >= 3" - Find Phase 3+ clinical trials
- "diabetes AND metformin" - Diabetes studies mentioning metformin
- "journal = NEJM" - Articles from New England Journal of Medicine
```

### Admin Operations
```bash
# Add a new disease
curl -X POST http://localhost:8000/api/admin/diseases \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Hypertension", "search_terms": ["high blood pressure", "HTN"]}'

# Trigger manual scrape
curl -X POST http://localhost:8000/api/admin/sources/1/trigger-scrape \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Export Data
```python
# From the UI: Click "Export" button and choose CSV or XLSX
# Via API:
import requests
response = requests.post('http://localhost:8000/api/search-unified', 
    json={"query": "diabetes", "format": "csv"})
with open('results.csv', 'wb') as f:
    f.write(response.content)
```

## 🧬 Data Sources & Metadata

### Active Scrapers
| Source | Status | Documents | Update Frequency |
|--------|--------|-----------|------------------|
| ClinicalTrials.gov | ✅ Active | 600K+ available | Daily |
| PubMed | ✅ Active | 35M+ available | Daily |
| FDA FAERS | ✅ Active | 20M+ reports | Quarterly |
| Reddit Medical | ✅ Active | 10+ subreddits | Hourly |
| Web Scraper | ✅ Active | Custom sites | On-demand |

### Metadata Fields
Each document type collects specific metadata:

**Clinical Trials**
- NCT ID, title, status, phase
- Enrollment, start/completion dates
- Sponsors, investigators
- Conditions, interventions
- Primary/secondary outcomes

**Publications**
- PMID, title, abstract
- Authors, affiliations
- Journal, publication date
- MeSH terms, keywords
- Citations, references

**FAERS Reports**
- Report ID, event date
- Drug names, dosages
- Adverse events, outcomes
- Patient demographics
- Reporter type

## 🚀 Performance & Scaling

### Current Performance
- **Search Latency**: ~200ms (target: <100ms with Elasticsearch)
- **Documents**: 10K+ indexed (scalable to millions)
- **Concurrent Users**: 100+ supported
- **API Rate Limits**: Configurable per source

### Optimization Status
- ✅ Database indexes for common queries
- ✅ Pagination for large result sets
- ✅ Connection pooling
- ⏳ Elasticsearch integration (Sprint 0)
- ⏳ Redis caching layer (Sprint 0)
- ⏳ Table partitioning (Sprint 0)

## 📝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and test locally: `make up && make test`
4. Commit changes: `git commit -am 'Add new feature'`
5. Push to branch: `git push origin feature/new-feature`
6. Submit a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

**1. Services won't start:**
```bash
# Check if ports are in use
lsof -i :3000  # Frontend
lsof -i :8000  # Backend

# Clean restart
make clean && make build && make up
```

**2. Database migrations not applied:**
```bash
# Check migration status
make shell-db
\dt  # Should show all tables

# Apply migrations manually
docker exec -it medical_data_postgres psql -U postgres -d medical_data -f /docker-entrypoint-initdb.d/migrations/002_sorting_optimization_indexes.sql
```

**3. Scrapers not running:**
```bash
# Check Celery workers
make logs | grep celery

# Restart workers
docker-compose restart celery_worker
```

**4. Search returns no results:**
```bash
# Check if data exists
make shell-db
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM document_diseases;

# Trigger test scrape
docker exec -it medical_data_api python -c "from tasks.scrapers import scrape_clinicaltrials; scrape_clinicaltrials.delay('diabetes', max_results=10)"
```

**5. Export not working:**
- Check browser console for errors
- Ensure you have data in search results
- Try different export format (CSV vs XLSX)

### Debug Commands
```bash
# Check all service health
docker-compose ps

# View recent logs
docker-compose logs --tail=100 api

# Interactive debugging
make shell-api
python
>>> from models.database import Document
>>> from core.database import SessionLocal
>>> db = SessionLocal()
>>> db.query(Document).count()
```

### Getting Help
- View API docs: http://localhost:8000/docs
- Check logs: `make logs`
- See development notes: [CLAUDE.md](./CLAUDE.md)
- Sprint planning: [UNIFIED_SPRINT_PLAN.md](./UNIFIED_SPRINT_PLAN.md)

---

## 🔀 Fork Strategy for Other Domains

This platform is designed to be easily forked for other domains (e.g., aircraft parts, legal documents). See [UNIFIED_SPRINT_PLAN.md](./UNIFIED_SPRINT_PLAN.md) for the fork strategy:

1. Complete Sprint 0 (core infrastructure)
2. Fork the repository
3. Replace disease-specific components with your domain
4. Add domain-specific scrapers
5. Both versions benefit from the same fast search infrastructure

---

*Built with ❤️ by MedicusLabs - Making medical research accessible to everyone*
