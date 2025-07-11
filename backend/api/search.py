from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, or_, and_
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from loguru import logger

from core.database import get_db
from models.database import Document, Source

router = APIRouter(prefix="/api/search", tags=["search"])

class SearchRequest(BaseModel):
    query: Optional[str] = None
    sources: Optional[List[str]] = []
    categories: Optional[List[str]] = []  # New: filter by source categories
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    metadata_filters: Optional[Dict[str, Any]] = {}  # Flexible JSONB filters
    page: int = 1
    page_size: int = 20
    sort_by: str = "relevance"  # relevance, date, title
    return_fields: Optional[List[str]] = None  # Specify which fields to return

class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[Dict[str, Any]]
    facets: Dict[str, List[Dict[str, Any]]]  # Dynamic faceting
    columns: List[Dict[str, Any]] = []  # Dynamic column configuration

@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest, db: AsyncSession = Depends(get_db)):
    """
    Unified search endpoint with flexible JSONB metadata filtering
    """
    # Build base query
    query = select(Document).join(Source)
    count_query = select(func.count(Document.id)).join(Source)
    
    # Apply text search if query provided
    if request.query:
        search_condition = or_(
            func.to_tsvector('english', Document.title).op('@@')(
                func.plainto_tsquery('english', request.query)
            ),
            func.to_tsvector('english', Document.content).op('@@')(
                func.plainto_tsquery('english', request.query)
            ),
            func.to_tsvector('english', Document.summary).op('@@')(
                func.plainto_tsquery('english', request.query)
            )
        )
        query = query.where(search_condition)
        count_query = count_query.where(search_condition)
    
    # Filter by source names
    if request.sources:
        query = query.where(Source.name.in_(request.sources))
        count_query = count_query.where(Source.name.in_(request.sources))
    
    # Filter by source categories (new)
    if request.categories:
        query = query.where(Source.category.in_(request.categories))
        count_query = count_query.where(Source.category.in_(request.categories))
    
    # Date range filter
    if request.date_from:
        query = query.where(Document.scraped_at >= request.date_from)
        count_query = count_query.where(Document.scraped_at >= request.date_from)
    
    if request.date_to:
        query = query.where(Document.scraped_at <= request.date_to)
        count_query = count_query.where(Document.scraped_at <= request.date_to)
    
    # Apply flexible metadata filters
    for field, value in request.metadata_filters.items():
        if isinstance(value, dict):
            # Support operators like $gt, $lt, $contains, etc.
            for operator, operand in value.items():
                if operator == "$exists":
                    if operand:
                        query = query.where(Document.doc_metadata[field].isnot(None))
                        count_query = count_query.where(Document.doc_metadata[field].isnot(None))
                    else:
                        query = query.where(Document.doc_metadata[field].is_(None))
                        count_query = count_query.where(Document.doc_metadata[field].is_(None))
                elif operator == "$contains":
                    query = query.where(Document.doc_metadata[field].astext.contains(str(operand)))
                    count_query = count_query.where(Document.doc_metadata[field].astext.contains(str(operand)))
                elif operator == "$in":
                    query = query.where(Document.doc_metadata[field].in_(operand))
                    count_query = count_query.where(Document.doc_metadata[field].in_(operand))
                elif operator == "$gt":
                    query = query.where(Document.doc_metadata[field] > operand)
                    count_query = count_query.where(Document.doc_metadata[field] > operand)
                elif operator == "$lt":
                    query = query.where(Document.doc_metadata[field] < operand)
                    count_query = count_query.where(Document.doc_metadata[field] < operand)
        else:
            # Simple equality
            query = query.where(Document.doc_metadata[field] == value)
            count_query = count_query.where(Document.doc_metadata[field] == value)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply sorting
    if request.sort_by == "date":
        query = query.order_by(Document.scraped_at.desc())
    elif request.sort_by == "title":
        query = query.order_by(Document.title)
    else:  # relevance (default)
        if request.query:
            # Calculate relevance score
            relevance = func.ts_rank(
                func.to_tsvector('english', func.concat(Document.title, ' ', Document.content)),
                func.plainto_tsquery('english', request.query)
            )
            query = query.order_by(relevance.desc())
        else:
            query = query.order_by(Document.scraped_at.desc())
    
    # Apply pagination
    offset = (request.page - 1) * request.page_size
    query = query.limit(request.page_size).offset(offset)
    
    # Execute query
    result = await db.execute(query.options())
    documents = result.scalars().all()
    
    # Format results
    results = []
    for doc in documents:
        # Build base result
        result_dict = {
            "id": doc.id,
            "title": doc.title,
            "url": doc.url,
            "summary": doc.summary,
            "source": doc.source.name,
            "source_category": doc.source.category,
            "date": doc.scraped_at.isoformat() if doc.scraped_at else None,
        }
        
        # Add metadata fields if specified
        if request.return_fields:
            for field in request.return_fields:
                if field in doc.doc_metadata:
                    result_dict[field] = doc.doc_metadata[field]
        else:
            # Return common metadata fields based on source
            if doc.source.category == "publications":
                result_dict["metadata"] = {
                    "pmid": doc.doc_metadata.get("pmid"),
                    "journal": doc.doc_metadata.get("journal"),
                    "authors": doc.doc_metadata.get("authors", [])[:3],  # First 3 authors
                    "publication_date": doc.doc_metadata.get("publication_date"),
                    "doi": doc.doc_metadata.get("doi")
                }
            elif doc.source.category == "trials":
                result_dict["metadata"] = {
                    "nct_id": doc.doc_metadata.get("nct_id"),
                    "status": doc.doc_metadata.get("overall_status"),
                    "phase": doc.doc_metadata.get("phase"),
                    "start_date": doc.doc_metadata.get("start_date"),
                    "sponsors": doc.doc_metadata.get("sponsors", [])
                }
            else:  # community
                result_dict["metadata"] = {
                    "author": doc.doc_metadata.get("author"),
                    "post_date": doc.doc_metadata.get("post_date"),
                    "forum": doc.doc_metadata.get("forum_name"),
                    "comments": doc.doc_metadata.get("comment_count", 0)
                }
        
        results.append(result_dict)
    
    # Generate dynamic facets based on data
    facets = await generate_facets(db, request)
    
    # Generate dynamic columns based on results
    columns = generate_columns_for_results(results)
    
    return SearchResponse(
        total=total,
        page=request.page,
        page_size=request.page_size,
        results=results,
        facets=facets,
        columns=columns
    )

