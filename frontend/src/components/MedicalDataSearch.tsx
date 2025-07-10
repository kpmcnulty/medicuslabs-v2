import React, { useState, useEffect, useMemo } from 'react';
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
import './MedicalDataSearch.css';

const MedicalDataSearch: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showQueryBuilder, setShowQueryBuilder] = useState(false);
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

  // Perform search
  const performSearch = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const filters = showQueryBuilder ? convertQueryToFilters(query) : {};
      const response = await searchAPI.search(
        searchQuery,
        filters,
        currentPage,
        pageSize
      );
      
      setDocuments(response.results);
      setTotalResults(response.total);
    } catch (err) {
      setError('Failed to search documents. Please try again.');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Search when query or page changes
  useEffect(() => {
    if (searchQuery) {
      performSearch();
    }
  }, [currentPage]);

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
        cell: ({ getValue }) => (
          <span className="source-badge">{getValue<string>()}</span>
        ),
      },
      {
        accessorKey: 'disease_names',
        header: 'Diseases',
        cell: ({ getValue }) => {
          const diseases = getValue<string[]>() || [];
          return (
            <div className="disease-tags">
              {diseases.map((disease, idx) => (
                <span key={idx} className="disease-tag">{disease}</span>
              ))}
            </div>
          );
        },
      },
      {
        accessorKey: 'scraped_at',
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
          return score ? `${(score * 100).toFixed(0)}%` : '-';
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
          <p>{doc.summary || 'No summary available'}</p>
        </div>
        <div className="detail-section">
          <h4>Content Preview</h4>
          <p className="content-preview">
            {doc.content ? doc.content.substring(0, 500) + '...' : 'No content available'}
          </p>
        </div>
        <div className="detail-section">
          <h4>Metadata</h4>
          <div className="metadata-grid">
            <div><strong>URL:</strong> <a href={doc.url} target="_blank" rel="noopener noreferrer">{doc.url}</a></div>
            <div><strong>External ID:</strong> {doc.external_id}</div>
            <div><strong>Created:</strong> {format(new Date(doc.created_at), 'PPpp')}</div>
            {doc.author_names && doc.author_names.length > 0 && (
              <div><strong>Authors:</strong> {doc.author_names.join(', ')}</div>
            )}
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
    <div className="medical-data-search">
      <header className="search-header">
        <h1>Medical Data Search Platform</h1>
        <p className="subtitle">Search across ClinicalTrials.gov, PubMed, and medical forums</p>
      </header>

      <div className="search-controls">
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

        <button
          onClick={() => setShowQueryBuilder(!showQueryBuilder)}
          className="toggle-filters-button"
        >
          {showQueryBuilder ? 'Hide' : 'Show'} Advanced Filters
        </button>
      </div>

      {showQueryBuilder && (
        <div className="query-builder-container">
          <h3>Advanced Filter Builder</h3>
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
            Showing {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, totalResults)} of {totalResults} results
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
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
            >
              Previous
            </button>
            <span>Page {currentPage} of {totalPages}</span>
            <button
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
            >
              Next
            </button>
          </div>
        </>
      )}

      {documents.length === 0 && !loading && searchQuery && (
        <div className="no-results">
          No results found. Try adjusting your search terms or filters.
        </div>
      )}
    </div>
  );
};

export default MedicalDataSearch;