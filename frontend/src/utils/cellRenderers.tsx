import React from 'react';
import { format } from 'date-fns';

export const cellRenderers: Record<string, (value: any, col?: any) => React.ReactNode> = {
  date: (value) => {
    if (!value) return null;
    try {
      return format(new Date(value), 'MMM d, yyyy');
    } catch {
      return value;
    }
  },
  
  link: (value) => {
    if (!value || typeof value !== 'string') return value;
    return (
      <a href={value} target="_blank" rel="noopener noreferrer" className="cell-link">
        {value.length > 50 ? value.substring(0, 50) + '...' : value}
      </a>
    );
  },
  
  badge: (value) => (
    <span className={`badge badge-${String(value).toLowerCase()}`}>{value}</span>
  ),
  
  list: (value, col) => {
    if (!Array.isArray(value)) return value;
    const maxItems = col?.maxItems || 3;
    const items = value.slice(0, maxItems);
    const remaining = value.length - maxItems;
    
    // Helper to render individual list items
    const renderItem = (item: any) => {
      if (item === null || item === undefined) {
        return '-';
      }
      
      // Handle objects (like medication data)
      if (typeof item === 'object' && !Array.isArray(item)) {
        // For medication/drug objects, show the name or a formatted string
        if (item.name) {
          // This handles drug objects with {name, dose, route, etc.}
          let display = item.name;
          if (item.dose) display += ` (${item.dose})`;
          return display;
        }
        // For other objects, try to find a display field or stringify
        return item.title || item.label || item.value || JSON.stringify(item);
      }
      
      // Handle nested arrays by joining
      if (Array.isArray(item)) {
        return item.join(', ');
      }
      
      // For primitive values, just convert to string
      return String(item);
    };
    
    return (
      <div className="list-value">
        {items.map((item: any, idx: number) => (
          <span key={idx} className="list-item">{renderItem(item)}</span>
        ))}
        {remaining > 0 && <span className="list-more">+{remaining} more</span>}
      </div>
    );
  },
  
  number: (value) => {
    if (typeof value !== 'number') return value;
    return value.toLocaleString();
  },
  
  boolean: (value) => {
    if (typeof value !== 'boolean') return value;
    return value ? '✓' : '✗';
  },
  
  json: (value) => {
    if (!value || typeof value !== 'object') return value;
    const str = JSON.stringify(value, null, 2);
    return (
      <pre className="json-value" title={str}>
        {str.length > 100 ? str.substring(0, 100) + '...' : str}
      </pre>
    );
  },
};

export const renderCellValue = (value: any, col: any): React.ReactNode => {
  if (value === null || value === undefined) {
    return <span className="null-value">-</span>;
  }

  const renderType = col.render || col.type;
  const renderer = cellRenderers[renderType];
  if (renderer) {
    return renderer(value, col) || value;
  }

  // Default: truncate long strings
  const strValue = String(value);
  if (strValue.length > 100) {
    return (
      <span className="truncated" title={strValue}>
        {strValue.substring(0, 100)}...
      </span>
    );
  }
  return strValue;
};