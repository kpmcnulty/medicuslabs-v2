# Scraper Design Proposal

## Current Issues

1. **Config Management**: Confusion between `config` and `default_config` fields
2. **Limited Association Types**: Only "search" and "fixed" don't cover all use cases
3. **Disease Detection**: No content-based disease matching
4. **Multi-Disease Sources**: No clear way to handle sources that cover multiple diseases

## Proposed Solution

### 1. Enhanced Association Methods

Instead of just "search" and "fixed", we need:

```sql
-- Update association_method to support more types
ALTER TABLE sources 
ALTER COLUMN association_method TYPE VARCHAR(30);

-- Add new association methods
UPDATE sources SET association_method = 'fixed_single' WHERE association_method = 'fixed';
-- New types: fixed_single, fixed_multi, search_targeted, search_all, hybrid
```

### 2. Source Association Configurations

Create a more flexible configuration system:

```sql
CREATE TABLE source_association_configs (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    disease_id INTEGER REFERENCES diseases(id) ON DELETE CASCADE,
    association_type VARCHAR(30) NOT NULL,
    search_terms TEXT[], -- Array of search terms for this disease
    relevance_threshold FLOAT DEFAULT 0.5,
    config JSONB, -- Disease-specific config overrides
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient lookups
CREATE INDEX idx_source_assoc_source_disease ON source_association_configs(source_id, disease_id);
```

### 3. Disease Search Terms

Add search configuration to diseases:

```sql
ALTER TABLE diseases ADD COLUMN search_config JSONB DEFAULT '{}';

-- Example search config:
-- {
--   "primary_terms": ["multiple sclerosis", "MS"],
--   "synonyms": ["demyelinating disease", "autoimmune neurological"],
--   "abbreviations": ["MS", "RRMS", "PPMS", "SPMS"],
--   "exclude_terms": ["MS Office", "Mississippi"],
--   "regex_patterns": ["\\bMS\\b", "multiple\\s+sclerosis"]
-- }
```

### 4. Association Types Explained

- **fixed_single**: Source is dedicated to one disease (e.g., r/MultipleSclerosis)
- **fixed_multi**: Source covers specific diseases (e.g., r/autoimmune for MS, Lupus, RA)
- **search_targeted**: Search for specific disease terms (e.g., PubMed)
- **search_all**: Search for all disease terms in one query (e.g., general medical forums)
- **hybrid**: Combination of fixed and search-based (e.g., r/medical with MS flair)

### 5. Configuration Examples

#### r/MultipleSclerosis (fixed_single)
```json
{
  "source": {
    "name": "r/MultipleSclerosis",
    "association_method": "fixed_single",
    "config": {
      "subreddit": "MultipleSclerosis"
    }
  },
  "associations": [{
    "disease_id": 1,  // MS
    "association_type": "fixed_single"
  }]
}
```

#### r/medical (search_all)
```json
{
  "source": {
    "name": "r/medical",
    "association_method": "search_all",
    "config": {
      "subreddit": "medical",
      "search_method": "flair_and_content"
    }
  },
  "associations": [{
    "disease_id": null,  // All diseases
    "association_type": "search_all",
    "config": {
      "use_flair_matching": true,
      "content_analysis": true,
      "min_relevance_score": 0.6
    }
  }]
}
```

#### r/autoimmune (fixed_multi)
```json
{
  "source": {
    "name": "r/autoimmune",
    "association_method": "fixed_multi",
    "config": {
      "subreddit": "autoimmune"
    }
  },
  "associations": [
    {
      "disease_id": 1,  // MS
      "association_type": "fixed_multi",
      "search_terms": ["MS", "multiple sclerosis", "demyelinating"]
    },
    {
      "disease_id": 3,  // Lupus
      "association_type": "fixed_multi",
      "search_terms": ["lupus", "SLE", "systemic lupus"]
    }
  ]
}
```

### 6. Document Processing Flow

```python
async def process_document(self, raw_data: Dict, source_config: Dict) -> Document:
    """Process document with disease detection"""
    
    # Extract document
    document = self.extract_document_data(raw_data)
    
    # Determine diseases based on association method
    if source_config['association_method'] == 'fixed_single':
        # Single disease from source config
        disease_ids = source_config['disease_ids']
        
    elif source_config['association_method'] == 'fixed_multi':
        # Detect which diseases based on content
        disease_ids = await self.detect_diseases_in_content(
            document.content,
            source_config['associations']
        )
        
    elif source_config['association_method'] in ['search_targeted', 'search_all']:
        # Use search context + content analysis
        disease_ids = await self.match_diseases(
            document.content,
            search_context=self.current_search_disease
        )
    
    # Save with disease associations
    return await self.save_document(document, disease_ids)
```

### 7. Content-Based Disease Detection

```python
async def detect_diseases_in_content(self, content: str, associations: List[Dict]) -> List[int]:
    """Detect diseases mentioned in content"""
    detected_diseases = []
    
    for assoc in associations:
        disease_id = assoc['disease_id']
        search_terms = assoc['search_terms']
        threshold = assoc.get('relevance_threshold', 0.5)
        
        # Simple term matching (can be enhanced with NLP)
        score = calculate_relevance_score(content, search_terms)
        
        if score >= threshold:
            detected_diseases.append({
                'disease_id': disease_id,
                'relevance_score': score
            })
    
    return detected_diseases
```

## Migration Path

1. Keep existing "search" and "fixed" for backward compatibility
2. Add new association methods gradually
3. Migrate sources one by one to new system
4. Enhanced disease detection can be added without breaking changes

## Benefits

1. **Flexibility**: Handle any type of source-disease relationship
2. **Accuracy**: Better disease detection and document linking
3. **Scalability**: Can add new association types without schema changes
4. **Configuration**: Disease-specific configurations per source
5. **Search Optimization**: Different strategies for different source types