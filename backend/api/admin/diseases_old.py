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
    synonyms: Optional[List[str]] = Field(default=[])
    icd10_codes: Optional[List[str]] = Field(default=[])
    category: Optional[str] = None
    description: Optional[str] = None
    prevalence: Optional[str] = None
    severity: Optional[str] = None

class DiseaseCreate(DiseaseBase):
    pass

class DiseaseUpdate(BaseModel):
    name: Optional[str] = None
    synonyms: Optional[List[str]] = None
    icd10_codes: Optional[List[str]] = None
    category: Optional[str] = None
    description: Optional[str] = None
    prevalence: Optional[str] = None
    severity: Optional[str] = None

class DiseaseResponse(DiseaseBase):
    id: int
    created_at: datetime
    updated_at: datetime
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
                dc.*,
                COUNT(DISTINCT dd.document_id) as document_count
            FROM disease_conditions dc
            LEFT JOIN document_diseases dd ON dc.id = dd.disease_id
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        if category:
            param_count += 1
            query += f" AND dc.category = ${param_count}"
            params.append(category)
        
        if search:
            param_count += 1
            query += f" AND (LOWER(dc.name) LIKE LOWER(${param_count}) OR ${param_count} = ANY(dc.synonyms))"
            params.append(f"%{search}%")
        
        query += f" GROUP BY dc.id ORDER BY dc.name LIMIT {limit} OFFSET {offset}"
        
        rows = await conn.fetch(query, *params)
        
        diseases = []
        for row in rows:
            disease_dict = dict(row)
            
            # Get source coverage
            coverage = await conn.fetch("""
                SELECT 
                    s.name as source_name,
                    COUNT(DISTINCT d.id) as document_count,
                    MAX(d.scraped_at) as last_scraped
                FROM documents d
                JOIN document_diseases dd ON d.id = dd.document_id
                JOIN sources s ON d.source_id = s.id
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
                dc.*,
                COUNT(DISTINCT dd.document_id) as document_count
            FROM disease_conditions dc
            LEFT JOIN document_diseases dd ON dc.id = dd.disease_id
            WHERE dc.id = $1
            GROUP BY dc.id
        """, disease_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Disease not found")
        
        disease_dict = dict(row)
        
        # Get source coverage
        coverage = await conn.fetch("""
            SELECT 
                s.name as source_name,
                COUNT(DISTINCT d.id) as document_count,
                MAX(d.scraped_at) as last_scraped
            FROM documents d
            JOIN document_diseases dd ON d.id = dd.document_id
            JOIN sources s ON d.source_id = s.id
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
            SELECT id FROM disease_conditions 
            WHERE LOWER(name) = LOWER($1)
        """, disease.name)
        
        if existing:
            raise HTTPException(status_code=400, detail="Disease with this name already exists")
        
        # Insert new disease
        row = await conn.fetchrow("""
            INSERT INTO disease_conditions 
            (name, synonyms, icd10_codes, category, description, prevalence, severity)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """, 
            disease.name,
            disease.synonyms or [],
            disease.icd10_codes or [],
            disease.category,
            disease.description,
            disease.prevalence,
            disease.severity
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
        existing = await conn.fetchrow("SELECT * FROM disease_conditions WHERE id = $1", disease_id)
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
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            query = f"""
                UPDATE disease_conditions 
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
                COUNT(DISTINCT d.id) as document_count,
                MAX(d.scraped_at) as last_scraped
            FROM documents d
            JOIN document_diseases dd ON d.id = dd.document_id
            JOIN sources s ON d.source_id = s.id
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
        existing = await conn.fetchrow("SELECT * FROM disease_conditions WHERE id = $1", disease_id)
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
        await conn.execute("DELETE FROM disease_conditions WHERE id = $1", disease_id)
        return {"message": "Disease deleted successfully"}

@router.get("/categories/list", dependencies=[Depends(get_current_admin)])
async def list_categories() -> List[str]:
    """Get all unique disease categories"""
    async with get_pg_connection() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT category 
            FROM disease_conditions 
            WHERE category IS NOT NULL 
            ORDER BY category
        """)
        return [row['category'] for row in rows]

@router.post("/{disease_id}/merge/{target_disease_id}", dependencies=[Depends(get_current_admin)])
async def merge_diseases(disease_id: int, target_disease_id: int) -> Dict[str, Any]:
    """Merge one disease into another"""
    async with get_pg_connection() as conn:
        # Check both diseases exist
        source = await conn.fetchrow("SELECT * FROM disease_conditions WHERE id = $1", disease_id)
        target = await conn.fetchrow("SELECT * FROM disease_conditions WHERE id = $1", target_disease_id)
        
        if not source or not target:
            raise HTTPException(status_code=404, detail="Disease not found")
        
        if disease_id == target_disease_id:
            raise HTTPException(status_code=400, detail="Cannot merge disease with itself")
        
        async with conn.transaction():
            # Move all document associations
            moved_count = await conn.fetchval("""
                UPDATE document_diseases 
                SET disease_id = $2 
                WHERE disease_id = $1
                AND NOT EXISTS (
                    SELECT 1 FROM document_diseases dd2 
                    WHERE dd2.document_id = document_diseases.document_id 
                    AND dd2.disease_id = $2
                )
                RETURNING COUNT(*)
            """, disease_id, target_disease_id)
            
            # Merge synonyms
            await conn.execute("""
                UPDATE disease_conditions
                SET synonyms = array_distinct(synonyms || $2),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """, target_disease_id, source['synonyms'] + [source['name']])
            
            # Delete source disease
            await conn.execute("DELETE FROM disease_conditions WHERE id = $1", disease_id)
        
        return {
            "message": f"Merged {source['name']} into {target['name']}",
            "documents_moved": moved_count or 0
        }