import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import MultiDiseaseDataTables from './MultiDiseaseDataTables';
import DiseaseSelector from './DiseaseSelector';
import QueryBuilder, { QueryGroup } from './QueryBuilder';
import './DiseaseDataByType.css';

// Configure axios with the API base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

interface SearchFilters {
  diseases: string[];
  query: string;
  advancedQuery?: QueryGroup;
}

const DiseaseDataByType: React.FC = () => {
  const [filters, setFilters] = useState<SearchFilters>({
    diseases: [],
    query: ''
  });
  
  const [diseasesData, setDiseasesData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [isAdvancedMode, setIsAdvancedMode] = useState(false);
  const [queryBuilderValid, setQueryBuilderValid] = useState(false);

  const [activeDataTypes, setActiveDataTypes] = useState<string[]>(['publications', 'trials', 'community', 'faers']);
  const [availableDataTypes] = useState([
    { id: 'publications', name: 'Publications & Research', endpoint: '/api/search/publications', color: '#007bff' },
    { id: 'trials', name: 'Clinical Trials', endpoint: '/api/search/trials', color: '#28a745' },
    { id: 'community', name: 'Community Discussions', endpoint: '/api/search/community', color: '#6f42c1' },
    { id: 'faers', name: 'Adverse Event Reports', endpoint: '/api/search/faers', color: '#dc3545' }
  ]);

  // Convert QueryBuilder output to unified search API format
  const convertQueryToUnifiedSearch = useCallback((query?: QueryGroup) => {
    if (!query) return {};

    const metadata: Record<string, any> = {};
    const columnFilters: any[] = [];

    const processGroup = (group: QueryGroup): any => {
      const conditions: any[] = [];

      // Process individual conditions
      group.conditions.forEach(condition => {
        if (!condition.field || !condition.operator) return;

        if (condition.field.startsWith('metadata.')) {
          // Metadata field
          const fieldName = condition.field.substring(9);
          if (condition.operator === '$exists') {
            metadata[fieldName] = { [condition.operator]: condition.value };
          } else if (condition.value !== '' && condition.value != null) {
            metadata[fieldName] = { [condition.operator]: condition.value };
          }
        } else {
          // Core field - add to column filters
          const operatorMapping: Record<string, string> = {
            '$eq': 'equals',
            '$ne': 'notEqual',
            '$contains': 'contains',
            '$startsWith': 'startsWith',
            '$endsWith': 'endsWith',
            '$gt': 'greaterThan',
            '$gte': 'greaterThanOrEqual',
            '$lt': 'lessThan',
            '$lte': 'lessThanOrEqual',
            '$between': 'inRange',
            '$in': 'equals',
            '$exists': 'notBlank'
          };

          columnFilters.push({
            id: condition.field,
            value: {
              conditions: [{
                operator: operatorMapping[condition.operator] || 'contains',
                value: condition.value
              }],
              joinOperator: 'AND'
            }
          });
        }
      });

      // Process nested groups
      group.groups.forEach(nestedGroup => {
        const nestedQuery = processGroup(nestedGroup);
        if (Object.keys(nestedQuery).length > 0) {
          conditions.push(nestedQuery);
        }
      });

      if (conditions.length === 0) {
        return {};
      } else if (conditions.length === 1) {
        return conditions[0];
      } else {
        return { [`$${group.operator.toLowerCase()}`]: conditions };
      }
    };

    processGroup(query);

    return {
      metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      columnFilters: columnFilters.length > 0 ? columnFilters : undefined
    };
  }, []);

  // Unified search using the new endpoint
  const searchUnified = useCallback(async () => {
    // Check search requirements
    const hasBasicSearch = filters.query.trim().length > 0;
    const hasAdvancedSearch = isAdvancedMode && queryBuilderValid && filters.advancedQuery;
    const hasDiseases = filters.diseases.length > 0;

    if (!hasBasicSearch && !hasAdvancedSearch && !hasDiseases) {
      setDiseasesData([]);
      setHasSearched(false);
      return;
    }

    setLoading(true);
    setHasSearched(true);

    try {
      // Build unified search query
      const unifiedQuery: any = {
        diseases: filters.diseases.length > 0 ? filters.diseases : undefined,
        source_categories: activeDataTypes,
        limit: 50,
        offset: 0
      };

      // Add basic text search
      if (hasBasicSearch) {
        unifiedQuery.q = filters.query;
      }

      // Add advanced query filters
      if (hasAdvancedSearch && filters.advancedQuery) {
        const advancedFilters = convertQueryToUnifiedSearch(filters.advancedQuery);
        if (advancedFilters.metadata) {
          unifiedQuery.metadata = advancedFilters.metadata;
        }
        if (advancedFilters.columnFilters) {
          unifiedQuery.columnFilters = advancedFilters.columnFilters;
        }
      }

      // Execute unified search
      const response = await api.post('/api/search/unified', unifiedQuery);
      const searchResults = response.data;

      if (searchResults.results && searchResults.results.length > 0) {
        // Group results by source category
        const groupedResults = activeDataTypes.map(typeId => {
          const typeResults = searchResults.results.filter((result: any) => 
            result.source_category === typeId
          );

          if (typeResults.length === 0) return null;

          const dataType = availableDataTypes.find(dt => dt.id === typeId);
          if (!dataType) return null;

          return {
            diseaseId: typeId,
            diseaseName: dataType.name,
            data: typeResults,
            columns: searchResults.columns || [],
            totalCount: typeResults.length,
            loading: false,
            searchFilters: {
              diseases: filters.diseases,
              query: filters.query || undefined,
              metadata: unifiedQuery.metadata,
              columnFilters: unifiedQuery.columnFilters
            },
            endpoint: '/api/search/unified', // Use unified endpoint for all
          };
        }).filter(Boolean);

        setDiseasesData(groupedResults);
      } else {
        setDiseasesData([]);
      }
    } catch (error) {
      console.error('Unified search failed:', error);
      setDiseasesData([]);
    } finally {
      setLoading(false);
    }
  }, [filters, activeDataTypes, availableDataTypes, isAdvancedMode, queryBuilderValid, convertQueryToUnifiedSearch]);

  // Auto-search when filters change (with debounce)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchUnified();
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchUnified]);

  const handleDiseasesChange = useCallback((selectedDiseases: string[]) => {
    setFilters(prev => ({ ...prev, diseases: selectedDiseases }));
  }, []);

  const handleQueryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFilters(prev => ({ ...prev, query: e.target.value }));
  }, []);

  const handleAdvancedQueryChange = useCallback((query: QueryGroup) => {
    setFilters(prev => ({ ...prev, advancedQuery: query }));
  }, []);

  const handleQueryBuilderValidChange = useCallback((isValid: boolean) => {
    setQueryBuilderValid(isValid);
  }, []);

  const toggleSearchMode = useCallback(() => {
    setIsAdvancedMode(prev => !prev);
    // Clear opposite mode's data when switching and reset results
    if (!isAdvancedMode) {
      setFilters(prev => ({ ...prev, query: '' }));
    } else {
      setFilters(prev => ({ ...prev, advancedQuery: undefined }));
    }
    // Reset search state
    setDiseasesData([]);
    setHasSearched(false);
  }, [isAdvancedMode]);

  const handleRowClick = useCallback((row: any, dataType: string) => {
    console.log(`Row clicked in ${dataType}:`, row);
    // Future: Open detailed view modal
    if (row.url) {
      window.open(row.url, '_blank');
    }
  }, []);

  const handleExpandedContent = useCallback((row: any, dataType: string) => {
    return (
      <div className="expanded-row-content">
        <div className="expanded-header">
          <h4>{dataType.charAt(0).toUpperCase() + dataType.slice(1)} Details</h4>
          <span className="data-type-badge">{dataType}</span>
        </div>
        
        <div className="expanded-body">
          <div className="basic-info">
            <p><strong>ID:</strong> {row.id}</p>
            <p><strong>Source:</strong> {row.source}</p>
            <p><strong>Last Updated:</strong> {new Date(row.last_updated).toLocaleDateString()}</p>
          </div>
          
          {row.summary && (
            <div className="summary-section">
              <h5>Summary</h5>
              <p>{row.summary}</p>
            </div>
          )}
          
          {row.diseases && row.diseases.length > 0 && (
            <div className="diseases-section">
              <h5>Related Diseases</h5>
              <div className="disease-tags">
                {row.diseases.map((disease: string, idx: number) => (
                  <span key={idx} className="disease-tag">{disease}</span>
                ))}
              </div>
            </div>
          )}
          
          <div className="metadata-section">
            <h5>Additional Data</h5>
            <div className="metadata-grid">
              {Object.entries(row.metadata).slice(0, 6).map(([key, value]) => (
                <div key={key} className="metadata-item">
                  <label>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</label>
                  <span>{Array.isArray(value) ? value.join(', ') : String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }, []);

  return (
    <div className="disease-data-by-type">
      <header className="search-header">
        <h1>Medical Research Dashboard</h1>
        <p className="subtitle">
          Comprehensive view across publications, clinical trials, community discussions, and adverse event reports
        </p>
      </header>

      <div className="search-controls">
        {/* Search Mode Toggle */}
        <div className="search-mode-toggle">
          <button
            className={`mode-button ${!isAdvancedMode ? 'active' : ''}`}
            onClick={() => !isAdvancedMode || toggleSearchMode()}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
            </svg>
            Simple Search
          </button>
          <button
            className={`mode-button ${isAdvancedMode ? 'active' : ''}`}
            onClick={() => isAdvancedMode || toggleSearchMode()}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/>
            </svg>
            Advanced Query Builder
          </button>
        </div>

        {/* Simple Search Row */}
        {!isAdvancedMode && (
          <div className="search-row">
            <div className="search-input-wrapper">
              <input
                type="text"
                className="search-input"
                placeholder="Search across all medical data..."
                value={filters.query}
                onChange={handleQueryChange}
              />
              <svg className="search-icon" width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
              </svg>
            </div>

            <DiseaseSelector
              selectedDiseases={filters.diseases}
              onDiseasesChange={handleDiseasesChange}
            />
          </div>
        )}

        {/* Advanced Query Builder */}
        {isAdvancedMode && (
          <div className="advanced-search-section">
            <div className="disease-selector-row">
              <DiseaseSelector
                selectedDiseases={filters.diseases}
                onDiseasesChange={handleDiseasesChange}
              />
            </div>
            <QueryBuilder
              value={filters.advancedQuery}
              onChange={handleAdvancedQueryChange}
              onValidChange={handleQueryBuilderValidChange}
              sourceCategory={activeDataTypes.length === 1 ? activeDataTypes[0] : undefined}
              className="main-query-builder"
            />
          </div>
        )}

        {/* Data Type Selector */}
        <div className="data-type-selector">
          <span className="selector-label">Show data from:</span>
          <div className="data-type-toggles">
            {availableDataTypes.map(dataType => (
              <button
                key={dataType.id}
                className={`data-type-toggle ${activeDataTypes.includes(dataType.id) ? 'active' : ''}`}
                style={{
                  borderColor: dataType.color,
                  backgroundColor: activeDataTypes.includes(dataType.id) ? dataType.color : 'transparent',
                  color: activeDataTypes.includes(dataType.id) ? 'white' : dataType.color
                }}
                onClick={() => {
                  if (activeDataTypes.includes(dataType.id)) {
                    // Don't allow removing if it's the last one
                    if (activeDataTypes.length > 1) {
                      setActiveDataTypes(prev => prev.filter(id => id !== dataType.id));
                    }
                  } else {
                    setActiveDataTypes(prev => [...prev, dataType.id]);
                  }
                }}
              >
                {dataType.name}
              </button>
            ))}
          </div>
        </div>

        {filters.diseases.length > 0 && (
          <div className="active-filters">
            <span className="filter-label">Diseases:</span>
            {filters.diseases.map(disease => (
              <span key={disease} className="filter-tag">
                {disease}
                <button 
                  onClick={() => handleDiseasesChange(filters.diseases.filter(d => d !== disease))}
                  className="remove-filter"
                >
                  ×
                </button>
              </span>
            ))}
            <button 
              onClick={() => handleDiseasesChange([])}
              className="clear-all-filters"
            >
              Clear All
            </button>
          </div>
        )}
      </div>

      {loading && (
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Searching across all data sources...</p>
        </div>
      )}

      {!loading && hasSearched && diseasesData.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h3>No Results Found</h3>
          <p>
            {filters.diseases.length === 0 
              ? "Please select at least one disease to begin searching."
              : "Try adjusting your search criteria or selecting different diseases."
            }
          </p>
        </div>
      )}

      {!loading && diseasesData.length > 0 && (
        <div className="results-summary">
          <h3>Search Results</h3>
          <p>
            Found data across {diseasesData.length} data type{diseasesData.length > 1 ? 's' : ''} for{' '}
            {filters.diseases.length} selected disease{filters.diseases.length > 1 ? 's' : ''}
            {filters.query && (
              <span> matching "{filters.query}"</span>
            )}
          </p>
        </div>
      )}

      {diseasesData.length > 0 && (
        <MultiDiseaseDataTables
          diseases={diseasesData}
          onRowClick={handleRowClick}
          expandedRowContent={handleExpandedContent}
        />
      )}
    </div>
  );
};

export default DiseaseDataByType;