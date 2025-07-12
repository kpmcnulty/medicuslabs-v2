# Simplified Scraper Design

## Core Principles
1. **One config source per entity** - No confusion
2. **Visual clarity** - Frontend shows exactly how it works
3. **KISS** - Minimal complexity

## 1. Search Terms Configuration

### Simple Disease Search Terms
```sql
-- Add search_terms directly to diseases table
ALTER TABLE diseases ADD COLUMN search_terms TEXT[] DEFAULT ARRAY[]::TEXT[];

-- Examples:
-- Multiple Sclerosis: ['multiple sclerosis', 'MS', 'RRMS', 'PPMS', 'SPMS']
-- Diabetes: ['diabetes', 'type 1 diabetes', 'type 2 diabetes', 'T1D', 'T2D']
-- Parkinson's: ['parkinson', 'parkinsons', "parkinson's", 'PD']
```

### Source Configuration (ONE config field)
```sql
-- Remove default_config to avoid confusion
ALTER TABLE sources DROP COLUMN default_config;

-- Keep only 'config' field with clear structure
-- config JSONB will contain ALL source configuration
```

## 2. Simplified Association Methods

Just THREE types (visually distinct):

### 🔗 "linked" - Source tied to specific diseases
```json
{
  "name": "r/MultipleSclerosis",
  "association_method": "linked",
  "config": {
    "subreddit": "MultipleSclerosis",
    "post_limit": 100
  }
}
// Links to: MS only (via source_diseases table)
```

### 🔍 "search" - Search for disease terms
```json
{
  "name": "PubMed", 
  "association_method": "search",
  "config": {
    "base_url": "https://pubmed.ncbi.nlm.nih.gov",
    "results_per_disease": 50
  }
}
// Searches for: Each disease's search_terms
```

### 🌐 "all" - Gets everything, analyze content
```json
{
  "name": "r/medical",
  "association_method": "all", 
  "config": {
    "subreddit": "medical",
    "post_limit": 200,
    "analyze_content": true
  }
}
// Gets: All posts, then matches disease terms in content
```

## 3. Frontend Display

### Sources List View
```tsx
// Clear visual indicators
<SourceRow>
  <Icon>{getAssociationIcon(source.association_method)}</Icon>
  <Name>{source.name}</Name>
  <Method>
    {source.association_method === 'linked' && (
      <Badge color="blue">🔗 Linked to {source.diseases.length} diseases</Badge>
    )}
    {source.association_method === 'search' && (
      <Badge color="green">🔍 Searches disease terms</Badge>
    )}
    {source.association_method === 'all' && (
      <Badge color="purple">🌐 Analyzes all content</Badge>
    )}
  </Method>
</SourceRow>
```

### Source Edit Form
```tsx
// Make behavior crystal clear
<Form>
  <RadioGroup 
    label="How does this source work?"
    value={associationMethod}
    onChange={setAssociationMethod}
  >
    <Radio value="linked">
      <strong>🔗 Linked</strong>
      <p>This source only covers specific diseases you select</p>
      <small>Example: r/MultipleSclerosis → only MS content</small>
    </Radio>
    
    <Radio value="search">
      <strong>🔍 Search</strong>
      <p>Searches for each disease using configured terms</p>
      <small>Example: PubMed → searches "multiple sclerosis" OR "MS"</small>
    </Radio>
    
    <Radio value="all">
      <strong>🌐 All Content</strong>
      <p>Gets all content, then detects diseases mentioned</p>
      <small>Example: r/medical → all posts, find disease mentions</small>
    </Radio>
  </RadioGroup>

  {associationMethod === 'linked' && (
    <DiseaseSelector
      label="Which diseases does this source cover?"
      helperText="Documents will be linked to these diseases"
      value={selectedDiseases}
      onChange={setSelectedDiseases}
    />
  )}

  {associationMethod === 'search' && (
    <InfoBox>
      <p>Will search for these terms per disease:</p>
      {diseases.map(d => (
        <div key={d.id}>
          <strong>{d.name}:</strong> {d.search_terms.join(', ')}
        </div>
      ))}
    </InfoBox>
  )}

  {associationMethod === 'all' && (
    <InfoBox>
      <p>Will analyze content for disease mentions using these terms:</p>
      <small>Configure detection threshold in Advanced Settings</small>
    </InfoBox>
  )}
</Form>
```

