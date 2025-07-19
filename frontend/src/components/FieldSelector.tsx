import React, { useState, useRef, useEffect } from 'react';
import { FieldMetadata } from './QueryBuilder';
import './FieldSelector.css';

interface FieldSelectorProps {
  value: string;
  onChange: (field: string) => void;
  availableFields: FieldMetadata[];
  placeholder?: string;
  className?: string;
}

const FieldSelector: React.FC<FieldSelectorProps> = ({
  value,
  onChange,
  availableFields,
  placeholder = "Select field...",
  className = ""
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Group fields by source category
  const groupedFields = availableFields.reduce((groups, field) => {
    // If field has sourceCategories, add it to each source category
    if (field.sourceCategories && field.sourceCategories.length > 0) {
      field.sourceCategories.forEach(sourceCategory => {
        if (!groups[sourceCategory]) {
          groups[sourceCategory] = [];
        }
        groups[sourceCategory].push(field);
      });
    } else {
      // Fallback to 'Common' for fields without source categories
      if (!groups['Common']) {
        groups['Common'] = [];
      }
      groups['Common'].push(field);
    }
    return groups;
  }, {} as Record<string, FieldMetadata[]>);

  // Filter fields based on search term
  const filteredGroups = Object.entries(groupedFields).reduce((filtered, [category, fields]) => {
    const matchingFields = fields.filter(field =>
      field.label?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      field.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      field.description?.toLowerCase().includes(searchTerm.toLowerCase())
    );
    
    if (matchingFields.length > 0) {
      filtered[category] = matchingFields;
    }
    
    return filtered;
  }, {} as Record<string, FieldMetadata[]>);

  // Sort categories in a logical order
  const categoryOrder = ['Common', 'publications', 'trials', 'community', 'faers'];
  const sortedCategories = Object.keys(filteredGroups).sort((a, b) => {
    const aIndex = categoryOrder.indexOf(a);
    const bIndex = categoryOrder.indexOf(b);
    
    // If both are in the order array, sort by their position
    if (aIndex !== -1 && bIndex !== -1) {
      return aIndex - bIndex;
    }
    // If only one is in the order array, it comes first
    if (aIndex !== -1) return -1;
    if (bIndex !== -1) return 1;
    // Otherwise, sort alphabetically
    return a.localeCompare(b);
  });

  // Flatten filtered fields for keyboard navigation
  const allFilteredFields = Object.values(filteredGroups).flat();

  // Get the current field metadata
  const currentField = availableFields.find(f => f.name === value);
  const displayValue = currentField?.label || value || '';

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchTerm('');
        setHighlightedIndex(-1);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(prev => 
          prev < allFilteredFields.length - 1 ? prev + 1 : prev
        );
        break;
      
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(prev => prev > 0 ? prev - 1 : prev);
        break;
      
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && allFilteredFields[highlightedIndex]) {
          selectField(allFilteredFields[highlightedIndex]);
        }
        break;
      
      case 'Escape':
        setIsOpen(false);
        setSearchTerm('');
        setHighlightedIndex(-1);
        inputRef.current?.blur();
        break;
    }
  };

  const selectField = (field: FieldMetadata) => {
    onChange(field.name);
    setIsOpen(false);
    setSearchTerm('');
    setHighlightedIndex(-1);
  };

  const getFieldTypeIcon = (type: string) => {
    switch (type) {
      case 'string': return '📝';
      case 'number': return '🔢';
      case 'date': return '📅';
      case 'boolean': return '☑️';
      case 'array': return '📋';
      case 'object': return '🗂️';
      default: return '📄';
    }
  };

  const getFieldTypeColor = (type: string) => {
    switch (type) {
      case 'string': return '#1a73e8';
      case 'number': return '#ea4335';
      case 'date': return '#34a853';
      case 'boolean': return '#9333ea';
      case 'array': return '#ff9800';
      case 'object': return '#607d8b';
      default: return '#5f6368';
    }
  };

  return (
    <div className={`field-selector ${className}`} ref={dropdownRef}>
      <div 
        className={`field-selector-input ${isOpen ? 'open' : ''} ${value ? 'has-value' : ''}`}
        onClick={() => setIsOpen(true)}
      >
        {value ? (
          <div className="selected-field">
            <span 
              className="field-type-icon"
              style={{ color: getFieldTypeColor(currentField?.type || 'string') }}
            >
              {getFieldTypeIcon(currentField?.type || 'string')}
            </span>
            <span className="field-label">{displayValue}</span>
            <span className="field-type-badge" style={{ 
              backgroundColor: getFieldTypeColor(currentField?.type || 'string') 
            }}>
              {currentField?.type || 'unknown'}
            </span>
          </div>
        ) : (
          <span className="placeholder">{placeholder}</span>
        )}
        
        <svg 
          className={`dropdown-arrow ${isOpen ? 'open' : ''}`}
          width="16" 
          height="16" 
          viewBox="0 0 16 16"
        >
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="2" fill="none"/>
        </svg>
      </div>

      {isOpen && (
        <div className="field-selector-dropdown">
          <div className="search-container">
            <input
              ref={inputRef}
              type="text"
              className="field-search"
              placeholder="Search fields..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setHighlightedIndex(-1);
              }}
              onKeyDown={handleKeyDown}
              autoFocus
            />
            <svg className="search-icon" width="16" height="16" viewBox="0 0 16 16">
              <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
            </svg>
          </div>

          <div className="fields-container">
            {Object.keys(filteredGroups).length === 0 ? (
              <div className="no-results">
                <p>No fields found matching "{searchTerm}"</p>
              </div>
            ) : (
              sortedCategories.map(category => {
                const fields = filteredGroups[category];
                return (
                <div key={category} className="field-category">
                  <div className="category-header">
                    <h4>{
                      category === 'publications' ? 'Publications' :
                      category === 'trials' ? 'Clinical Trials' :
                      category === 'community' ? 'Community' :
                      category === 'faers' ? 'Adverse Events' :
                      category
                    }</h4>
                  </div>
                  
                  <div className="field-list">
                    {fields.map((field, index) => {
                      const globalIndex = allFilteredFields.findIndex(f => f.name === field.name);
                      const isHighlighted = globalIndex === highlightedIndex;
                      
                      return (
                        <div
                          key={field.name}
                          className={`field-option ${isHighlighted ? 'highlighted' : ''} ${value === field.name ? 'selected' : ''}`}
                          onClick={() => selectField(field)}
                          onMouseEnter={() => setHighlightedIndex(globalIndex)}
                        >
                          <div className="field-option-main">
                            <span 
                              className="field-type-icon"
                              style={{ color: getFieldTypeColor(field.type) }}
                            >
                              {getFieldTypeIcon(field.type)}
                            </span>
                            <div className="field-info">
                              <span className="field-name">{field.label || field.name}</span>
                              {field.description && (
                                <span className="field-description">{field.description}</span>
                              )}
                            </div>
                          </div>
                          
                          <div className="field-option-meta">
                            <span 
                              className="field-type-badge"
                              style={{ backgroundColor: getFieldTypeColor(field.type) }}
                            >
                              {field.type}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
              })
            )}
          </div>

        </div>
      )}
    </div>
  );
};

export default FieldSelector;