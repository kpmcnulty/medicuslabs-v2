-- Show final state after cleanup

-- Show source counts
SELECT 
  COUNT(*) FILTER (WHERE is_active = true) as active_sources,
  COUNT(*) FILTER (WHERE association_method = 'linked') as linked_sources,
  COUNT(*) FILTER (WHERE association_method = 'search') as search_sources
FROM sources;

-- Show all active sources
SELECT 
  name, 
  association_method, 
  scraper_type,
  CASE WHEN config IS NOT NULL THEN 'Yes' ELSE 'No' END as has_config
FROM sources 
WHERE is_active = true 
ORDER BY association_method, name;

-- Show disease count and which have search terms
SELECT 
  COUNT(*) as total_diseases,
  COUNT(*) FILTER (WHERE array_length(search_terms, 1) > 0) as with_search_terms
FROM diseases;

-- Show source-disease associations
SELECT 
  s.name as source_name,
  s.association_method,
  string_agg(d.name, ', ') as linked_diseases
FROM sources s
LEFT JOIN source_diseases sd ON s.id = sd.source_id
LEFT JOIN diseases d ON sd.disease_id = d.id
WHERE s.is_active = true
GROUP BY s.id, s.name, s.association_method
ORDER BY s.name;