async def generate_facets(db: AsyncSession, request: SearchRequest) -> Dict[str, List[Dict[str, Any]]]:
    """Generate dynamic facets based on available data"""
    facets = {}
    
    # Source categories facet
    category_query = text("""
        SELECT s.category, COUNT(DISTINCT d.id) as count
        FROM documents d
        JOIN sources s ON d.source_id = s.id
        WHERE s.category IS NOT NULL
        GROUP BY s.category
        ORDER BY count DESC
    """)
    
    result = await db.execute(category_query)
    facets["categories"] = [
        {"value": row.category, "count": row.count}
        for row in result
    ]
    
    # Source facet
    source_query = text("""
        SELECT s.name, s.category, COUNT(DISTINCT d.id) as count
        FROM documents d
        JOIN sources s ON d.source_id = s.id
        GROUP BY s.name, s.category
        ORDER BY s.category, count DESC
    """)
    
    result = await db.execute(source_query)
    facets["sources"] = [
        {"value": row.name, "category": row.category, "count": row.count}
        for row in result
    ]
    
    # Dynamic metadata facets based on source categories
    if request.categories and len(request.categories) == 1:
        category = request.categories[0]
        
        if category == "publications":
            # Journal facet for publications
            journal_query = text("""
                SELECT doc_metadata->>'journal' as journal, COUNT(*) as count
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE s.category = 'publications' 
                AND doc_metadata->>'journal' IS NOT NULL
                GROUP BY doc_metadata->>'journal'
                ORDER BY count DESC
                LIMIT 10
            """)
            result = await db.execute(journal_query)
            facets["journals"] = [
                {"value": row.journal, "count": row.count}
                for row in result
            ]
            
        elif category == "trials":
            # Status facet for trials
            status_query = text("""
                SELECT doc_metadata->>'overall_status' as status, COUNT(*) as count
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE s.category = 'trials'
                AND doc_metadata->>'overall_status' IS NOT NULL
                GROUP BY doc_metadata->>'overall_status'
                ORDER BY count DESC
            """)
            result = await db.execute(status_query)
            facets["trial_status"] = [
                {"value": row.status, "count": row.count}
                for row in result
            ]
    
    return facets

