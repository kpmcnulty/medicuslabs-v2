# Medical Data Aggregation Platform

A comprehensive platform for aggregating, searching, and analyzing medical data from multiple sources including ClinicalTrials.gov, PubMed, and medical forums.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Running the Platform

1. **Clone and start all services:**
```bash
git clone <repository-url>
cd medicuslabs
make build    # Build all Docker images
make up       # Start all services
```

2. **Access the platform:**
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health
- **Celery Monitor (Flower)**: http://localhost:5555
- **Nginx Proxy**: http://localhost:80

3. **Stop the platform:**
```bash
make down     # Stop all services
make clean    # Stop and remove all data
```

## 📊 Current Status - Phase 1 Complete ✅

### 🎯 NEW: Dynamic Database-Driven Interface

#### **Dynamic Filtering System**
- **Source Type Selector**: Visual cards for Publications, Clinical Trials, Community Forums
- **Disease/Condition Selector**: Searchable dropdown with all diseases from database
- **Dynamic Table Columns**: Columns automatically adapt based on selected source type
  - **Publications**: Journal, Authors, Publication Date, PMID, Article Types
  - **Clinical Trials**: NCT ID, Status, Phase, Conditions, Start Date
  - **Community**: Source, Author, Posted Date, Engagement metrics
- **Metadata-Driven**: All filter options come from actual database content
- **Zero Hardcoding**: Completely dynamic, adapts to new data automatically

### ✅ Implemented Features

#### **Advanced Search Interface**
- **TanStack Table** with master-detail expandable rows (free AG-Grid Enterprise alternative)
- **react-querybuilder** for complex filter building
- **Enhanced filtering** by source types, study phases, publication types, diseases, dates
- **Multiple search modes**: keyword, semantic, hybrid
- **Real-time filter options** with document counts
- **Responsive design** with collapsible sidebar

#### **Backend API**
- **PostgreSQL full-text search** with GIN indexes and ts_rank scoring
- **Dynamic metadata discovery** (`/api/metadata/schema`) - analyzes document structure
- **Advanced search endpoint** (`/api/search/advanced`) with adaptive columns
- **Values endpoint** (`/api/metadata/values`) - populates filters from actual data
- **Enhanced search endpoint** (`/api/search/enhanced`) with complex filtering
- **Metadata-based filtering** using PostgreSQL JSON operators
- **Working scrapers**: ClinicalTrials.gov, PubMed
- **Rich metadata collection** from all sources with automatic field detection

#### **Database & Infrastructure**
- **PostgreSQL with pgvector** for semantic search support
- **Complete Docker deployment** with all services
- **Celery + Redis** for background task processing
- **Database migrations** with comprehensive schema

### 🎯 Next Steps - Phase 1.5

#### **Data Collection Expansion**
- Fix broken scrapers (Reddit, HealthUnlocked, Patient.info)
- Add FDA FAERS adverse event reporting system
- Define data normalization pipeline
- Implement scraping strategy decisions

