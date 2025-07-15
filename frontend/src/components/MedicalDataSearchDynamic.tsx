import React, { useState, useCallback, useEffect } from 'react';
import { ColumnFiltersState } from '@tanstack/react-table';
import SourceTypeSelector from './SourceTypeSelector';
import DiseaseSelector from './DiseaseSelector';
import DynamicDataTable from './DynamicDataTable';
import './MedicalDataSearchDynamic.css';

interface SearchState {
  query: string;
  sourceTypes: string[];
  disease: string | null;
  metadataFilters: Record<string, any>;
}

const MedicalDataSearchDynamic: React.FC = () => {
  const [searchState, setSearchState] = useState<SearchState>({
    query: '',
    sourceTypes: [],  // Start with no sources selected to prevent auto-search on load
    disease: null,
    metadataFilters: {}
  });

  const [results, setResults] = useState<any[]>([]);
  const [columns, setColumns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalResults, setTotalResults] = useState(0);
  const [sourceBreakdown, setSourceBreakdown] = useState<Record<string, number>>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const pageSize = 20;

  // Perform search
  const performSearch = useCallback(async () => {
    if (!searchState.query && !searchState.disease && searchState.sourceTypes.length === 0) {
      setError('Please enter a search query, select a disease, or choose data sources');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/search/unified`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          q: searchState.query || undefined,
          source_categories: searchState.sourceTypes.length > 0 ? searchState.sourceTypes : undefined,
          diseases: searchState.disease ? [searchState.disease] : undefined,
          metadata: Object.keys(searchState.metadataFilters).length > 0 ? searchState.metadataFilters : undefined,
          columnFilters: columnFilters.length > 0 ? columnFilters.map(filter => ({
            id: filter.id,
            value: filter.value
          })) : undefined,
          limit: pageSize,
          offset: (currentPage - 1) * pageSize
        }),
      });

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status}`);
      }

      const data = await response.json();
      setResults(data.results || []);
      setColumns(data.columns || []);  // Use columns from API response
      setTotalResults(data.total || 0);
      
      // Calculate source breakdown from facets
      const breakdown: Record<string, number> = {};
      if (data.facets && data.facets.sources) {
        data.facets.sources.forEach((facet: any) => {
          breakdown[facet.value] = facet.count;
        });
      }
      setSourceBreakdown(breakdown);
    } catch (err) {
      console.error('Search error:', err);
      setError('Failed to perform search. Please try again.');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [searchState, currentPage, columnFilters]);

  // Auto-search when filters change (but not on initial load with no filters)
  useEffect(() => {
    // Only perform search if user has entered something
    if (searchState.query || searchState.disease || (searchState.sourceTypes.length > 0 && searchState.sourceTypes.length < 3)) {
      const debounceTimer = setTimeout(() => {
        performSearch();
      }, 500);
      return () => clearTimeout(debounceTimer);
    }
  }, [searchState, performSearch, columnFilters]);

  // Reset to page 1 when column filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [columnFilters]);

  // Handle search input
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchState(prev => ({ ...prev, query: e.target.value }));
    setCurrentPage(1);
  };

  // Handle source type selection
  const handleSourceTypeChange = (types: string[]) => {
    setSearchState(prev => ({ ...prev, sourceTypes: types }));
    setCurrentPage(1);
  };

  // Handle disease selection
  const handleDiseaseChange = (disease: string | null) => {
    setSearchState(prev => ({ ...prev, disease }));
    setCurrentPage(1);
  };

  // Handle row click - show details
  const handleRowClick = (row: any) => {
    console.log('Row clicked:', row);
    // TODO: Implement detail view
  };

  // Render expanded row content
  const renderExpandedContent = (row: any) => {
    return (
      <div className="expanded-row-content">
        <h4>{row.title}</h4>
        {row.summary && (
          <div className="summary-section">
            <h5>Summary</h5>
            <p>{row.summary}</p>
          </div>
        )}
        <div className="metadata-section">
          <h5>Metadata</h5>
          <pre>{JSON.stringify(row.metadata, null, 2)}</pre>
        </div>
        <div className="actions">
          <a href={row.url} target="_blank" rel="noopener noreferrer" className="view-source-btn">
            View Original Source
          </a>
        </div>
      </div>
    );
  };

  const totalPages = Math.ceil(totalResults / pageSize);

  return (
    <div className="medical-search-dynamic">
      <header className="search-header">
        <h1>Medical Data Search</h1>
        <p className="subtitle">Search across publications, clinical trials, and community discussions</p>
      </header>

      <div className="search-controls">
        {/* Source Type Selector */}
        <SourceTypeSelector
          selectedTypes={searchState.sourceTypes}
          onSelectionChange={handleSourceTypeChange}
          loading={loading}
        />

        {/* Search Bar and Disease Selector */}
        <div className="search-row">
          <div className="search-input-wrapper">
            <input
              type="text"
              className="search-input"
              placeholder="Search medical data..."
              value={searchState.query}
              onChange={handleSearchChange}
              disabled={loading}
            />
            <button 
              className="search-button"
              onClick={performSearch}
              disabled={loading}
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
          
          <DiseaseSelector
            selectedDisease={searchState.disease}
            onDiseaseChange={handleDiseaseChange}
          />
        </div>
      </div>

      {/* Results Summary */}
      {totalResults > 0 && !loading && (
        <div className="results-summary">
          <div className="summary-text">
            Found <strong>{totalResults}</strong> results
            {searchState.disease && <> for <span className="highlight">{searchState.disease}</span></>}
            {searchState.query && <> matching "<span className="highlight">{searchState.query}</span>"</>}
          </div>
          {Object.keys(sourceBreakdown).length > 0 && (
            <div className="source-breakdown">
              {Object.entries(sourceBreakdown).map(([source, count]) => (
                <span key={source} className="source-count">
                  {source}: {count}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {/* Results Table */}
      <div className="results-container">
        <DynamicDataTable
          data={results}
          columns={columns}
          loading={loading}
          onRowClick={handleRowClick}
          expandedRowContent={renderExpandedContent}
          onColumnFiltersChange={setColumnFilters}
          externalFilters={columnFilters}
        />
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1 || loading}
          >
            Previous
          </button>
          <span className="page-info">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages || loading}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default MedicalDataSearchDynamic;