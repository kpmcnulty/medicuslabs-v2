import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import MultiDiseaseDataTables from './MultiDiseaseDataTables';
import DiseaseSelector from './DiseaseSelector';
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
}

const DiseaseDataByType: React.FC = () => {
  const [filters, setFilters] = useState<SearchFilters>({
    diseases: [],
    query: ''
  });
  
  const [diseasesData, setDiseasesData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const [activeDataTypes, setActiveDataTypes] = useState<string[]>(['publications', 'trials', 'community', 'faers']);
  const [availableDataTypes] = useState([
    { id: 'publications', name: 'Publications & Research', endpoint: '/api/search/publications', color: '#007bff' },
    { id: 'trials', name: 'Clinical Trials', endpoint: '/api/search/trials', color: '#28a745' },
    { id: 'community', name: 'Community Discussions', endpoint: '/api/search/community', color: '#6f42c1' },
    { id: 'faers', name: 'Adverse Event Reports', endpoint: '/api/search/faers', color: '#dc3545' }
  ]);

  // Search only active data types for selected diseases
  const searchActiveTypes = useCallback(async () => {
    if (filters.diseases.length === 0 || activeDataTypes.length === 0) {
      setDiseasesData([]);
      setHasSearched(false);
      return;
    }

    setLoading(true);
    setHasSearched(true);

    try {
      const baseSearchQuery = {
        diseases: filters.diseases,
        q: filters.query || undefined,
        limit: 50,
        offset: 0
      };

      // Execute searches only for active data types
      const searchPromises = activeDataTypes.map(async (typeId) => {
        const dataType = availableDataTypes.find(dt => dt.id === typeId);
        if (!dataType) return null;
        
        try {
          const response = await api.post(dataType.endpoint, baseSearchQuery);
          return {
            typeId,
            dataType,
            response: response.data
          };
        } catch (error) {
          console.error(`Search failed for ${typeId}:`, error);
          return null;
        }
      });

      const results = await Promise.all(searchPromises);
      
      // Transform responses into MultiDiseaseDataTables format
      const validResults = results.filter((result): result is NonNullable<typeof result> => 
        result !== null && result.response && result.response.total > 0
      );

      const newDiseasesData = validResults.map(result => ({
        diseaseId: result.typeId,
        diseaseName: result.dataType.name,
        data: result.response.results,
        columns: result.response.columns,
        totalCount: result.response.total,
        loading: false,
        // Add search filters and endpoint for export functionality
        searchFilters: {
          diseases: filters.diseases,
          query: filters.query || undefined,
        },
        endpoint: result.dataType.endpoint,
      }));

      setDiseasesData(newDiseasesData);
    } catch (error) {
      console.error('Search failed:', error);
      setDiseasesData([]);
    } finally {
      setLoading(false);
    }
  }, [filters, activeDataTypes, availableDataTypes]);

  // Auto-search when filters change (with debounce)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchActiveTypes();
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchActiveTypes]);

  const handleDiseasesChange = useCallback((selectedDiseases: string[]) => {
    setFilters(prev => ({ ...prev, diseases: selectedDiseases }));
  }, []);

  const handleQueryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFilters(prev => ({ ...prev, query: e.target.value }));
  }, []);

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