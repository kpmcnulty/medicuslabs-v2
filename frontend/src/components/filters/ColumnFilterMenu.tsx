import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Column } from '@tanstack/react-table';
import './ColumnFilterMenu.css';

// Filter condition interface
export interface FilterCondition {
  operator: string;
  value: any;
}

export interface AdvancedFilterValue {
  conditions: FilterCondition[];
  joinOperator: 'AND' | 'OR';
}

interface ColumnFilterMenuProps {
  column: Column<any, unknown>;
  columnConfig?: any;
}

// Text filter operators with user-friendly labels
const TEXT_OPERATORS = [
  { value: 'contains', label: 'Contains', icon: '⊃' },
  { value: 'equals', label: 'Equals', icon: '=' },
  { value: 'notEqual', label: 'Not equal', icon: '≠' },
  { value: 'startsWith', label: 'Starts with', icon: '⊏' },
  { value: 'endsWith', label: 'Ends with', icon: '⊐' },
  { value: 'notContains', label: 'Does not contain', icon: '⊅' },
];

// Number filter operators
const NUMBER_OPERATORS = [
  { value: 'equals', label: 'Equals', icon: '=' },
  { value: 'notEqual', label: 'Not equal', icon: '≠' },
  { value: 'greaterThan', label: 'Greater than', icon: '>' },
  { value: 'greaterThanOrEqual', label: 'Greater than or equal', icon: '≥' },
  { value: 'lessThan', label: 'Less than', icon: '<' },
  { value: 'lessThanOrEqual', label: 'Less than or equal', icon: '≤' },
  { value: 'inRange', label: 'In range', icon: '↔' },
];

// Date filter operators
const DATE_OPERATORS = [
  { value: 'equals', label: 'On', icon: '=' },
  { value: 'before', label: 'Before', icon: '<' },
  { value: 'after', label: 'After', icon: '>' },
  { value: 'between', label: 'Between', icon: '↔' },
  { value: 'notEqual', label: 'Not on', icon: '≠' },
];

// Common filter presets
const TEXT_PRESETS = [
  { label: 'Empty', operator: 'blank', value: '' },
  { label: 'Not empty', operator: 'notBlank', value: '' },
];

const NUMBER_PRESETS = [
  { label: 'Empty', operator: 'blank', value: '' },
  { label: 'Not empty', operator: 'notBlank', value: '' },
  { label: 'Positive', operator: 'greaterThan', value: 0 },
  { label: 'Negative', operator: 'lessThan', value: 0 },
];