## 4. Disease Configuration UI

```tsx
// Simple search terms management
<DiseaseForm>
  <Input 
    label="Disease Name" 
    value={disease.name}
  />
  
  <TagInput
    label="Search Terms"
    helperText="Add all variations, abbreviations, and common misspellings"
    placeholder="Type and press Enter"
    value={disease.search_terms}
    onChange={setSearchTerms}
  />
  
  <Preview>
    <strong>When searching, we'll look for:</strong>
    <code>{disease.search_terms.join(' OR ')}</code>
  </Preview>
</DiseaseForm>
```

## 5. How It Works - Visual Guide

### In the Admin Dashboard
```tsx
<HowItWorksGuide>
  <Section>
    <h3>🔗 Linked Sources</h3>
    <Diagram>
      [r/MultipleSclerosis] → [MS Documents]
      [r/diabetes] → [Diabetes Documents]
    </Diagram>
    <p>One source → Specific diseases only</p>
  </Section>

  <Section>
    <h3>🔍 Search Sources</h3>
    <Diagram>
      [PubMed] → Search "MS" → [MS Documents]
                → Search "diabetes" → [Diabetes Documents]
    </Diagram>
    <p>One source → Searches each disease separately</p>
  </Section>

  <Section>
    <h3>🌐 All Content Sources</h3>
    <Diagram>
      [r/medical] → Get all posts → Analyze content → [Match diseases]
    </Diagram>
    <p>One source → Gets everything, detects diseases</p>
  </Section>
</HowItWorksGuide>
```

## 6. Config Examples (One Config to Rule Them All)

### Reddit Linked Source
```json
{
  "subreddit": "MultipleSclerosis",
  "post_limit": 100,
  "include_comments": true,
  "sort_by": "hot"
}
```

### PubMed Search Source
```json
{
  "base_url": "https://pubmed.ncbi.nlm.nih.gov",
  "results_per_disease": 50,
  "date_range": "1year",
  "article_types": ["Clinical Trial", "Review"]
}
```

### Reddit All Content Source
```json
{
  "subreddit": "medical",
  "post_limit": 200,
  "analyze_content": true,
  "min_relevance_score": 0.6,
  "include_comments": true
}
```

## 7. Migration Steps

```sql
-- 1. Add search_terms to diseases
ALTER TABLE diseases ADD COLUMN search_terms TEXT[] DEFAULT ARRAY[]::TEXT[];

-- 2. Populate search terms
UPDATE diseases SET search_terms = ARRAY['multiple sclerosis', 'MS', 'RRMS', 'PPMS'] WHERE name = 'Multiple Sclerosis';
UPDATE diseases SET search_terms = ARRAY['diabetes', 'diabetic', 'type 1 diabetes', 'type 2 diabetes', 'T1D', 'T2D'] WHERE name = 'Diabetes';

-- 3. Update association methods
UPDATE sources SET association_method = 'linked' WHERE association_method = 'fixed';
UPDATE sources SET association_method = 'all' WHERE name LIKE '%medical%' OR name LIKE '%health%';

-- 4. Drop default_config
ALTER TABLE sources DROP COLUMN default_config;
```

## Benefits

1. **No Confusion**: One config field, clear purpose
2. **Visual Clarity**: Icons and descriptions make it obvious
3. **Simple Mental Model**: 
   - Linked = specific diseases
   - Search = search for terms
   - All = get everything, analyze
4. **Easy to Configure**: Just pick a method and configure
5. **Predictable**: Developers know exactly where to look