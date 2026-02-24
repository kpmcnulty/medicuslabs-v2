import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import * as XLSX from 'xlsx';
import DynamicDataTable from './DynamicDataTable';
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

interface DataTypeConfig {
  id: string;
  name: string;
  icon: string;
  color: string;
  columns: any[];
}

const DATA_TYPE_CONFIGS: DataTypeConfig[] = [
  {
    id: 'publications',
    name: 'Publications',
    icon: '📄',
    color: '#007bff',
    columns: [
      { key: 'title', label: 'Title', type: 'string', sortable: true, width: '400' },
      { key: 'metadata.authors', label: 'Authors', type: 'array', width: '200' },
      { key: 'metadata.journal', label: 'Journal', type: 'string', width: '180' },
      { key: 'metadata.publication_date', label: 'Publication Date', type: 'date', sortable: true, width: '140' },
      { key: 'metadata.article_types', label: 'Article Types', type: 'array', width: '150' },
      { key: 'metadata.keywords', label: 'Keywords', type: 'array', width: '200' },
      { key: 'diseases', label: 'Diseases', type: 'array', width: '180' },
    ]
  },
  {
    id: 'trials',
    name: 'Clinical Trials',
    icon: '🧪',
    color: '#28a745',
    columns: [
      { key: 'title', label: 'Title', type: 'string', sortable: true, width: '400' },
      { key: 'metadata.phase', label: 'Phase', type: 'string', width: '100' },
      { key: 'metadata.status', label: 'Status', type: 'string', width: '120' },
      { key: 'metadata.sponsor', label: 'Sponsor', type: 'string', width: '200' },
      { key: 'metadata.study_type', label: 'Study Type', type: 'string', width: '150' },
      { key: 'metadata.enrollment', label: 'Enrollment', type: 'number', width: '100' },
      { key: 'metadata.start_date', label: 'Start Date', type: 'date', sortable: true, width: '120' },
      { key: 'diseases', label: 'Diseases', type: 'array', width: '180' },
    ]
  },
  {
    id: 'community',
    name: 'Community',
    icon: '💬',
    color: '#6f42c1',
    columns: [
      { key: 'title', label: 'Title', type: 'string', sortable: true, width: '400' },
      { key: 'metadata.subreddit', label: 'Subreddit', type: 'string', width: '150' },
      { key: 'metadata.score', label: 'Score', type: 'number', sortable: true, width: '80' },
      { key: 'metadata.num_comments', label: 'Comments', type: 'number', sortable: true, width: '100' },
      { key: 'metadata.posted_date', label: 'Posted Date', type: 'date', sortable: true, width: '120' },
      { key: 'diseases', label: 'Diseases', type: 'array', width: '180' },
    ]
  },
  {
    id: 'safety',
    name: 'Adverse Events',
    icon: '⚠️',
    color: '#dc3545',
    columns: [
      { key: 'title', label: 'Title', type: 'string', sortable: true, width: '400' },
      { key: 'metadata.serious', label: 'Serious', type: 'boolean', width: '80' },
      { key: 'metadata.reactions', label: 'Reactions', type: 'array', width: '200' },
      { key: 'metadata.drugs', label: 'Drugs', type: 'array', width: '180' },
      { key: 'metadata.patient_age', label: 'Patient Age', type: 'string', width: '100' },
      { key: 'metadata.receive_date', label: 'Report Date', type: 'date', sortable: true, width: '120' },
      { key: 'diseases', label: 'Diseases', type: 'array', width: '180' },
    ]
  },
];

interface DataTypeResults {
  data: any[];
  total: number;
  loading: boolean;
  collapsed: boolean;
  pagination: { pageIndex: number; pageSize: number };
  sorting: any[];
  columnFilters: any[];
}