export const ColumnFilterMenu: React.FC<ColumnFilterMenuProps> = ({ column, columnConfig }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [localFilter, setLocalFilter] = useState<AdvancedFilterValue>({
    conditions: [{ operator: 'contains', value: '' }],
    joinOperator: 'AND',
  });
  const [activeCondition, setActiveCondition] = useState(0);
  const [menuPosition, setMenuPosition] = useState<'left' | 'right' | 'center'>('center');
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Get operators based on column type
  const getOperators = () => {
    const type = columnConfig?.type || 'text';
    switch (type) {
      case 'number':
        return NUMBER_OPERATORS;
      case 'date':
        return DATE_OPERATORS;
      default:
        return TEXT_OPERATORS;
    }
  };

  const getPresets = () => {
    const type = columnConfig?.type || 'text';
    switch (type) {
      case 'number':
        return NUMBER_PRESETS;
      default:
        return TEXT_PRESETS;
    }
  };

  const operators = getOperators();
  const presets = getPresets();

  // Load existing filter value
  useEffect(() => {
    const existingValue = column.getFilterValue() as AdvancedFilterValue;
    if (existingValue && existingValue.conditions) {
      setLocalFilter(existingValue);
    }
  }, [column]);

  // Calculate menu position to prevent cutoff
  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const positionMenu = () => {
        if (!buttonRef.current || !menuRef.current) return;
        
        const buttonRect = buttonRef.current.getBoundingClientRect();
        const menuWidth = 320; // min-width of menu
        const menuHeight = menuRef.current.offsetHeight || 400; // estimated height
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        const scrollY = window.scrollY;
        
        // Calculate available space
        const spaceOnRight = windowWidth - buttonRect.right;
        const spaceOnLeft = buttonRect.left;
        const spaceBelow = windowHeight - buttonRect.bottom;
        
        // Determine horizontal position
        let horizontalPos = 'center';
        let left = buttonRect.left + buttonRect.width / 2;
        
        if (spaceOnRight < menuWidth / 2 && spaceOnLeft > spaceOnRight) {
          horizontalPos = 'right';
          left = buttonRect.right;
        } else if (buttonRect.left < menuWidth / 2) {
          horizontalPos = 'left';
          left = buttonRect.left;
        }
        
        // Determine vertical position
        let top = buttonRect.bottom + scrollY + 8;
        
        // If not enough space below and more space above, position above
        if (spaceBelow < menuHeight && buttonRect.top > menuHeight) {
          top = buttonRect.top + scrollY - menuHeight - 8;
        }
        
        // Apply position
        if (menuRef.current) {
          menuRef.current.style.top = `${top}px`;
          menuRef.current.style.left = `${left}px`;
        }
        
        setMenuPosition(horizontalPos as 'left' | 'right' | 'center');
      };
      
      // Position immediately and on scroll/resize
      positionMenu();
      window.addEventListener('scroll', positionMenu);
      window.addEventListener('resize', positionMenu);
      
      return () => {
        window.removeEventListener('scroll', positionMenu);
        window.removeEventListener('resize', positionMenu);
      };
    }
  }, [isOpen]);

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        menuRef.current && 
        !menuRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Apply filter
  const applyFilter = useCallback(() => {
    const hasValidCondition = localFilter.conditions.some(c => 
      (c.value !== '' && c.value !== null && c.value !== undefined) ||
      ['blank', 'notBlank'].includes(c.operator)
    );
    column.setFilterValue(hasValidCondition ? localFilter : undefined);
    setIsOpen(false);
  }, [column, localFilter]);

  // Clear filter
  const clearFilter = () => {
    const newFilter = {
      conditions: [{ operator: operators[0].value, value: '' }],
      joinOperator: 'AND' as const,
    };
    setLocalFilter(newFilter);
    column.setFilterValue(undefined);
  };

  // Update condition
  const updateCondition = (index: number, field: 'operator' | 'value', value: any) => {
    const newFilter = { ...localFilter };
    newFilter.conditions[index] = {
      ...newFilter.conditions[index],
      [field]: value,
    };
    setLocalFilter(newFilter);
  };

  // Add condition
  const addCondition = () => {
    const newFilter = {
      ...localFilter,
      conditions: [...localFilter.conditions, { operator: operators[0].value, value: '' }],
    };
    setLocalFilter(newFilter);
    setActiveCondition(newFilter.conditions.length - 1);
  };

  // Remove condition
  const removeCondition = (index: number) => {
    if (localFilter.conditions.length > 1) {
      const newConditions = localFilter.conditions.filter((_, i) => i !== index);
      setLocalFilter({ ...localFilter, conditions: newConditions });
      if (activeCondition >= newConditions.length) {
        setActiveCondition(newConditions.length - 1);
      }
    }
  };

  // Apply preset
  const applyPreset = (preset: any) => {
    const newFilter = {
      conditions: [{ operator: preset.operator, value: preset.value }],
      joinOperator: 'AND' as const,
    };
    setLocalFilter(newFilter);
    column.setFilterValue(newFilter);
    setIsOpen(false);
  };

  // Toggle join operator
  const toggleJoinOperator = () => {
    setLocalFilter({
      ...localFilter,
      joinOperator: localFilter.joinOperator === 'AND' ? 'OR' : 'AND',
    });
  };

  // Check if filter is active
  const isFilterActive = column.getIsFiltered();

  // Render value input
  const renderValueInput = (condition: FilterCondition, index: number) => {
    const type = columnConfig?.type || 'text';
    
    if (['blank', 'notBlank'].includes(condition.operator)) {
      return <span className="no-value-needed">No value needed</span>;
    }

    if (condition.operator === 'inRange' || condition.operator === 'between') {
      return (
        <div className="range-inputs">
          <input
            type={type === 'date' ? 'date' : 'number'}
            value={condition.value?.[0] || ''}
            onChange={(e) => updateCondition(index, 'value', [e.target.value, condition.value?.[1] || ''])}
            placeholder={type === 'date' ? '' : 'From'}
            className="filter-value-input"
          />
          <span className="range-separator">to</span>
          <input
            type={type === 'date' ? 'date' : 'number'}
            value={condition.value?.[1] || ''}
            onChange={(e) => updateCondition(index, 'value', [condition.value?.[0] || '', e.target.value])}
            placeholder={type === 'date' ? '' : 'To'}
            className="filter-value-input"
          />
        </div>
      );
    }

    return (
      <input
        type={type === 'number' ? 'number' : type === 'date' ? 'date' : 'text'}
        value={condition.value || ''}
        onChange={(e) => updateCondition(index, 'value', e.target.value)}
        placeholder="Enter value..."
        className="filter-value-input"
        autoFocus={index === activeCondition}
      />
    );
  };

  return (
    <div className="column-filter-menu-container">
      <button
        ref={buttonRef}
        className={`filter-menu-button ${isFilterActive ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        title={isFilterActive ? 'Filter active' : 'Open filter menu'}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/>
        </svg>
      </button>

      {isOpen && createPortal(
        <div 
          ref={menuRef} 
          className={`filter-menu-dropdown position-${menuPosition}`}
          style={{ zIndex: 9999, position: 'absolute' }}
        >
          <div className="filter-menu-header">
            <h4>Filter: {columnConfig?.label || column.id}</h4>
            <button className="close-button" onClick={() => setIsOpen(false)}>×</button>
          </div>

          {/* Quick presets */}
          {presets.length > 0 && (
            <div className="filter-presets">
              <div className="preset-label">Quick filters:</div>
              <div className="preset-buttons">
                {presets.map((preset, idx) => (
                  <button
                    key={idx}
                    className="preset-button"
                    onClick={() => applyPreset(preset)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Filter conditions */}
          <div className="filter-conditions">
            {localFilter.conditions.map((condition, index) => (
              <div key={index} className={`filter-condition-item ${index === activeCondition ? 'active' : ''}`}>
                {index > 0 && (
                  <button
                    className="join-operator-button"
                    onClick={toggleJoinOperator}
                  >
                    {localFilter.joinOperator}
                  </button>
                )}
                
                <div className="condition-content" onClick={() => setActiveCondition(index)}>
                  <select
                    value={condition.operator}
                    onChange={(e) => updateCondition(index, 'operator', e.target.value)}
                    className="operator-select"
                  >
                    {operators.map(op => (
                      <option key={op.value} value={op.value}>
                        {op.icon} {op.label}
                      </option>
                    ))}
                  </select>

                  {renderValueInput(condition, index)}

                  {localFilter.conditions.length > 1 && (
                    <button
                      className="remove-condition-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeCondition(index);
                      }}
                      title="Remove condition"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Add condition button */}
          <button className="add-condition-button" onClick={addCondition}>
            + Add condition
          </button>

          {/* Action buttons */}
          <div className="filter-menu-actions">
            <button className="clear-button" onClick={clearFilter}>
              Clear
            </button>
            <button className="cancel-button" onClick={() => setIsOpen(false)}>
              Cancel
            </button>
            <button className="apply-button" onClick={applyFilter}>
              Apply
            </button>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};