import React, { useMemo, useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  ColumnDef,
  VisibilityState,
  PaginationState,
  SortingState,
  ColumnFiltersState,
  ColumnPinningState,
  RowSelectionState,
  ColumnOrderState,
} from '@tanstack/react-table';
import { renderCellValue } from '../utils/cellRenderers';
import './DynamicDataTable.css';

interface DynamicDataTableProps {
  data: any[];
  columns: any[];
  loading?: boolean;
  onRowClick?: (row: any) => void;
  expandedRowContent?: ((row: any) => React.ReactNode) | null;
  // Server-side state management
  totalCount?: number;
  pagination?: PaginationState;
  onPaginationChange?: (pagination: PaginationState) => void;
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  columnFilters?: ColumnFiltersState;
  onColumnFiltersChange?: (filters: ColumnFiltersState) => void;
}

const DynamicDataTable = forwardRef<{ table: any }, DynamicDataTableProps>(({
  data,
  columns: columnConfig,
  loading = false,
  onRowClick,
  expandedRowContent,
  totalCount,
  pagination,
  onPaginationChange,
  sorting,
  onSortingChange,
  columnFilters,
  onColumnFiltersChange,
}, ref) => {
  // Local UI state only
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [columnPinning, setColumnPinning] = useState<ColumnPinningState>({ left: [], right: [] });
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>([]);
  const [showColumnSettings, setShowColumnSettings] = useState(false);
  const [selectedRow, setSelectedRow] = useState<any>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  // Set default visibility only (let users control pinning)
  useEffect(() => {
    const defaultVisibility: VisibilityState = {
      select: true, // Always show selection column
    };
    let metadataCount = 0;
    
    columnConfig.forEach((col: any) => {
      // Always show base columns
      if (!col.key.startsWith('metadata.')) {
        defaultVisibility[col.key] = true;
      } else {
        // Show first 8 metadata columns, hide the rest
        defaultVisibility[col.key] = metadataCount < 8;
        metadataCount++;
      }
    });
    
    setColumnVisibility(defaultVisibility);
    // Only pin select column by default, let users control other columns
    setColumnPinning({ left: ['select'], right: [] });
    // Set initial column order
    setColumnOrder(['select', ...columnConfig.map((col: any) => col.key)]);
  }, [columnConfig]);

  // Build column definitions from dynamic config
  const columns = useMemo<ColumnDef<any>[]>(() => {
    // Add select column first
    const selectColumn: ColumnDef<any> = {
      id: 'select',
      header: ({ table }: any) => (
        <input
          type="checkbox"
          checked={table.getIsAllPageRowsSelected()}
          onChange={table.getToggleAllPageRowsSelectedHandler()}
        />
      ),
      cell: ({ row }: any) => (
        <input
          type="checkbox"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          disabled={!row.getCanSelect()}
        />
      ),
      size: 40,
      enableSorting: false,
      enableColumnFilter: false,
    };
    
    const dataColumns = columnConfig.map((col: any) => ({
      id: col.key,
      accessorKey: col.key,
      header: col.label,
      size: parseInt(col.width) || 150,
      enableSorting: col.sortable !== false,
      // Enable column filtering for server-side
      enableColumnFilter: true,
      cell: ({ getValue, row }: any) => {
        const value = getValue();
        
        // Make title column a clickable link if there's a URL
        if (col.key === 'title' && row.original.url) {
          return (
            <a 
              href={row.original.url} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="title-link"
              onClick={(e) => e.stopPropagation()}
            >
              {value}
            </a>
          );
        }
        
        return renderCellValue(value, col);
      },
    }));
    
    return [selectColumn, ...dataColumns];
  }, [columnConfig]);

  const table = useReactTable({
    data,
    columns,
    pageCount: totalCount ? Math.ceil(totalCount / (pagination?.pageSize || 20)) : undefined,
    state: {
      columnVisibility,
      columnPinning,
      rowSelection,
      columnOrder,
      pagination: pagination || { pageIndex: 0, pageSize: 20 },
      sorting: sorting || [],
      columnFilters: columnFilters || [],
    },
    onColumnVisibilityChange: setColumnVisibility,
    onColumnPinningChange: setColumnPinning,
    onRowSelectionChange: setRowSelection,
    onColumnOrderChange: setColumnOrder,
    enableRowSelection: true,
    enableMultiRowSelection: true,
    onPaginationChange: (updater) => {
      if (onPaginationChange && pagination) {
        const newPagination = typeof updater === 'function' ? updater(pagination) : updater;
        onPaginationChange(newPagination);
      }
    },
    onSortingChange: (updater) => {
      if (onSortingChange) {
        const newSorting = typeof updater === 'function' ? updater(sorting || []) : updater;
        onSortingChange(newSorting);
      }
    },
    onColumnFiltersChange: (updater) => {
      if (onColumnFiltersChange) {
        const newFilters = typeof updater === 'function' ? updater(columnFilters || []) : updater;
        onColumnFiltersChange(newFilters);
      }
    },
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true, // Server-side filtering
  });

  // Expose table instance to parent via ref
  useImperativeHandle(ref, () => ({
    table,
  }));

  if (loading) {
    return (
      <div className="table-loading">
        <div className="loading-spinner"></div>
        <p>Loading results...</p>
      </div>
    );
  }

  if (data.length === 0 && !loading) {
    return (
      <div className="table-empty">
        <p>No results found</p>
      </div>
    );
  }

  return (
    <div className="dynamic-data-table">
      <div className="table-toolbar">
        <div className="toolbar-left">
          {Object.keys(rowSelection).length > 0 && (
            <div className="selection-info">
              {Object.keys(rowSelection).length} row{Object.keys(rowSelection).length > 1 ? 's' : ''} selected
              <button
                className="clear-selection-btn"
                onClick={() => setRowSelection({})}
              >
                Clear
              </button>
              <button
                className="export-btn"
                onClick={() => {
                  // Get selected rows using TanStack's API
                  const selectedRows = table.getFilteredSelectedRowModel().rows;
                  const dataToExport = selectedRows.map(row => row.original);
                  
                  // Simple CSV export
                  const visibleColumns = table.getAllLeafColumns()
                    .filter(col => col.getIsVisible() && col.id !== 'select');
                  
                  const headers = visibleColumns
                    .map(col => String(col.columnDef.header || col.id));
                  
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
                  a.download = `export-${new Date().toISOString().split('T')[0]}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                Export Selected
              </button>
            </div>
          )}
        </div>
        <div className="toolbar-right">
          {columnFilters && columnFilters.length > 0 && (
            <div className="active-filters-info">
              <span className="filter-badge">{columnFilters.length} filter{columnFilters.length > 1 ? 's' : ''} active</span>
              <button
                className="clear-filters-btn"
                onClick={() => onColumnFiltersChange?.([])}
              >
                Clear All
              </button>
            </div>
          )}
          <button
            className="column-settings-btn"
            onClick={() => setShowColumnSettings(!showColumnSettings)}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Columns
          </button>
        </div>
        
        {showColumnSettings && (
          <div className="column-settings-dropdown">
            <div className="column-settings-header">
              <h3>Table Settings</h3>
              <button
                className="reset-btn"
                onClick={() => {
                  table.resetColumnVisibility();
                  table.resetColumnPinning();
                  table.resetColumnOrder();
                }}
              >
                Reset
              </button>
            </div>
            
            <div className="column-settings-content">
              <h4>Column Settings</h4>
              <div className="column-settings-list">
                {table.getAllLeafColumns().map(column => {
                  const config = columnConfig.find((col: any) => col.key === column.id);
                  const isPinned = column.getIsPinned();
                  
                  return (
                    <div key={column.id} className="column-settings-item">
                      <label className="column-toggle">
                        <input
                          type="checkbox"
                          checked={column.getIsVisible()}
                          onChange={column.getToggleVisibilityHandler()}
                        />
                        {config?.label || column.id}
                      </label>
                      
                      {column.id !== 'select' && (
                        <div className="column-pin-controls">
                          <button
                            className={`pin-btn ${isPinned === 'left' ? 'active' : ''}`}
                            onClick={() => {
                              if (isPinned === 'left') {
                                column.pin(false);
                              } else {
                                column.pin('left');
                              }
                            }}
                            title="Pin to left"
                          >
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                              <path d="M2 2v12h2V2H2zm4 0v12h2V8l4 4V4l-4 4V2H6z"/>
                            </svg>
                          </button>
                          <button
                            className={`pin-btn ${isPinned === 'right' ? 'active' : ''}`}
                            onClick={() => {
                              if (isPinned === 'right') {
                                column.pin(false);
                              } else {
                                column.pin('right');
                              }
                            }}
                            title="Pin to right"
                          >
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                              <path d="M14 2v12h-2V2h2zm-4 0v12H8V8L4 4v8l4-4v6H8z"/>
                            </svg>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
      <div className="table-wrapper">
        <table>
          <thead>
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => {
                  const isPinned = header.column.getIsPinned();
                  const isLastLeftPinned = isPinned === 'left' && header.column.getIsLastColumn('left');
                  const isFirstRightPinned = isPinned === 'right' && header.column.getIsFirstColumn('right');
                  
                  return (
                    <th 
                      key={header.id}
                      style={{ 
                        width: header.getSize(),
                        position: isPinned ? 'sticky' : 'relative',
                        left: isPinned === 'left' ? header.column.getStart('left') : undefined,
                        right: isPinned === 'right' ? header.column.getAfter('right') : undefined,
                        zIndex: isPinned ? 1 : 0,
                        background: isPinned ? '#f8f9fa' : undefined,
                        boxShadow: isLastLeftPinned ? '2px 0 5px -2px rgba(0,0,0,0.1)' : 
                                   isFirstRightPinned ? '-2px 0 5px -2px rgba(0,0,0,0.1)' : undefined,
                      }}
                      className={`
                        ${header.column.getCanSort() ? 'sortable' : ''}
                        ${header.column.getFilterValue() ? 'has-filter' : ''}
                      `}
                    >
                  <div className="header-content">
                    <span 
                      className="header-label"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {header.column.getIsSorted() && (
                        <span className="sort-indicator">
                          {header.column.getIsSorted() === 'asc' ? ' ↑' : ' ↓'}
                        </span>
                      )}
                    </span>
                    {header.column.getCanFilter() && header.column.id !== 'select' && (
                      <input
                        type="text"
                        value={(header.column.getFilterValue() ?? '') as string}
                        onChange={e => header.column.setFilterValue(e.target.value)}
                        onClick={e => e.stopPropagation()}
                        placeholder="Filter..."
                        className="column-filter-input"
                      />
                    )}
                  </div>
                  {header.column.getCanResize() && (
                    <div
                      className="resizer"
                      onMouseDown={header.getResizeHandler()}
                      onTouchStart={header.getResizeHandler()}
                    />
                  )}
                </th>
                  );
                })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr 
              key={row.id}
              className="data-row"
              onClick={() => {
                setSelectedRow(row.original);
                setShowDetailModal(true);
              }}
            >
              {row.getVisibleCells().map(cell => {
                const isPinned = cell.column.getIsPinned();
                const isLastLeftPinned = isPinned === 'left' && cell.column.getIsLastColumn('left');
                const isFirstRightPinned = isPinned === 'right' && cell.column.getIsFirstColumn('right');
                
                return (
                  <td 
                    key={cell.id} 
                    style={{ 
                      width: cell.column.getSize(),
                      position: isPinned ? 'sticky' : 'relative',
                      left: isPinned === 'left' ? cell.column.getStart('left') : undefined,
                      right: isPinned === 'right' ? cell.column.getAfter('right') : undefined,
                      zIndex: isPinned ? 1 : 0,
                      background: isPinned ? 'white' : undefined,
                      boxShadow: isLastLeftPinned ? '2px 0 5px -2px rgba(0,0,0,0.1)' : 
                                 isFirstRightPinned ? '-2px 0 5px -2px rgba(0,0,0,0.1)' : undefined,
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        </table>
      </div>

      {/* TanStack Pagination */}
      {totalCount && totalCount > (pagination?.pageSize || 20) && (
        <div className="table-pagination">
          <button
            onClick={() => table.setPageIndex(0)}
            disabled={!table.getCanPreviousPage()}
          >
            {'<<'}
          </button>
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            {'<'}
          </button>
          <span className="pagination-info">
            Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
          </span>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            {'>'}
          </button>
          <button
            onClick={() => table.setPageIndex(table.getPageCount() - 1)}
            disabled={!table.getCanNextPage()}
          >
            {'>>'}
          </button>
          <select
            value={table.getState().pagination.pageSize}
            onChange={e => {
              table.setPageSize(Number(e.target.value));
            }}
          >
            {[10, 20, 30, 40, 50].map(pageSize => (
              <option key={pageSize} value={pageSize}>
                Show {pageSize}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedRow && (
        <div className="detail-modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="detail-modal-header">
              <h3>Record Details</h3>
              <button 
                className="close-modal-btn"
                onClick={() => setShowDetailModal(false)}
                aria-label="Close modal"
              >
                ×
              </button>
            </div>
            <div className="detail-modal-content">
              {/* Main fields */}
              {columnConfig.filter((col: any) => !col.key.startsWith('metadata.')).map((col: any) => {
                const keys = col.key.split('.');
                let value: any = selectedRow;
                for (const key of keys) {
                  value = value?.[key];
                }
                
                if (value === null || value === undefined || value === '') return null;
                
                return (
                  <div key={col.key} className="detail-field">
                    <label>{col.label}:</label>
                    <div className="detail-value">
                      {col.key === 'url' || (typeof value === 'string' && value.startsWith('http')) ? (
                        <a href={value} target="_blank" rel="noopener noreferrer" className="detail-link">
                          {value}
                        </a>
                      ) : (
                        renderCellValue(value, col)
                      )}
                    </div>
                  </div>
                );
              })}
              
              {/* Metadata fields */}
              {selectedRow.metadata && Object.keys(selectedRow.metadata).length > 0 && (
                <>
                  <div className="detail-field">
                    <label>Additional Details:</label>
                  </div>
                  {Object.entries(selectedRow.metadata).map(([key, value]) => {
                    if (value === null || value === undefined || value === '') return null;
                    
                    // Format the key nicely
                    const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    
                    return (
                      <div key={`metadata.${key}`} className="detail-field metadata-field">
                        <label>{formattedKey}:</label>
                        <div className="detail-value">
                          {typeof value === 'string' && value.startsWith('http') ? (
                            <a href={value} target="_blank" rel="noopener noreferrer" className="detail-link">
                              {value}
                            </a>
                          ) : Array.isArray(value) ? (
                            <div className="list-value">
                              {value.map((item: any, idx: number) => (
                                <span key={idx} className="list-item">{String(item)}</span>
                              ))}
                            </div>
                          ) : typeof value === 'object' ? (
                            <pre className="json-value">{JSON.stringify(value, null, 2)}</pre>
                          ) : (
                            <span>{String(value)}</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
            <div className="detail-modal-footer">
              <button 
                className="modal-action-btn"
                onClick={() => setShowDetailModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

DynamicDataTable.displayName = 'DynamicDataTable';

export default DynamicDataTable;