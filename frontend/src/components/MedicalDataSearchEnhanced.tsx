import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getExpandedRowModel,
  ColumnDef,
  flexRender,
  Row,
} from '@tanstack/react-table';
import QueryBuilder, { RuleGroupType, formatQuery } from 'react-querybuilder';
import { searchAPI } from '../api/search';
import { Document, SearchFilters } from '../types';
import { format } from 'date-fns';
import EnhancedFilters from './EnhancedFilters';
import './MedicalDataSearchEnhanced.css';

const MedicalDataSearchEnhanced: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showQueryBuilder, setShowQueryBuilder] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [searchType, setSearchType] = useState<'keyword' | 'semantic' | 'hybrid'>('hybrid');
  const [enhancedFilters, setEnhancedFilters] = useState<any>({});
  const [query, setQuery] = useState<RuleGroupType>({
    combinator: 'and',
    rules: [],
  });

  const pageSize = 20;

  // Define the fields for the query builder
  const fields = [
    { name: 'title', label: 'Title', inputType: 'text' },
    { name: 'content', label: 'Content', inputType: 'text' },
    { name: 'source', label: 'Source', inputType: 'select', values: [
      { name: 'ClinicalTrials.gov', label: 'ClinicalTrials.gov' },
      { name: 'PubMed', label: 'PubMed' },
      { name: 'Reddit Medical', label: 'Reddit Medical' },
    ]},
    { name: 'disease', label: 'Disease/Condition', inputType: 'text' },
    { name: 'study_phase', label: 'Study Phase', inputType: 'select', values: [
      { name: 'Phase 1', label: 'Phase 1' },
      { name: 'Phase 2', label: 'Phase 2' },
      { name: 'Phase 3', label: 'Phase 3' },
      { name: 'Phase 4', label: 'Phase 4' },
    ]},
    { name: 'publication_type', label: 'Publication Type', inputType: 'text' },
    { name: 'date', label: 'Date', inputType: 'date' },
    { name: 'relevance_score', label: 'Relevance Score', inputType: 'number' },
  ];

  // Convert query builder rules to search filters
  const convertQueryToFilters = (query: RuleGroupType): SearchFilters => {
    const filters: SearchFilters = {};
    
    query.rules.forEach((rule) => {
      if ('field' in rule) {
        switch (rule.field) {
          case 'source':
            filters.sources = [rule.value as string];
            break;
          case 'disease':
            filters.diseases = [rule.value as string];
            break;
          case 'study_phase':
            filters.study_phase = [rule.value as string];
            break;
          case 'publication_type':
            filters.publication_type = [rule.value as string];
            break;
          case 'date':
            if (rule.operator === '>' || rule.operator === '>=') {
              filters.date_from = rule.value as string;
            } else if (rule.operator === '<' || rule.operator === '<=') {
              filters.date_to = rule.value as string;
            }
            break;
        }
      }
    });
    
    return filters;
  };

  // Combine all filters
  const getCombinedFilters = () => {
    const queryBuilderFilters = showQueryBuilder ? convertQueryToFilters(query) : {};
    return {
      ...queryBuilderFilters,
      ...enhancedFilters,
    };
  };

  // Perform search using enhanced API
  const performSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const filters = getCombinedFilters();
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/search/enhanced`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          q: searchQuery,
          ...filters,
          search_type: searchType,
          limit: pageSize,
          offset: (currentPage - 1) * pageSize,
        }),
      });

      if (!response.ok) {
        throw new Error('Search failed');
      }

      const data = await response.json();
      setDocuments(data.results);
      setTotalResults(data.total);
    } catch (err) {
      setError('Failed to search documents. Please try again.');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, currentPage, searchType, enhancedFilters, query, showQueryBuilder]);

  // Search when filters or page changes
  useEffect(() => {
    if (searchQuery) {
      performSearch();
    }
  }, [currentPage, searchType, enhancedFilters]);

  // Handle filter changes from EnhancedFilters component
  const handleFiltersChange = useCallback((filters: any) => {
    setEnhancedFilters(filters);
    setCurrentPage(1); // Reset to first page when filters change
  }, []);

  // Define columns for the table
  const columns = useMemo<ColumnDef<Document>[]>(
    () => [
      {
        id: 'expander',
        header: () => null,
        cell: ({ row }) => {
          return row.getCanExpand() ? (
            <button
              {...{
                onClick: row.getToggleExpandedHandler(),
                style: { cursor: 'pointer' },
              }}
              className="expand-button"
            >
              {row.getIsExpanded() ? '▼' : '▶'}
            </button>
          ) : null;
        },
      },
      {
        accessorKey: 'title',
        header: 'Title',
        cell: ({ getValue }) => {
          const title = getValue<string>();
          return <div className="title-cell">{title || 'Untitled'}</div>;
        },
      },
      {
        accessorKey: 'source_name',
        header: 'Source',
        cell: ({ row }) => (
          <div>
            <span className="source-badge">{row.original.source_name}</span>
            <span className="source-type">{row.original.source_type}</span>
          </div>
        ),
      },
      {
        accessorKey: 'disease_tags',
        header: 'Diseases',
        cell: ({ getValue }) => {
          const diseases = getValue<string[]>() || [];
          return (
            <div className="disease-tags">
              {diseases.slice(0, 3).map((disease, idx) => (
                <span key={idx} className="disease-tag">{disease}</span>
              ))}
              {diseases.length > 3 && (
                <span className="disease-tag more">+{diseases.length - 3}</span>
              )}
            </div>
          );
        },
      },
      {
        accessorKey: 'created_at',
        header: 'Date',
        cell: ({ getValue }) => {
          const date = getValue<string>();
          return date ? format(new Date(date), 'MMM dd, yyyy') : '-';
        },
      },
      {
        accessorKey: 'relevance_score',
        header: 'Relevance',
        cell: ({ getValue }) => {
          const score = getValue<number>();
          return (
            <div className="relevance-score">
              <div className="score-bar">
                <div 
                  className="score-fill" 
                  style={{ width: `${(score || 0) * 100}%` }}
                />
              </div>
              <span className="score-text">{score ? `${(score * 100).toFixed(0)}%` : '-'}</span>
            </div>
          );
        },
      },
    ],
    []
  );

  // Render expanded row content
  const renderSubComponent = ({ row }: { row: Row<Document> }) => {
    const doc = row.original;
    return (
      <div className="expanded-content">
        <div className="detail-section">
          <h4>Summary</h4>
          <p>{doc.snippet || doc.summary || 'No summary available'}</p>
        </div>
        {doc.metadata && Object.keys(doc.metadata).length > 0 && (
          <div className="detail-section">
            <h4>Additional Information</h4>
            <div className="metadata-grid">
              {doc.metadata.phase && (
                <div><strong>Study Phase:</strong> {Array.isArray(doc.metadata.phase) ? doc.metadata.phase.join(', ') : doc.metadata.phase}</div>
              )}
              {doc.metadata.status && (
                <div><strong>Status:</strong> {doc.metadata.status}</div>
              )}
              {doc.metadata.study_type && (
                <div><strong>Study Type:</strong> {doc.metadata.study_type}</div>
              )}
              {doc.metadata.journal && (
                <div><strong>Journal:</strong> {doc.metadata.journal}</div>
              )}
              {doc.metadata.pmid && (
                <div><strong>PubMed ID:</strong> {doc.metadata.pmid}</div>
              )}
              {doc.metadata.nct_id && (
                <div><strong>NCT ID:</strong> {doc.metadata.nct_id}</div>
              )}
            </div>
          </div>
        )}
        <div className="detail-section">
          <h4>Links & References</h4>
          <div className="metadata-grid">
            {doc.url && (
              <div><strong>URL:</strong> <a href={doc.url} target="_blank" rel="noopener noreferrer">{doc.url}</a></div>
            )}
            <div><strong>External ID:</strong> {doc.external_id}</div>
            <div><strong>Added to System:</strong> {format(new Date(doc.created_at), 'PPpp')}</div>
          </div>
        </div>
      </div>
    );
  };

  // Setup the table
  const table = useReactTable({
    data: documents,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getRowCanExpand: () => true,
  });

  const totalPages = Math.ceil(totalResults / pageSize);

  return (
    <div className="medical-data-search-enhanced">
      <header className="search-header">
        <h1>Medical Data Search Platform</h1>
        <p className="subtitle">Advanced search across ClinicalTrials.gov, PubMed, and medical forums</p>
      </header>

      <div className="search-container">
        <div className={`sidebar ${showSidebar ? 'visible' : 'hidden'}`}>
          <EnhancedFilters onFiltersChange={handleFiltersChange} loading={loading} />
        </div>

        <div className="main-content">
          <div className="search-controls">
            <div className="search-bar-row">
              <button 
                className="sidebar-toggle"
                onClick={() => setShowSidebar(!showSidebar)}
                title={showSidebar ? 'Hide filters' : 'Show filters'}
              >
                {showSidebar ? '◀' : '▶'}
              </button>

              <div className="search-bar">
                <input
                  type="text"
                  placeholder="Search medical data..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      setCurrentPage(1);
                      performSearch();
                    }
                  }}
                  className="search-input"
                />
                <select 
                  value={searchType} 
                  onChange={(e) => setSearchType(e.target.value as any)}
                  className="search-type-select"
                >
                  <option value="keyword">Keyword</option>
                  <option value="semantic">Semantic</option>
                  <option value="hybrid">Hybrid</option>
                </select>
                <button 
                  onClick={() => {
                    setCurrentPage(1);
                    performSearch();
                  }}
                  disabled={loading}
                  className="search-button"
                >
                  {loading ? 'Searching...' : 'Search'}
                </button>
              </div>
            </div>

            <button
              onClick={() => setShowQueryBuilder(!showQueryBuilder)}
              className="toggle-filters-button"
            >
              {showQueryBuilder ? 'Hide' : 'Show'} Query Builder
            </button>
          </div>

          {showQueryBuilder && (
            <div className="query-builder-container">
              <h3>Advanced Query Builder</h3>
              <QueryBuilder
                fields={fields}
                query={query}
                onQueryChange={setQuery}
              />
              <div className="query-preview">
                <strong>SQL Preview:</strong>
                <code>{formatQuery(query, 'sql')}</code>
              </div>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}

          {documents.length > 0 && (
            <>
              <div className="results-info">
                <span>Showing {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, totalResults)} of {totalResults} results</span>
                {loading && <span className="loading-indicator">Refreshing...</span>}
              </div>

              <div className="data-table">
                <table>
                  <thead>
                    {table.getHeaderGroups().map(headerGroup => (
                      <tr key={headerGroup.id}>
                        {headerGroup.headers.map(header => (
                          <th key={header.id}>
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                  <tbody>
                    {table.getRowModel().rows.map(row => (
                      <React.Fragment key={row.id}>
                        <tr>
                          {row.getVisibleCells().map(cell => (
                            <td key={cell.id}>
                              {flexRender(
                                cell.column.columnDef.cell,
                                cell.getContext()
                              )}
                            </td>
                          ))}
                        </tr>
                        {row.getIsExpanded() && (
                          <tr>
                            <td colSpan={columns.length}>
                              {renderSubComponent({ row })}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pagination">
                <button
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                  className="pagination-btn"
                >
                  First
                </button>
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className="pagination-btn"
                >
                  Previous
                </button>
                <span className="page-info">
                  Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
                </span>
                <button
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                  className="pagination-btn"
                >
                  Next
                </button>
                <button
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage === totalPages}
                  className="pagination-btn"
                >
                  Last
                </button>
              </div>
            </>
          )}

          {documents.length === 0 && !loading && searchQuery && (
            <div className="no-results">
              <h3>No results found</h3>
              <p>Try adjusting your search terms or filters.</p>
            </div>
          )}

          {documents.length === 0 && !loading && !searchQuery && (
            <div className="welcome-message">
              <h2>Welcome to Medical Data Search</h2>
              <p>Enter a search term above to begin exploring medical data from multiple sources.</p>
              <div className="feature-list">
                <div className="feature">
                  <h4>🔍 Advanced Filtering</h4>
                  <p>Filter by source, disease, study phase, publication type, and more</p>
                </div>
                <div className="feature">
                  <h4>🧬 Multiple Data Sources</h4>
                  <p>Search across ClinicalTrials.gov, PubMed, and medical forums</p>
                </div>
                <div className="feature">
                  <h4>📊 Smart Search</h4>
                  <p>Choose between keyword, semantic, or hybrid search modes</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MedicalDataSearchEnhanced;