def generate_columns_for_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate dynamic column configuration based on search results"""
    
    # Base columns always shown
    columns = [
        {"key": "title", "label": "Title", "sortable": True, "width": "300"},
        {"key": "source", "label": "Source", "sortable": True, "width": "150"},
        {"key": "date", "label": "Date", "sortable": True, "width": "120"}
    ]
    
    if not results:
        return columns
    
    # Determine the primary source category from results
    categories = set()
    for result in results[:10]:  # Sample first 10 results
        if "source_category" in result:
            categories.add(result["source_category"])
    
    # If mixed categories, show generic columns
    if len(categories) > 1:
        columns.append({"key": "summary", "label": "Summary", "sortable": False, "width": "400"})
        return columns
    
    # Category-specific columns
    category = categories.pop() if categories else None
    
    if category == "publications":
        columns.extend([
            {"key": "metadata.journal", "label": "Journal", "sortable": False, "width": "200"},
            {"key": "metadata.authors", "label": "Authors", "sortable": False, "width": "200", 
             "render": "list", "maxItems": 3},
            {"key": "metadata.pmid", "label": "PMID", "sortable": False, "width": "100"},
            {"key": "metadata.doi", "label": "DOI", "sortable": False, "width": "150", "render": "link"}
        ])
    elif category == "trials":
        columns.extend([
            {"key": "metadata.nct_id", "label": "NCT ID", "sortable": False, "width": "120"},
            {"key": "metadata.status", "label": "Status", "sortable": False, "width": "150",
             "render": "badge"},
            {"key": "metadata.phase", "label": "Phase", "sortable": False, "width": "100",
             "render": "list"},
            {"key": "metadata.sponsors", "label": "Sponsors", "sortable": False, "width": "200",
             "render": "list", "maxItems": 2}
        ])
    elif category == "community":
        columns.extend([
            {"key": "metadata.forum", "label": "Forum", "sortable": False, "width": "150"},
            {"key": "metadata.author", "label": "Author", "sortable": False, "width": "150"},
            {"key": "metadata.comments", "label": "Comments", "sortable": False, "width": "100",
             "render": "number"},
            {"key": "summary", "label": "Preview", "sortable": False, "width": "300"}
        ])
    else:
        # Fallback for unknown categories
        columns.append({"key": "summary", "label": "Summary", "sortable": False, "width": "400"})
    
    return columns

@router.get("/filters")
async def get_available_filters(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get available filter options based on source category"""
    
    filters = {
        "categories": [],
        "sources": [],
        "diseases": [],
        "metadata_fields": {}
    }
    
    # Get categories with counts
    category_query = text("""
        SELECT s.category, COUNT(DISTINCT d.id) as doc_count
        FROM sources s
        LEFT JOIN documents d ON s.id = d.source_id
        WHERE s.is_active = true
        GROUP BY s.category
        ORDER BY s.category
    """)
    
    result = await db.execute(category_query)
    filters["categories"] = [
        {"value": row.category, "label": row.category.title(), "count": row.doc_count}
        for row in result
    ]
    
    # Get sources
    source_query = select(Source).where(Source.is_active == True)
    if category:
        source_query = source_query.where(Source.category == category)
    
    result = await db.execute(source_query)
    sources = result.scalars().all()
    
    filters["sources"] = [
        {
            "value": s.name,
            "category": s.category,
            "document_count": len(s.documents)
        }
        for s in sources
    ]
    
    # Define metadata fields available for each category
    if category == "publications":
        filters["metadata_fields"] = {
            "journal": {"type": "string", "description": "Journal name"},
            "pmid": {"type": "string", "description": "PubMed ID"},
            "doi": {"type": "string", "description": "Digital Object Identifier"},
            "publication_type": {"type": "array", "description": "Type of publication"},
            "mesh_terms": {"type": "array", "description": "MeSH terms"},
            "has_abstract": {"type": "boolean", "description": "Has abstract text"}
        }
    elif category == "trials":
        filters["metadata_fields"] = {
            "nct_id": {"type": "string", "description": "ClinicalTrials.gov ID"},
            "overall_status": {"type": "string", "description": "Trial status"},
            "phase": {"type": "array", "description": "Trial phase"},
            "study_type": {"type": "string", "description": "Type of study"},
            "has_results": {"type": "boolean", "description": "Has posted results"}
        }
    elif category == "community":
        filters["metadata_fields"] = {
            "forum_name": {"type": "string", "description": "Forum or subreddit"},
            "author": {"type": "string", "description": "Post author"},
            "comment_count": {"type": "number", "description": "Number of comments"},
            "has_comments": {"type": "boolean", "description": "Has comments"}
        }
    
    return filters

@router.get("/export")
async def export_search_results(
    format: str = "json",
    query: Optional[str] = None,
    sources: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Export search results in various formats"""
    
    # Build query similar to search endpoint
    query_obj = select(Document).join(Source)
    
    if query:
        search_condition = or_(
            func.to_tsvector('english', Document.title).op('@@')(
                func.plainto_tsquery('english', query)
            ),
            func.to_tsvector('english', Document.content).op('@@')(
                func.plainto_tsquery('english', query)
            )
        )
        query_obj = query_obj.where(search_condition)
    
    if sources:
        query_obj = query_obj.where(Source.name.in_(sources))
    
    if categories:
        query_obj = query_obj.where(Source.category.in_(categories))
    
    query_obj = query_obj.limit(limit)
    
    result = await db.execute(query_obj)
    documents = result.scalars().all()
    
    if format == "csv":
        # Return CSV format
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["id", "title", "url", "source", "category", "date", "summary"]
        )
        writer.writeheader()
        
        for doc in documents:
            writer.writerow({
                "id": doc.id,
                "title": doc.title,
                "url": doc.url,
                "source": doc.source.name,
                "category": doc.source.category,
                "date": doc.scraped_at.isoformat() if doc.scraped_at else "",
                "summary": doc.summary[:200] if doc.summary else ""
            })
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=search_results.csv"}
        )
    
    else:  # JSON format
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "title": doc.title,
                "url": doc.url,
                "source": doc.source.name,
                "category": doc.source.category,
                "date": doc.scraped_at.isoformat() if doc.scraped_at else None,
                "summary": doc.summary,
                "metadata": doc.doc_metadata
            })
        
        return {"total": len(results), "results": results}