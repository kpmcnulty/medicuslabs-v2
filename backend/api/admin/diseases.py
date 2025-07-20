from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import json
from core.auth import get_current_admin
from core.database import get_pg_connection
from loguru import logger

router = APIRouter(prefix="/api/admin/diseases", tags=["admin-diseases"])

class DiseaseBase(BaseModel):
    name: str
    category: Optional[str] = None
    synonyms: Optional[List[str]] = Field(default=[])
    search_terms: Optional[List[str]] = Field(default=[])

class DiseaseCreate(DiseaseBase):
    pass

class DiseaseUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    synonyms: Optional[List[str]] = None
    search_terms: Optional[List[str]] = None

class DiseaseResponse(DiseaseBase):
    id: int
    created_at: datetime
    document_count: Optional[int] = None
    source_coverage: Optional[List[Dict[str, Any]]] = None

@router.get("/", response_model=List[DiseaseResponse], dependencies=[Depends(get_current_admin)])
async def list_diseases(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[DiseaseResponse]:
    """List all diseases with optional filtering"""
    async with get_pg_connection() as conn:
        query = """
            SELECT 
                d.*,
                COUNT(DISTINCT dd.document_id) as document_count
            FROM diseases d
            LEFT JOIN document_diseases dd ON d.id = dd.disease_id
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        if category:
            param_count += 1
            query += f" AND d.category = ${param_count}"
            params.append(category)
        
        if search:
            param_count += 1
            query += f" AND (LOWER(d.name) LIKE LOWER(${param_count}) OR ${param_count} = ANY(d.synonyms))"
            params.append(f"%{search}%")
        
        query += f" GROUP BY d.id ORDER BY d.name LIMIT {limit} OFFSET {offset}"
        
        rows = await conn.fetch(query, *params)
        
        diseases = []
        for row in rows:
            disease_dict = dict(row)
            
            # Get source coverage
            coverage = await conn.fetch("""
                SELECT 
                    s.name as source_name,
                    COUNT(DISTINCT doc.id) as document_count,
                    MAX(doc.created_at) as last_scraped
                FROM documents doc
                JOIN document_diseases dd ON doc.id = dd.document_id
                JOIN sources s ON doc.source_id = s.id
                WHERE dd.disease_id = $1
                GROUP BY s.id, s.name
                ORDER BY document_count DESC
            """, disease_dict['id'])
            
            disease_dict['source_coverage'] = [dict(c) for c in coverage]
            diseases.append(DiseaseResponse(**disease_dict))
        
        return diseases

@router.get("/{disease_id}", response_model=DiseaseResponse, dependencies=[Depends(get_current_admin)])
async def get_disease(disease_id: int) -> DiseaseResponse:
    """Get a specific disease by ID"""
    async with get_pg_connection() as conn:
        row = await conn.fetchrow("""
            SELECT 
                d.*,
                COUNT(DISTINCT dd.document_id) as document_count
            FROM diseases d
            LEFT JOIN document_diseases dd ON d.id = dd.disease_id
            WHERE d.id = $1
            GROUP BY d.id
        """, disease_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Disease not found")
        
        disease_dict = dict(row)
        
        # Get source coverage
        coverage = await conn.fetch("""
            SELECT 
                s.name as source_name,
                COUNT(DISTINCT doc.id) as document_count,
                MAX(doc.created_at) as last_scraped
            FROM documents doc
            JOIN document_diseases dd ON doc.id = dd.document_id
            JOIN sources s ON doc.source_id = s.id
            WHERE dd.disease_id = $1
            GROUP BY s.id, s.name
            ORDER BY document_count DESC
        """, disease_id)
        
        disease_dict['source_coverage'] = [dict(c) for c in coverage]
        
        return DiseaseResponse(**disease_dict)

@router.post("/", response_model=DiseaseResponse, dependencies=[Depends(get_current_admin)])
async def create_disease(disease: DiseaseCreate) -> DiseaseResponse:
    """Create a new disease"""
    async with get_pg_connection() as conn:
        # Check if disease name already exists
        existing = await conn.fetchval("""
            SELECT id FROM diseases 
            WHERE LOWER(name) = LOWER($1)
        """, disease.name)
        
        if existing:
            raise HTTPException(status_code=400, detail="Disease with this name already exists")
        
        # Insert new disease
        row = await conn.fetchrow("""
            INSERT INTO diseases (name, category, synonyms, search_terms)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """, 
            disease.name,
            disease.category,
            disease.synonyms or [],
            disease.search_terms or []
        )
        
        disease_dict = dict(row)
        disease_dict['document_count'] = 0
        disease_dict['source_coverage'] = []
        
        return DiseaseResponse(**disease_dict)

@router.patch("/{disease_id}", response_model=DiseaseResponse, dependencies=[Depends(get_current_admin)])
async def update_disease(disease_id: int, disease_update: DiseaseUpdate) -> DiseaseResponse:
    """Update a disease"""
    async with get_pg_connection() as conn:
        # Check if disease exists
        existing = await conn.fetchrow("SELECT * FROM diseases WHERE id = $1", disease_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Disease not found")
        
        # Build update query dynamically
        update_fields = []
        params = [disease_id]
        param_count = 1
        
        update_dict = disease_update.dict(exclude_unset=True)
        for field, value in update_dict.items():
            param_count += 1
            update_fields.append(f"{field} = ${param_count}")
            params.append(value)
        
        if update_fields:
            query = f"""
                UPDATE diseases 
                SET {', '.join(update_fields)}
                WHERE id = $1
                RETURNING *
            """
            row = await conn.fetchrow(query, *params)
        else:
            row = existing
        
        # Get document count
        doc_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT document_id) 
            FROM document_diseases 
            WHERE disease_id = $1
        """, disease_id)
        
        disease_dict = dict(row)
        disease_dict['document_count'] = doc_count
        
        # Get source coverage
        coverage = await conn.fetch("""
            SELECT 
                s.name as source_name,
                COUNT(DISTINCT doc.id) as document_count,
                MAX(doc.created_at) as last_scraped
            FROM documents doc
            JOIN document_diseases dd ON doc.id = dd.document_id
            JOIN sources s ON doc.source_id = s.id
            WHERE dd.disease_id = $1
            GROUP BY s.id, s.name
            ORDER BY document_count DESC
        """, disease_id)
        
        disease_dict['source_coverage'] = [dict(c) for c in coverage]
        
        return DiseaseResponse(**disease_dict)

@router.delete("/{disease_id}", dependencies=[Depends(get_current_admin)])
async def delete_disease(disease_id: int) -> Dict[str, str]:
    """Delete a disease"""
    async with get_pg_connection() as conn:
        # Check if disease exists
        existing = await conn.fetchrow("SELECT * FROM diseases WHERE id = $1", disease_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Disease not found")
        
        # Check if disease has documents
        doc_count = await conn.fetchval("""
            SELECT COUNT(*) FROM document_diseases WHERE disease_id = $1
        """, disease_id)
        
        if doc_count > 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete disease with {doc_count} associated documents. Remove document associations first."
            )
        
        # Delete disease
        await conn.execute("DELETE FROM diseases WHERE id = $1", disease_id)
        return {"message": "Disease deleted successfully"}

@router.get("/categories/list", dependencies=[Depends(get_current_admin)])
async def list_categories() -> List[str]:
    """Get all unique disease categories"""
    async with get_pg_connection() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT category 
            FROM diseases 
            WHERE category IS NOT NULL 
            ORDER BY category
        """)
        return [row['category'] for row in rows]