const DiseaseDataByType: React.FC = () => {
  const [selectedDiseases, setSelectedDiseases] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [counts, setCounts] = useState<Record<string, number>>({
    publications: 0,
    trials: 0,
    community: 0,
    safety: 0,
  });
  const [results, setResults] = useState<Record<string, DataTypeResults>>({});
  const [loading, setLoading] = useState(false);

  // Fetch counts when filters change
  useEffect(() => {
    const fetchCounts = async () => {
      if (selectedDiseases.length === 0) {
        setCounts({ publications: 0, trials: 0, community: 0, safety: 0 });
        return;
      }

      try {
        const params = new URLSearchParams();
        params.set('diseases', selectedDiseases.join(','));
        if (searchQuery.trim()) {
          params.set('q', searchQuery.trim());
        }

        const response = await api.get(`/api/search/counts?${params.toString()}`);
        setCounts(response.data);
      } catch (error) {
        console.error('Error fetching counts:', error);
        setCounts({ publications: 0, trials: 0, community: 0, safety: 0 });
      }
    };

    const timeoutId = setTimeout(fetchCounts, 300);
    return () => clearTimeout(timeoutId);
  }, [selectedDiseases, searchQuery]);

  // Fetch data for a specific data type
  const fetchDataType = useCallback(async (
    dataTypeId: string,
    pageIndex: number = 0,
    pageSize: number = 20,
    sorting: any[] = [],
    columnFilters: any[] = []
  ) => {
    if (selectedDiseases.length === 0) return;

    setResults(prev => ({
      ...prev,
      [dataTypeId]: {
        ...(prev[dataTypeId] || { data: [], total: 0, collapsed: false, columnFilters: [] }),
        loading: true,
        pagination: { pageIndex, pageSize },
        sorting,
        columnFilters,
      }
    }));

    try {
      const query: any = {
        diseases: selectedDiseases,
        source_categories: [dataTypeId],
        limit: pageSize,
        offset: pageIndex * pageSize,
      };

      if (searchQuery.trim()) {
        query.q = searchQuery.trim();
      }

      // Add sorting
      if (sorting.length > 0) {
        query.sort_by = sorting[0].id;
        query.sort_order = sorting[0].desc ? 'desc' : 'asc';
      }

      // Convert column filters to API format
      if (columnFilters.length > 0) {
        query.columnFilters = columnFilters.map((f: any) => ({
          id: f.id,
          value: f.value,
        }));
      }

      const response = await api.post('/api/search/unified', query);

      setResults(prev => ({
        ...prev,
        [dataTypeId]: {
          data: response.data.results,
          total: response.data.total,
          loading: false,
          collapsed: prev[dataTypeId]?.collapsed || false,
          pagination: { pageIndex, pageSize },
          sorting,
          columnFilters,
        }
      }));
    } catch (error) {
      console.error(`Error fetching ${dataTypeId}:`, error);
      setResults(prev => ({
        ...prev,
        [dataTypeId]: {
          data: [],
          total: 0,
          loading: false,
          collapsed: prev[dataTypeId]?.collapsed || false,
          pagination: { pageIndex, pageSize },
          sorting,
          columnFilters,
        }
      }));
    }
  }, [selectedDiseases, searchQuery]);

  // Initialize all data types when filters change
  useEffect(() => {
    if (selectedDiseases.length === 0) {
      setResults({});
      return;
    }

    setLoading(true);
    Promise.all(
      DATA_TYPE_CONFIGS.map(config => fetchDataType(config.id, 0, 20, []))
    ).finally(() => setLoading(false));
  }, [selectedDiseases, searchQuery]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleCollapse = (dataTypeId: string) => {
    setResults(prev => ({
      ...prev,
      [dataTypeId]: {
        ...(prev[dataTypeId] || { data: [], total: 0, loading: false, pagination: { pageIndex: 0, pageSize: 20 }, sorting: [] }),
        collapsed: !prev[dataTypeId]?.collapsed,
      }
    }));
  };

  // Helper: fetch ALL results for a data type (respecting current filters)
  const fetchAllForExport = async (dataTypeId: string): Promise<any[]> => {
    const typeResults = results[dataTypeId];
    if (!typeResults || typeResults.total === 0) return [];

    const query: any = {
      diseases: selectedDiseases,
      source_categories: [dataTypeId],
      limit: Math.min(typeResults.total, 10000), // Cap at 10k
      offset: 0,
    };
    if (searchQuery.trim()) query.q = searchQuery.trim();
    if (typeResults.columnFilters?.length > 0) {
      query.columnFilters = typeResults.columnFilters.map((f: any) => ({ id: f.id, value: f.value }));
    }

    try {
      const response = await api.post('/api/search/unified', query);
      return response.data.results || [];
    } catch {
      return typeResults.data; // Fallback to current page
    }
  };

  // Helper: convert rows to export format
  const rowsToSheetData = (rows: any[], columns: any[]) => {
    return rows.map(row => {
      const obj: any = {};
      columns.forEach(col => {
        const keys = col.key.split('.');
        let value: any = row;
        for (const key of keys) value = value?.[key];
        if (Array.isArray(value)) {
          obj[col.label] = value.map((v: any) => typeof v === 'object' ? (v.name || v.title || JSON.stringify(v)) : v).join('; ');
        } else if (typeof value === 'object' && value !== null) {
          obj[col.label] = value.name || value.title || JSON.stringify(value);
        } else {
          obj[col.label] = value ?? '';
        }
      });
      return obj;
    });
  };

  const [exporting, setExporting] = useState(false);

  const handleExport = async (dataTypeId: string) => {
    const config = DATA_TYPE_CONFIGS.find(c => c.id === dataTypeId);
    if (!config) return;

    setExporting(true);
    try {
      const allRows = await fetchAllForExport(dataTypeId);
      const sheetData = rowsToSheetData(allRows, config.columns);
      
      const ws = XLSX.utils.json_to_sheet(sheetData);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, config.name.substring(0, 31));
      
      const dateStr = new Date().toISOString().split('T')[0];
      XLSX.writeFile(wb, `${dataTypeId}-${dateStr}.csv`);
    } finally {
      setExporting(false);
    }
  };

  const handleExportAllXLSX = async () => {
    setExporting(true);
    try {
      const wb = XLSX.utils.book_new();
      let sheetsAdded = 0;

      for (const config of DATA_TYPE_CONFIGS) {
        const typeResults = results[config.id];
        if (!typeResults || typeResults.collapsed || typeResults.total === 0) continue;

        const allRows = await fetchAllForExport(config.id);
        const sheetData = rowsToSheetData(allRows, config.columns);

        const ws = XLSX.utils.json_to_sheet(sheetData);
        XLSX.utils.book_append_sheet(wb, ws, config.name.substring(0, 31));
        sheetsAdded++;
      }

      if (sheetsAdded === 0) return;

      const dateStr = new Date().toISOString().split('T')[0];
      const diseases = selectedDiseases.slice(0, 3).join('-').replace(/\s+/g, '_');
      XLSX.writeFile(wb, `medicuslabs-${diseases}-${dateStr}.xlsx`);
    } finally {
      setExporting(false);
    }
  };

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
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <svg className="search-icon" width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
            </svg>
          </div>

          <DiseaseSelector
            selectedDiseases={selectedDiseases}
            onDiseasesChange={setSelectedDiseases}
          />
        </div>

        {selectedDiseases.length > 0 && (
          <div className="active-filters">
            <span className="filter-label">Diseases:</span>
            {selectedDiseases.map(disease => (
              <span key={disease} className="filter-tag">
                {disease}
                <button
                  onClick={() => setSelectedDiseases(selectedDiseases.filter(d => d !== disease))}
                  className="remove-filter"
                >
                  ×
                </button>
              </span>
            ))}
            <button
              onClick={() => setSelectedDiseases([])}
              className="clear-all-filters"
            >
              Clear All
            </button>
          </div>
        )}
      </div>

      {selectedDiseases.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h3>Select Diseases to Begin</h3>
          <p>Choose one or more diseases from the selector above to search across all data sources.</p>
        </div>
      )}

      {selectedDiseases.length > 0 && (
        <>
          {/* Summary Cards */}
          <div className="summary-cards">
            {DATA_TYPE_CONFIGS.map(config => (
              <label
                key={config.id}
                className={`summary-card ${counts[config.id] === 0 ? 'disabled' : ''} ${results[config.id]?.collapsed ? 'unchecked' : 'checked'}`}
                style={{ borderLeftColor: results[config.id]?.collapsed ? '#ccc' : config.color }}
              >
                <input
                  type="checkbox"
                  checked={!results[config.id]?.collapsed}
                  onChange={() => counts[config.id] > 0 && toggleCollapse(config.id)}
                  disabled={counts[config.id] === 0}
                  className="card-checkbox"
                />
                <div className="card-icon">{config.icon}</div>
                <div className="card-content">
                  <h3>{config.name}</h3>
                  <p className="card-count">
                    {loading ? '...' : (
                      results[config.id]?.columnFilters?.length > 0 && results[config.id]?.total !== counts[config.id] ? (
                        <>
                          <span className="filtered-count">{results[config.id].total.toLocaleString()}</span>
                          <span className="original-count"> / {counts[config.id].toLocaleString()}</span>
                          <span className="card-label"> filtered</span>
                        </>
                      ) : (
                        <>
                          {counts[config.id].toLocaleString()}
                          <span className="card-label"> results</span>
                        </>
                      )
                    )}
                  </p>
                  {/* Active filter tags */}
                  {results[config.id]?.columnFilters?.length > 0 && (
                    <div className="card-filters">
                      {results[config.id].columnFilters.map((f: any, idx: number) => {
                        const col = config.columns.find((c: any) => c.key === f.id);
                        const label = col?.label || f.id;
                        const conditions = f.value?.conditions || [];
                        const desc = conditions
                          .filter((c: any) => c.value || ['blank', 'notBlank'].includes(c.operator))
                          .map((c: any) => {
                            const opLabels: Record<string, string> = {
                              contains: '⊃', equals: '=', notEqual: '≠',
                              startsWith: 'starts', endsWith: 'ends',
                              notContains: '⊅', greaterThan: '>', lessThan: '<',
                              greaterThanOrEqual: '≥', lessThanOrEqual: '≤',
                              before: '<', after: '>', between: '↔',
                              blank: 'empty', notBlank: 'not empty',
                            };
                            const op = opLabels[c.operator] || c.operator;
                            return `${op} ${c.value || ''}`.trim();
                          })
                          .join(` ${f.value?.joinOperator || 'AND'} `);
                        return (
                          <span key={idx} className="card-filter-tag">
                            <strong>{label}</strong> {desc}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              </label>
            ))}
          </div>

          {/* Export All */}
          <div className="export-all-bar">
            <button
              className="export-all-btn"
              onClick={handleExportAllXLSX}
              disabled={exporting || Object.values(results).every(r => !r || r.collapsed || r.total === 0)}
            >
              {exporting ? '⏳ Exporting...' : '📊 Export All as XLSX'}
            </button>
            <span className="export-hint">Exports visible categories as separate sheets</span>
          </div>

          {/* Table Sections */}
          <div className="table-sections">
            {DATA_TYPE_CONFIGS.map(config => {
              const typeResults = results[config.id];
              if (!typeResults || counts[config.id] === 0) return null;

              return (
                <div
                  key={config.id}
                  id={`section-${config.id}`}
                  className="table-section"
                >
                  <div className="section-header" style={{ borderLeftColor: config.color }}>
                    <div className="section-title">
                      <span className="section-icon">{config.icon}</span>
                      <h2>{config.name}</h2>
                      <span className="result-count">{typeResults.total.toLocaleString()}</span>
                    </div>
                    <div className="section-actions">
                      <button
                        className="export-btn"
                        onClick={() => handleExport(config.id)}
                        disabled={typeResults.data.length === 0 || exporting}
                      >
                        {exporting ? '⏳' : '📥'} CSV
                      </button>
                    </div>
                  </div>

                  {!typeResults.collapsed && (
                    <div className="section-content">
                      <DynamicDataTable
                        data={typeResults.data}
                        columns={config.columns}
                        loading={typeResults.loading}
                        totalCount={typeResults.total}
                        pagination={typeResults.pagination}
                        onPaginationChange={(newPagination) => {
                          fetchDataType(
                            config.id,
                            newPagination.pageIndex,
                            newPagination.pageSize,
                            typeResults.sorting,
                            typeResults.columnFilters
                          );
                        }}
                        sorting={typeResults.sorting}
                        onSortingChange={(newSorting) => {
                          fetchDataType(
                            config.id,
                            0,
                            typeResults.pagination.pageSize,
                            newSorting,
                            typeResults.columnFilters
                          );
                        }}
                        columnFilters={typeResults.columnFilters}
                        onColumnFiltersChange={(newFilters) => {
                          fetchDataType(
                            config.id,
                            0,
                            typeResults.pagination.pageSize,
                            typeResults.sorting,
                            newFilters
                          );
                        }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export default DiseaseDataByType;