#### **Smart Query Builder**
- Replace basic filters with visual query builder using react-querybuilder
- Integrate with dynamic metadata schema discovery
- Add field-specific operators and value autocomplete
- Implement query validation and save/load functionality

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
make migrate        # Run database migrations (when available)
make backup         # Backup database
```

### Development Tools
```bash
make shell-api      # Open shell in API container
make test           # Run tests (when available)
make lint           # Run code linters
```

## 🔌 API Endpoints

### Core Search API
- `GET /health` - Health check
- `POST /api/search/` - Basic search with filtering
- `POST /api/search/enhanced` - Advanced search with complex filtering
- `POST /api/search/advanced` - Dynamic search with adaptive columns
- `GET /api/search/filters/enhanced` - Get available filter options with counts
- `GET /api/search/suggestions/` - Search suggestions

### Metadata API
- `GET /api/metadata/schema/{source_type}` - Get metadata schema for a source
- `GET /api/metadata/schema` - Get all source schemas
- `POST /api/metadata/values` - Get unique values for any metadata field
- `GET /api/metadata/field-correlations/{field}` - Get correlated fields

### Scraper Management
- `GET /api/scrapers/sources` - List all data sources
- `POST /api/scrapers/scrape` - Trigger scraping job
- `GET /api/scrapers/jobs` - View scraping jobs status

### Filter Options Available
- **Source Types**: Primary (clinical trials, journals) vs Secondary (forums, blogs)
- **Diseases/Conditions**: All diseases with document counts
- **Study Phases**: Phase 1, 2, 3, 4 for clinical trials
- **Study Types**: Interventional, Observational, etc.
- **Trial Status**: Active, Completed, Recruiting, etc.
- **Publication Types**: Clinical Trial, Review, Case Study, etc.
- **Journals**: All journals with document counts
- **Date Ranges**: System dates vs publication dates

## 🏗 Architecture

### Technology Stack
- **Frontend**: React 18 + TypeScript + TanStack Table + react-querybuilder
- **Backend**: FastAPI + Python 3.11 + SQLAlchemy + asyncpg
- **Database**: PostgreSQL 15 + pgvector extension
- **Task Queue**: Celery + Redis
- **Deployment**: Docker + Docker Compose + Nginx

### Key Design Decisions
- **Free AG-Grid Alternative**: TanStack Table + react-querybuilder saves $1000+ licensing
- **Dynamic Database-Driven UI**: Zero hardcoded values, all options from database
- **Self-Adapting Interface**: Automatically adapts to new sources and metadata fields
- **Database-first approach**: All data in PostgreSQL, no file system dependencies
- **Metadata-rich scraping**: Collect maximum available data from each source
- **Docker containerization**: Complete environment in single compose file
- **Async processing**: Background scraping with Celery workers

## 📁 Project Structure

```
medicuslabs/
├── backend/                    # FastAPI application
│   ├── api/                   # API endpoints
│   │   ├── search.py         # Basic search endpoints
│   │   ├── search_enhanced.py # Advanced search with complex filtering
│   │   ├── search_advanced.py # Dynamic search with adaptive columns
│   │   └── metadata.py       # Metadata discovery and values
│   ├── core/                 # Core configuration
│   ├── models/               # Database models and schemas
│   ├── scrapers/            # Data scrapers
│   └── tasks/               # Celery background tasks
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/      # React components
│   │   │   ├── SourceTypeSelector.tsx # Visual source selection
│   │   │   ├── DiseaseSelector.tsx    # Searchable disease dropdown
│   │   │   ├── DynamicDataTable.tsx   # Adaptive column table
│   │   │   └── MedicalDataSearchDynamic.tsx # Main interface
│   │   ├── api/            # API client
│   │   ├── utils/          # Utility functions
│   │   └── types/          # TypeScript types
│   └── public/             # Static assets
├── database/                # Database setup
│   ├── migrations/         # SQL migration files
│   └── seeds/             # Seed data
├── docker-compose.yml      # Docker services configuration
└── Makefile               # Development commands
```

## 🔍 Search Features

### Current Data Available for Testing
- **8 Total Documents**: 2 Clinical Trials + 6 PubMed Publications
- **Search Terms to Try**: "diabetes", "cancer", "immunotherapy", "rheumatoid arthritis"
- **Diseases Available**: Diabetes, Cancer, Melanoma, Heart Failure, COVID-19, etc.
- **Source Types**: Publications (PubMed), Clinical Trials (ClinicalTrials.gov)

### Dynamic Search Interface
- **Source Type Cards**: Select Publications, Clinical Trials, or Community Forums
- **Disease Selector**: Searchable dropdown with popular diseases section
- **Adaptive Columns**: Table automatically shows relevant fields per source type
- **Real-time Filtering**: Search updates as you type with 500ms debounce

### Basic Search
- Full-text search across document titles and content
- Filter by sources, diseases, date ranges
- Pagination and sorting
- Search suggestions

### Enhanced Search
- **Advanced filtering**: Study phases, publication types, trial status
- **Query builder**: Visual interface for complex queries
- **Metadata filtering**: JSON-based filtering on rich metadata
- **Multiple search types**: Keyword, semantic (planned), hybrid (planned)
- **Real-time filter counts**: See how many documents match each filter

### Filter Builder
- **Drag-and-drop interface** for building complex queries
- **Boolean operators**: AND, OR, NOT combinations
- **Field-specific operators**: Contains, equals, date ranges, etc.
- **SQL preview**: See generated query
- **Save/load queries**: Store complex searches (planned)

## 🧬 Data Sources

### Currently Working
- **ClinicalTrials.gov**: Official API with trial metadata
- **PubMed**: Enhanced XML parsing with full metadata

### In Development (Phase 1.5)
- **Reddit Medical Subreddits**: Patient experiences and discussions
- **HealthUnlocked**: Patient community discussions
- **Patient.info Forums**: Medical condition forums
- **FDA FAERS**: Adverse event reporting system

### Metadata Collected
- **Clinical Trials**: NCT ID, phases, status, conditions, interventions, outcomes
- **PubMed**: PMID, authors, affiliations, journals, MeSH terms, chemicals
- **Forums**: User discussions, symptoms, treatments, experiences
- **Common**: Dates, URLs, source types, relevance scores

## 🚧 Roadmap

### Phase 2: Data Processing & AI (Week 3-4)
- Implement embedding generation for semantic search
- Add medical NER (Named Entity Recognition)
- Sentiment analysis for patient experiences
- Automated content summarization

### Phase 3: Advanced Analytics (Week 4-5)
- Clinical trial intelligence and comparison
- Adverse event detection and monitoring
- Treatment pathway analysis
- Research gap identification

### Phase 4: Admin & Management (Week 5-6)
- Admin dashboard for managing sources and diseases
- User management and authentication
- Data quality monitoring
- Export and reporting features

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

**Services won't start:**
```bash
make down && make clean
make build --no-cache
make up
```

**Database connection issues:**
```bash
make logs-postgres  # Check database logs
make shell-db       # Test database connection
```

**Frontend not loading:**
```bash
make logs-frontend  # Check React compilation
curl http://localhost:3000  # Test accessibility
```

**API not responding:**
```bash
make logs-api       # Check API logs
curl http://localhost:8000/health  # Test API health
```

### Getting Help
- View logs: `make logs`
- Check service status: `make ps`
- Open API documentation: http://localhost:8000/docs
- Report issues: [GitHub Issues](https://github.com/your-repo/medicuslabs/issues)

---

**Built with ❤️ for medical researchers and healthcare professionals**