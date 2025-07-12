# Search Implementation Migration Plan

## Current State Analysis

### Three Implementations:
1. **search.py** - Basic search with simple filters
2. **search_enhanced.py** - Enhanced search with hardcoded metadata filters
3. **search_advanced.py** - Dynamic columns but limited metadata query capabilities

## Recommendation: Unified Search Approach

### Why Unify?
- Your schema uses JSONB for ALL metadata - this requires a flexible approach
- Different sources have completely different metadata structures
- Future sources should work without code changes
- Single endpoint reduces complexity

### The New Unified Search (`search_unified.py`)

#### Key Features:
1. **MongoDB-style Query Operators** for maximum flexibility:
   ```json
   {
     "metadata": {
       "publication_date": {"$gte": "2023-01-01"},
       "authors": {"$contains": "Smith"},
       "phase": {"$in": ["Phase 2", "Phase 3"]},
       "pmid": {"$exists": true}
     }
   }
   ```

2. **Dynamic Faceting** - Generate counts for any field:
   ```json
   {
     "facets": ["source_category", "metadata.journal", "metadata.phase"]
   }
   ```

3. **Flexible Return Fields** - Client decides what metadata to receive:
   ```json
   {
     "return_fields": ["metadata.pmid", "metadata.authors", "metadata.journal"]
   }
   ```

4. **Smart Sorting** - Sort by any field including nested metadata

5. **Source Categories** - Group sources logically (publications, trials, community)

## Migration Steps

### Phase 1: Backend Updates
1. **Deploy Unified Search** alongside existing endpoints
2. **Add source categories** to the sources table (already done in migration 003)
3. **Create indexes** for common query patterns:
   ```sql
   -- Add these indexes for better performance
   CREATE INDEX idx_documents_metadata_publication_date ON documents ((metadata->>'publication_date'));
   CREATE INDEX idx_documents_metadata_journal ON documents ((metadata->>'journal'));
   CREATE INDEX idx_documents_metadata_phase ON documents USING gin ((metadata->'phase'));
   CREATE INDEX idx_documents_metadata_status ON documents ((metadata->>'status'));
   ```

### Phase 2: Frontend Migration
1. **Update search API client** to use the unified endpoint
2. **Build dynamic filter UI** based on `/unified/suggest` endpoint
3. **Implement faceted search UI** with the new facet capabilities
4. **Remove hardcoded filter components** in favor of dynamic ones

### Phase 3: Deprecation
1. **Monitor usage** of old endpoints
2. **Deprecate old endpoints** with notices
3. **Remove old search implementations** after migration period

## Benefits of This Approach

1. **True Schema Flexibility** - New sources with different metadata just work
2. **Powerful Queries** - MongoDB-style operators are familiar and powerful
3. **Performance** - PostgreSQL's JSONB with proper indexes is very fast
4. **Single Source of Truth** - One search implementation to maintain
5. **Frontend Flexibility** - UI can adapt to available metadata dynamically

## Example Queries

### Clinical Trials - Active Phase 3 Studies
```json
{
  "source_categories": ["trials"],
  "metadata": {
    "phase": {"$contains": "Phase 3"},
    "status": {"$in": ["Recruiting", "Active, not recruiting"]}
  }
}
```

### PubMed - Recent Cancer Research
```json
{
  "q": "cancer immunotherapy",
  "sources": ["PubMed"],
  "metadata": {
    "publication_date": {"$gte": "2023-01-01"},
    "article_types": {"$contains": "Clinical Trial"}
  },
  "facets": ["metadata.journal", "metadata.mesh_terms"]
}
```

### Community Forums - High Engagement Posts
```json
{
  "source_categories": ["community"],
  "metadata": {
    "engagement.replies": {"$gt": 10},
    "posted_date": {"$gte": "2024-01-01"}
  },
  "sort_by": "metadata.engagement.replies",
  "sort_order": "desc"
}
```

## Next Steps

1. **Test the unified search** with various query patterns
2. **Add the recommended indexes**
3. **Build a query builder UI** for non-technical users
4. **Document the query syntax** for API users
5. **Implement caching** for common queries/facets

## Performance Considerations

1. **Use materialized views** for very common aggregations
2. **Consider partial indexes** for frequently filtered fields
3. **Monitor slow queries** and add indexes as needed
4. **Implement query complexity limits** to prevent abuse

The unified approach aligns perfectly with your JSONB-first schema and provides maximum flexibility for current and future needs.