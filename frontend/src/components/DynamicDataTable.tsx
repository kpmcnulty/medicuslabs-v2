import React, { useMemo, useState, useEffect, useCallback } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getExpandedRowModel,
  getFilteredRowModel,
  ColumnDef,
  flexRender,
  ExpandedState,
  ColumnFiltersState,
} from '@tanstack/react-table';
import { format } from 'date-fns';
import { ColumnFilterMenu } from './filters/ColumnFilterMenu';
import './DynamicDataTable.css';

interface DynamicDataTableProps {
  data: any[];
  columns: any[];
  loading?: boolean;
  onRowClick?: (row: any) => void;
  expandedRowContent?: (row: any) => React.ReactNode;
  onColumnFiltersChange?: (filters: ColumnFiltersState) => void;
  externalFilters?: ColumnFiltersState;
}

const DynamicDataTable: React.FC<DynamicDataTableProps> = ({
  data,
  columns: columnConfig,
  loading = false,
  onRowClick,
  expandedRowContent,
  onColumnFiltersChange,
  externalFilters
}) => {
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>(externalFilters || []);

  // Sync with external filters if provided
  useEffect(() => {
    if (externalFilters) {
      setColumnFilters(externalFilters);
    }
  }, [externalFilters]);

  // Notify parent of filter changes
  const handleColumnFiltersChange = useCallback((updater: any) => {
    const newFilters = typeof updater === 'function' ? updater(columnFilters) : updater;
    setColumnFilters(newFilters);
    onColumnFiltersChange?.(newFilters);
  }, [columnFilters, onColumnFiltersChange]);

  // Build column definitions from dynamic config
  const columns = useMemo<ColumnDef<any>[]>(() => {
    const cols: ColumnDef<any>[] = [];

    // Add expander column if needed
    if (expandedRowContent) {
      cols.push({
        id: 'expander',
        header: '',
        cell: ({ row }) => (
          <button
            className="row-expander"
            onClick={(e) => {
              e.stopPropagation();
              row.toggleExpanded();
            }}
          >
            {row.getIsExpanded() ? '▼' : '▶'}
          </button>
        ),
        size: 40,
      });
    }

    // Add dynamic columns
    columnConfig.forEach((col: any) => {
      cols.push({
        accessorKey: col.key,
        header: col.label,
        size: parseInt(col.width) || 100,
        enableColumnFilter: col.filterable !== false, // Enable filtering by default
        filterFn: advancedFilter,
        cell: ({ getValue, row }) => {
          const value = getValue();
          
          // Handle nested keys
          if (col.key.includes('.')) {
            const keys = col.key.split('.');
            let nestedValue = row.original;
            for (const key of keys) {
              nestedValue = nestedValue?.[key];
            }
            return renderCellValue(nestedValue, col);
          }
          
          return renderCellValue(value, col);
        }
      });
    });

    return cols;
  }, [columnConfig, expandedRowContent]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    state: {
      expanded,
      columnFilters,
    },
    onExpandedChange: setExpanded,
    onColumnFiltersChange: handleColumnFiltersChange,
  });

  // Render cell value based on type and render config
  const renderCellValue = (value: any, col: any) => {
    if (value === null || value === undefined) {
      return <span className="null-value">—</span>;
    }

    // Handle different render types
    switch (col.render) {
      case 'first_three':
        if (Array.isArray(value)) {
          const authors = value.slice(0, 3).map((a: any) => 
            typeof a === 'object' ? a.name : a
          ).filter(Boolean);
          const remaining = value.length - 3;
          return (
            <span className="array-value">
              {authors.join(', ')}
              {remaining > 0 && <span className="more-count"> +{remaining} more</span>}
            </span>
          );
        }
        break;

      case 'tags':
        if (Array.isArray(value)) {
          return (
            <div className="tags-container">
              {value.slice(0, 3).map((tag, idx) => (
                <span key={idx} className="tag">{tag}</span>
              ))}
              {value.length > 3 && <span className="more-count">+{value.length - 3}</span>}
            </div>
          );
        }
        break;

      case 'status_badge':
        return (
          <span className={`status-badge status-${(value || '').toLowerCase().replace(/\s+/g, '-')}`}>
            {value}
          </span>
        );

      case 'badge':
        return <span className="badge">{value}</span>;

      case 'engagement_stats':
        if (typeof value === 'object') {
          return (
            <div className="engagement-stats">
              {value.upvotes && <span>👍 {value.upvotes}</span>}
              {value.comments && <span>💬 {value.comments}</span>}
            </div>
          );
        }
        break;
    }

    // Handle data types
    switch (col.type) {
      case 'date':
        if (value) {
          try {
            return format(new Date(value), 'MMM d, yyyy');
          } catch {
            return value;
          }
        }
        break;

      case 'array':
        if (Array.isArray(value)) {
          return <span className="array-value">{value.join(', ')}</span>;
        }
        break;

      case 'object':
        if (typeof value === 'object') {
          return <span className="object-value">{JSON.stringify(value)}</span>;
        }
        break;

      default:
        // String/number - truncate if too long
        const strValue = String(value);
        if (strValue.length > 100) {
          return (
            <span className="truncated" title={strValue}>
              {strValue.substring(0, 100)}...
            </span>
          );
        }
        return strValue;
    }

    return String(value);
  };

  if (loading) {
    return (
      <div className="table-loading">
        <div className="loading-spinner"></div>
        <p>Loading results...</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="table-empty">
        <p>No results found</p>
      </div>
    );
  }

  return (
    <div className="dynamic-data-table">
      <table>
        <thead>
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th 
                  key={header.id}
                  style={{ width: header.getSize() }}
                  className={header.column.getIsFiltered() ? 'has-filter' : ''}
                >
                  <div className="header-content">
                    <span className="header-label">
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </span>
                    {header.column.getCanFilter() && header.column.id !== 'expander' && (
                      <ColumnFilterMenu 
                        column={header.column} 
                        columnConfig={columnConfig.find((col: any) => col.key === header.column.id)}
                      />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <React.Fragment key={row.id}>
              <tr 
                onClick={() => onRowClick && onRowClick(row.original)}
                className={onRowClick ? 'clickable' : ''}
              >
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
              {row.getIsExpanded() && expandedRowContent && (
                <tr>
                  <td colSpan={columns.length}>
                    <div className="expanded-content">
                      {expandedRowContent(row.original)}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DynamicDataTable;