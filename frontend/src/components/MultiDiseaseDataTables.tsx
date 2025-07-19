import React, { useRef, useState } from 'react';
import { Table } from '@tanstack/react-table';
import * as XLSX from 'xlsx';
import axios from 'axios';
import DynamicDataTable from './DynamicDataTable';
import './MultiDiseaseDataTables.css';

// Configure axios with the API base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

interface DiseaseTableData {
  diseaseId: string;
  diseaseName: string;
  data: any[];
  columns: any[];
  loading?: boolean;
  totalCount?: number;
  pagination?: any;
  onPaginationChange?: (pagination: any) => void;
  sorting?: any;
  onSortingChange?: (sorting: any) => void;
  columnFilters?: any;
  onColumnFiltersChange?: (filters: any) => void;
  // For export functionality
  searchFilters?: {
    diseases: string[];
    query?: string;
  };
  endpoint?: string;
}

interface MultiDiseaseDataTablesProps {
  diseases: DiseaseTableData[];
  onRowClick?: (row: any, diseaseId: string) => void;
  expandedRowContent?: ((row: any, diseaseId: string) => React.ReactNode) | null;
}

const MultiDiseaseDataTables: React.FC<MultiDiseaseDataTablesProps> = ({
  diseases,
  onRowClick,
  expandedRowContent,
}) => {
  // Store refs to each table instance to access their data for export
  const tableRefs = useRef<{ [key: string]: Table<any> | null }>({});
  const [exportLoading, setExportLoading] = useState(false);
  const [exportProgress, setExportProgress] = useState<{ current: number; total: number; type: string } | null>(null);

  // Fetch complete dataset for export using pagination
  const fetchCompleteDataset = async (diseaseData: DiseaseTableData): Promise<any[]> => {
    if (!diseaseData.endpoint || !diseaseData.searchFilters) {
      console.log(`No endpoint or searchFilters for ${diseaseData.diseaseId}, using current data`);
      return diseaseData.data; // Fallback to current data
    }

    try {
      const totalRecords = diseaseData.totalCount || diseaseData.data.length;
      const pageSize = 1000; // Fetch in chunks of 1000
      const totalPages = Math.ceil(totalRecords / pageSize);
      
      console.log(`Fetching complete dataset for ${diseaseData.diseaseId}:`, {
        totalRecords,
        pageSize, 
        totalPages,
        endpoint: diseaseData.endpoint
      });

      let allResults: any[] = [];
      
      // Fetch all pages
      for (let page = 0; page < totalPages; page++) {
        // Update progress
        setExportProgress({
          current: page + 1,
          total: totalPages,
          type: diseaseData.diseaseName
        });

        const requestPayload: any = {
          diseases: diseaseData.searchFilters.diseases,
          limit: pageSize,
          offset: page * pageSize,
          search_type: "keyword",
          sort_order: "desc"
        };
        
        // Only include query if it exists
        if (diseaseData.searchFilters.query) {
          requestPayload.q = diseaseData.searchFilters.query;
        }
        
        console.log(`Fetching page ${page + 1}/${totalPages} for ${diseaseData.diseaseId}`);
        
        const response = await api.post(diseaseData.endpoint, requestPayload);
        const pageResults = response.data.results || [];
        
        allResults = [...allResults, ...pageResults];
        
        // Break if we got fewer results than expected (end of data)
        if (pageResults.length < pageSize) {
          console.log(`Reached end of data at page ${page + 1} for ${diseaseData.diseaseId}`);
          break;
        }
      }
      
      console.log(`Complete dataset fetched for ${diseaseData.diseaseId}:`, {
        totalFetched: allResults.length,
        expectedTotal: totalRecords
      });
      
      return allResults;
    } catch (error) {
      console.error(`Failed to fetch complete dataset for ${diseaseData.diseaseId}:`, error);
      return diseaseData.data; // Fallback to current data
    }
  };

  // Export single table to CSV
  const exportTableToCSV = async (diseaseData: DiseaseTableData) => {
    const table = tableRefs.current[diseaseData.diseaseId];
    if (!table) return;

    setExportLoading(true);
    setExportProgress(null);
    
    try {
      const selectedRows = table.getFilteredSelectedRowModel().rows;
      const dataToExport = selectedRows.length > 0 
        ? selectedRows.map(row => row.original)
        : await fetchCompleteDataset(diseaseData); // Fetch complete dataset with pagination

      // Get visible columns (user's selected columns)
      const visibleColumns = table.getAllLeafColumns()
        .filter(col => col.getIsVisible() && col.id !== 'select');

      const headers = visibleColumns
        .map(col => String(col.columnDef.header || col.id));

      console.log(`Exporting ${dataToExport.length} records with ${visibleColumns.length} columns for ${diseaseData.diseaseName}`);

      const csv = [
        headers.join(','),
        ...dataToExport.map(row => 
          visibleColumns
            .map(col => {
              const keys = col.id.split('.');
              let value: any = row;
              for (const key of keys) {
                value = value?.[key];
              }
              value = value ?? '';
              return typeof value === 'string' && value.includes(',') 
                ? `"${value}"` 
                : value;
            })
            .join(',')
        )
      ].join('\n');

      // Download CSV
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${diseaseData.diseaseName}-complete-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      
      console.log(`✅ CSV export completed: ${dataToExport.length} records exported`);
    } catch (error) {
      console.error('CSV export failed:', error);
    } finally {
      setExportLoading(false);
      setExportProgress(null);
    }
  };

  // Export all tables to Excel workbook
  const exportAllToExcel = async () => {
    setExportLoading(true);
    setExportProgress(null);
    
    try {
      const workbook = XLSX.utils.book_new();
      let totalRecordsExported = 0;

      for (const diseaseData of diseases) {
        const table = tableRefs.current[diseaseData.diseaseId];
        if (!table || diseaseData.totalCount === 0) continue;

        console.log(`📊 Processing ${diseaseData.diseaseName} for Excel export...`);

        const selectedRows = table.getFilteredSelectedRowModel().rows;
        const dataToExport = selectedRows.length > 0 
          ? selectedRows.map(row => row.original)
          : await fetchCompleteDataset(diseaseData); // Fetch complete dataset with pagination

        // Get visible columns (user's selected columns)
        const visibleColumns = table.getAllLeafColumns()
          .filter(col => col.getIsVisible() && col.id !== 'select');

        console.log(`Preparing Excel sheet for ${diseaseData.diseaseName}: ${dataToExport.length} records, ${visibleColumns.length} columns`);

        // Prepare data for Excel
        const headers = visibleColumns.map(col => String(col.columnDef.header || col.id));
        const rows = dataToExport.map(row => 
          visibleColumns.map(col => {
            const keys = col.id.split('.');
            let value: any = row;
            for (const key of keys) {
              value = value?.[key];
            }
            return value ?? '';
          })
        );

        // Create worksheet
        const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows]);
        
        // Sanitize sheet name (Excel has restrictions)
        const sanitizedSheetName = diseaseData.diseaseName
          .replace(/[\\\/\?\*\[\]]/g, '') // eslint-disable-line no-useless-escape
          .substring(0, 31);

        XLSX.utils.book_append_sheet(workbook, worksheet, sanitizedSheetName);
        totalRecordsExported += dataToExport.length;
      }

      console.log(`📋 Creating Excel workbook with ${totalRecordsExported} total records across ${diseases.length} sheets`);

      // Download Excel file
      const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `disease-data-complete-${new Date().toISOString().split('T')[0]}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      
      console.log(`✅ Excel export completed: ${totalRecordsExported} total records exported across ${diseases.length} sheets`);
    } catch (error) {
      console.error('Excel export failed:', error);
    } finally {
      setExportLoading(false);
      setExportProgress(null);
    }
  };

  // Get total selected rows across all tables
  const getTotalSelectedRows = () => {
    return diseases.reduce((total, diseaseData) => {
      const table = tableRefs.current[diseaseData.diseaseId];
      if (!table) return total;
      return total + Object.keys(table.getState().rowSelection).length;
    }, 0);
  };

  return (
    <div className="multi-disease-data-tables">
      <div className="multi-table-header">
        <h2>Medical Research Data by Disease</h2>
        <div className="multi-table-actions">
          {getTotalSelectedRows() > 0 && (
            <div className="global-selection-info">
              {getTotalSelectedRows()} total rows selected across all tables
            </div>
          )}
          <button
            className="export-all-btn primary"
            onClick={exportAllToExcel}
            disabled={diseases.every(d => d.data.length === 0) || exportLoading}
          >
            {exportLoading ? (
              <>
                <div className="loading-spinner-small"></div>
                {exportProgress ? (
                  `Fetching ${exportProgress.type} (${exportProgress.current}/${exportProgress.total})`
                ) : (
                  'Preparing Export...'
                )}
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M3 1.5A1.5 1.5 0 0 1 4.5 0h5.086a1.5 1.5 0 0 1 1.06.44l2.914 2.914A1.5 1.5 0 0 1 14 4.414V14.5A1.5 1.5 0 0 1 12.5 16h-8A1.5 1.5 0 0 1 3 14.5V1.5zM11.793 3L9.5 0.707A.5.5 0 0 0 9.146 0.5H4.5a.5.5 0 0 0-.5.5v13a.5.5 0 0 0 .5.5h7a.5.5 0 0 0 .5-.5V3.5a.5.5 0 0 0-.146-.354z"/>
                </svg>
                Export All to Excel
              </>
            )}
          </button>
        </div>
      </div>

      <div className="disease-tables-container">
        {diseases.map((diseaseData, index) => (
          <div key={diseaseData.diseaseId} className="disease-table-section">
            <div className="disease-table-header">
              <h3>{diseaseData.diseaseName}</h3>
              <div className="disease-table-actions">
                <span className="table-count">
                  {diseaseData.totalCount ?? diseaseData.data.length} records
                </span>
                <button
                  className="export-csv-btn"
                  onClick={() => exportTableToCSV(diseaseData)}
                  disabled={diseaseData.data.length === 0 || exportLoading}
                  title={`Export ${diseaseData.diseaseName} data to CSV`}
                >
                  {exportLoading ? (
                    <>
                      <div className="loading-spinner-small"></div>
                      {exportProgress && exportProgress.type === diseaseData.diseaseName ? (
                        `${exportProgress.current}/${exportProgress.total}`
                      ) : (
                        '...'
                      )}
                    </>
                  ) : (
                    <>
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M14 4.5V11h-1V4.5h-2A1.5 1.5 0 0 1 9.5 3V1H4a1 1 0 0 0-1 1v9H2V2a2 2 0 0 1 2-2h5.5L14 4.5z"/>
                        <path d="M11.5 10.5a.5.5 0 0 1-.5.5h-4a.5.5 0 0 1 0-1h4a.5.5 0 0 1 .5.5zm-2-2a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5z"/>
                      </svg>
                      CSV
                    </>
                  )}
                </button>
              </div>
            </div>
            
            <DynamicDataTable
              ref={(tableInstance: any) => {
                if (tableInstance) {
                  tableRefs.current[diseaseData.diseaseId] = tableInstance.table;
                }
              }}
              data={diseaseData.data}
              columns={diseaseData.columns}
              loading={diseaseData.loading}
              totalCount={diseaseData.totalCount}
              pagination={diseaseData.pagination}
              onPaginationChange={diseaseData.onPaginationChange}
              sorting={diseaseData.sorting}
              onSortingChange={diseaseData.onSortingChange}
              columnFilters={diseaseData.columnFilters}
              onColumnFiltersChange={diseaseData.onColumnFiltersChange}
              onRowClick={(row) => onRowClick?.(row, diseaseData.diseaseId)}
              expandedRowContent={expandedRowContent ? (row) => expandedRowContent(row, diseaseData.diseaseId) : null}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default MultiDiseaseDataTables;