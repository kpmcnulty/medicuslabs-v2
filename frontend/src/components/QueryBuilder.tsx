import React, { useState, useCallback, useEffect } from 'react';
import FieldSelector from './FieldSelector';
import ValueInput from './ValueInput';
import QueryPreview from './QueryPreview';
import useFieldMetadata from '../hooks/useFieldMetadata';
import './QueryBuilder.css';

// Core types for query building
export interface QueryCondition {
  field: string;
  operator: string;
  value: any;
  id: string;
}

export interface QueryGroup {
  id: string;
  operator: 'AND' | 'OR';
  conditions: QueryCondition[];
  groups: QueryGroup[];
}

export interface QueryBuilderProps {
  value?: QueryGroup;
  onChange?: (query: QueryGroup) => void;
  onValidChange?: (isValid: boolean) => void;
  availableFields?: FieldMetadata[];
  sourceCategory?: string;
  source?: string;
  loading?: boolean;
  className?: string;
}

export interface FieldMetadata {
  name: string;
  type: 'string' | 'number' | 'date' | 'boolean' | 'array' | 'object';
  label?: string;
  category?: string;
  operators?: string[];
  sampleValues?: any[];
  description?: string;
  sourceCategories?: string[];
}

// MongoDB-style operators with user-friendly labels
export const OPERATORS = {
  // String operators
  $eq: { label: 'Equals', icon: '=', types: ['string', 'number', 'date', 'boolean'] },
  $ne: { label: 'Not equals', icon: '≠', types: ['string', 'number', 'date', 'boolean'] },
  $contains: { label: 'Contains', icon: '⊃', types: ['string', 'array'] },
  $startsWith: { label: 'Starts with', icon: '⊏', types: ['string'] },
  $endsWith: { label: 'Ends with', icon: '⊐', types: ['string'] },
  $regex: { label: 'Matches pattern', icon: '~', types: ['string'] },
  
  // Comparison operators
  $gt: { label: 'Greater than', icon: '>', types: ['number', 'date'] },
  $gte: { label: 'Greater than or equal', icon: '≥', types: ['number', 'date'] },
  $lt: { label: 'Less than', icon: '<', types: ['number', 'date'] },
  $lte: { label: 'Less than or equal', icon: '≤', types: ['number', 'date'] },
  
  // Array/Set operators
  $in: { label: 'In list', icon: '∈', types: ['string', 'number', 'array'] },
  $nin: { label: 'Not in list', icon: '∉', types: ['string', 'number', 'array'] },
  $all: { label: 'Contains all', icon: '⊇', types: ['array'] },
  
  // Existence operators
  $exists: { label: 'Exists', icon: '∃', types: ['string', 'number', 'date', 'boolean', 'array', 'object'] },
  
  // Date range operators
  $between: { label: 'Between', icon: '↔', types: ['number', 'date'] },
};

// Helper to generate unique IDs
const generateId = () => Math.random().toString(36).substr(2, 9);

// Get smart default operator for a field
const getDefaultOperator = (fieldName: string, fieldType: string): string => {
  const field = fieldName.toLowerCase();
  
  // Text fields that should default to contains
  if (field === '_fulltext' || field.includes('summary') || field.includes('content') || 
      field.includes('description') || field.includes('text') || field.includes('body')) {
    return '$contains';
  }
  
  // ID fields should use equals
  if (field.includes('id') || field === 'pmid' || field === 'nct' || field === 'doi') {
    return '$eq';
  }
  
  // Date fields often use greater than
  if (fieldType === 'date' && (field.includes('updated') || field.includes('created'))) {
    return '$gte';
  }
  
  // Arrays default to contains
  if (fieldType === 'array') {
    return '$contains';
  }
  
  // Default fallback
  return '$eq';
};

// Helper to create empty condition
const createEmptyCondition = (field?: string, fieldType?: string): QueryCondition => ({
  id: generateId(),
  field: field || '',
  operator: field && fieldType ? getDefaultOperator(field, fieldType) : '$eq',
  value: ''
});

// Helper to create empty group
const createEmptyGroup = (): QueryGroup => ({
  id: generateId(),
  operator: 'AND',
  conditions: [createEmptyCondition()],
  groups: []
});

// Get available operators for a field type
const getOperatorsForType = (type: string): string[] => {
  return Object.entries(OPERATORS)
    .filter(([_, meta]) => meta.types.includes(type))
    .map(([op]) => op);
};

const QueryBuilder: React.FC<QueryBuilderProps> = ({
  value,
  onChange,
  onValidChange,
  availableFields: propFields,
  sourceCategory,
  source,
  loading: propLoading = false,
  className = ''
}) => {
  const [query, setQuery] = useState<QueryGroup>(
    value || createEmptyGroup()
  );
  
  const [isValid, setIsValid] = useState(false);

  // Fetch field metadata if not provided
  const { 
    fields: fetchedFields, 
    loading: fieldsLoading, 
    error: fieldsError 
  } = useFieldMetadata({ 
    sourceCategory, 
    source, 
    autoFetch: !propFields 
  });

  // Use provided fields or fetched fields
  const availableFields = propFields || fetchedFields;
  const loading = propLoading || fieldsLoading;

  // Update query when value prop changes
  useEffect(() => {
    if (value) {
      setQuery(value);
    }
  }, [value]);

  // Validate query and notify parent
  useEffect(() => {
    const validateQuery = (group: QueryGroup): boolean => {
      // Check if group has valid conditions
      const hasValidConditions = group.conditions.some(condition => 
        condition.field && 
        condition.operator && 
        ((condition.value !== '' && condition.value != null) ||
        condition.operator === '$exists')
      );
      
      // Check nested groups
      const hasValidGroups = group.groups.some(validateQuery);
      
      return hasValidConditions || hasValidGroups;
    };

    const valid = validateQuery(query);
    setIsValid(valid);
    onValidChange?.(valid);
  }, [query, onValidChange]);

  // Notify parent of changes
  const handleQueryChange = useCallback((newQuery: QueryGroup) => {
    setQuery(newQuery);
    onChange?.(newQuery);
  }, [onChange]);

  // Update a condition
  const updateCondition = useCallback((
    groupId: string, 
    conditionId: string, 
    updates: Partial<QueryCondition>
  ) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return {
          ...group,
          conditions: group.conditions.map(condition =>
            condition.id === conditionId
              ? { ...condition, ...updates }
              : condition
          )
        };
      }
      
      return {
        ...group,
        groups: group.groups.map(updateGroup)
      };
    };

    handleQueryChange(updateGroup(query));
  }, [query, handleQueryChange]);

  // Add condition to group
  const addCondition = useCallback((groupId: string, field?: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return {
          ...group,
          conditions: [...group.conditions, createEmptyCondition(field, availableFields.find(f => f.name === field)?.type)]
        };
      }
      
      return {
        ...group,
        groups: group.groups.map(updateGroup)
      };
    };

    handleQueryChange(updateGroup(query));
  }, [query, handleQueryChange]);

  // Remove condition from group
  const removeCondition = useCallback((groupId: string, conditionId: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        const newConditions = group.conditions.filter(c => c.id !== conditionId);
        // Ensure at least one condition exists
        return {
          ...group,
          conditions: newConditions.length > 0 ? newConditions : [createEmptyCondition()]
        };
      }
      
      return {
        ...group,
        groups: group.groups.map(updateGroup)
      };
    };

    handleQueryChange(updateGroup(query));
  }, [query, handleQueryChange]);

  // Add nested group
  const addGroup = useCallback((parentGroupId: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === parentGroupId) {
        return {
          ...group,
          groups: [...group.groups, createEmptyGroup()]
        };
      }
      
      return {
        ...group,
        groups: group.groups.map(updateGroup)
      };
    };

    handleQueryChange(updateGroup(query));
  }, [query, handleQueryChange]);

  // Remove nested group
  const removeGroup = useCallback((parentGroupId: string, groupId: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === parentGroupId) {
        return {
          ...group,
          groups: group.groups.filter(g => g.id !== groupId)
        };
      }
      
      return {
        ...group,
        groups: group.groups.map(updateGroup)
      };
    };

    handleQueryChange(updateGroup(query));
  }, [query, handleQueryChange]);

  // Toggle group operator (AND/OR)
  const toggleGroupOperator = useCallback((groupId: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return {
          ...group,
          operator: group.operator === 'AND' ? 'OR' : 'AND'
        };
      }
      
      return {
        ...group,
        groups: group.groups.map(updateGroup)
      };
    };

    handleQueryChange(updateGroup(query));
  }, [query, handleQueryChange]);

  // Clear all conditions and groups
  const clearQuery = useCallback(() => {
    handleQueryChange(createEmptyGroup());
  }, [handleQueryChange]);

  if (loading) {
    return (
      <div className={`query-builder loading ${className}`}>
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading field metadata...</p>
        </div>
      </div>
    );
  }

  if (fieldsError && !propFields) {
    return (
      <div className={`query-builder error ${className}`}>
        <div className="error-state">
          <h3>Failed to Load Field Metadata</h3>
          <p>{fieldsError}</p>
          <button 
            className="retry-button"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`query-builder ${className}`}>
      <div className="query-builder-header">
        <h3>Advanced Query Builder</h3>
        <div className="header-actions">
          <span className={`validation-indicator ${isValid ? 'valid' : 'invalid'}`}>
            {isValid ? '✓ Valid query' : '⚠ Incomplete query'}
          </span>
          <button 
            className="clear-button"
            onClick={clearQuery}
            title="Clear all conditions"
          >
            Clear All
          </button>
        </div>
      </div>

      <div className="query-builder-content">
        <QueryBuilderGroup
          group={query}
          availableFields={availableFields}
          onUpdateCondition={updateCondition}
          onAddCondition={addCondition}
          onRemoveCondition={removeCondition}
          onAddGroup={addGroup}
          onRemoveGroup={removeGroup}
          onToggleOperator={toggleGroupOperator}
          isRoot={true}
        />
      </div>

      <QueryPreview 
        query={query} 
        isValid={isValid}
        className="query-builder-preview"
      />
    </div>
  );
};

// QueryBuilderGroup component (this will be implemented next)
interface QueryBuilderGroupProps {
  group: QueryGroup;
  availableFields: FieldMetadata[];
  onUpdateCondition: (groupId: string, conditionId: string, updates: Partial<QueryCondition>) => void;
  onAddCondition: (groupId: string, field?: string) => void;
  onRemoveCondition: (groupId: string, conditionId: string) => void;
  onAddGroup: (parentGroupId: string) => void;
  onRemoveGroup: (parentGroupId: string, groupId: string) => void;
  onToggleOperator: (groupId: string) => void;
  isRoot?: boolean;
}

const QueryBuilderGroup: React.FC<QueryBuilderGroupProps> = ({
  group,
  availableFields,
  onUpdateCondition,
  onAddCondition,
  onRemoveCondition,
  onAddGroup,
  onRemoveGroup,
  onToggleOperator,
  isRoot = false
}) => {
  const hasMultipleItems = group.conditions.length + group.groups.length > 1;

  return (
    <div className={`query-group ${isRoot ? 'root-group' : ''}`}>
      {hasMultipleItems && (
        <div className="group-operator">
          <button
            className={`operator-toggle ${group.operator.toLowerCase()}`}
            onClick={() => onToggleOperator(group.id)}
          >
            {group.operator}
          </button>
          <span className="operator-description">
            {group.operator === 'AND' ? 'All conditions must match' : 'Any condition can match'}
          </span>
        </div>
      )}

      <div className="group-content">
        {/* Render conditions */}
        {group.conditions.map((condition, index) => (
          <div key={condition.id} className="condition-wrapper">
            {index > 0 && hasMultipleItems && (
              <div className="condition-operator">
                <span className={`operator-badge ${group.operator.toLowerCase()}`}>
                  {group.operator}
                </span>
              </div>
            )}
            <QueryBuilderRule
              condition={condition}
              availableFields={availableFields}
              onUpdate={(updates) => onUpdateCondition(group.id, condition.id, updates)}
              onRemove={() => onRemoveCondition(group.id, condition.id)}
              canRemove={group.conditions.length > 1 || group.groups.length > 0}
            />
          </div>
        ))}

        {/* Render nested groups */}
        {group.groups.map((nestedGroup, index) => (
          <div key={nestedGroup.id} className="nested-group-wrapper">
            {(group.conditions.length > 0 || index > 0) && hasMultipleItems && (
              <div className="condition-operator">
                <span className={`operator-badge ${group.operator.toLowerCase()}`}>
                  {group.operator}
                </span>
              </div>
            )}
            <div className="nested-group">
              <div className="nested-group-header">
                <span className="group-label">Group</span>
                <button
                  className="remove-group-button"
                  onClick={() => onRemoveGroup(group.id, nestedGroup.id)}
                  title="Remove group"
                >
                  ×
                </button>
              </div>
              <QueryBuilderGroup
                group={nestedGroup}
                availableFields={availableFields}
                onUpdateCondition={onUpdateCondition}
                onAddCondition={onAddCondition}
                onRemoveCondition={onRemoveCondition}
                onAddGroup={onAddGroup}
                onRemoveGroup={onRemoveGroup}
                onToggleOperator={onToggleOperator}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="group-actions">
        <button
          className="add-condition-button"
          onClick={() => onAddCondition(group.id)}
        >
          + Add Condition
        </button>
        <button
          className="add-group-button"
          onClick={() => onAddGroup(group.id)}
        >
          + Add Group
        </button>
      </div>
    </div>
  );
};

// QueryBuilderRule component
interface QueryBuilderRuleProps {
  condition: QueryCondition;
  availableFields: FieldMetadata[];
  onUpdate: (updates: Partial<QueryCondition>) => void;
  onRemove: () => void;
  canRemove: boolean;
}

const QueryBuilderRule: React.FC<QueryBuilderRuleProps> = ({
  condition,
  availableFields,
  onUpdate,
  onRemove,
  canRemove
}) => {
  const selectedField = availableFields.find(f => f.name === condition.field);
  const availableOperators = selectedField 
    ? getOperatorsForType(selectedField.type)
    : Object.keys(OPERATORS);

  // Update operator if current one is not valid for selected field
  useEffect(() => {
    if (selectedField && !availableOperators.includes(condition.operator)) {
      onUpdate({ operator: availableOperators[0] || '$eq' });
    }
  }, [selectedField, availableOperators, condition.operator, onUpdate]);

  const handleFieldChange = (fieldName: string) => {
    const field = availableFields.find(f => f.name === fieldName);
    const validOperators = field ? getOperatorsForType(field.type) : ['$eq'];
    
    // Get smart default operator for this field
    const defaultOp = field ? getDefaultOperator(fieldName, field.type) : '$eq';
    
    // Use default operator if it's valid, otherwise fall back to first valid operator
    const newOperator = validOperators.includes(defaultOp) ? defaultOp : validOperators[0];
    
    onUpdate({ 
      field: fieldName,
      operator: newOperator,
      value: '' // Reset value when field changes
    });
  };

  return (
    <div className="query-rule">
      <div className="rule-content">
        <div className="rule-field">
          <FieldSelector
            value={condition.field}
            onChange={handleFieldChange}
            availableFields={availableFields}
            placeholder="Select field..."
          />
        </div>
        
        <div className="rule-operator">
          <select
            value={condition.operator}
            onChange={(e) => onUpdate({ operator: e.target.value, value: '' })}
            className="operator-select"
            disabled={!condition.field}
          >
            {!condition.field && (
              <option value="">Select operator...</option>
            )}
            {availableOperators.map(op => (
              <option key={op} value={op}>
                {OPERATORS[op as keyof typeof OPERATORS]?.icon} {OPERATORS[op as keyof typeof OPERATORS]?.label}
              </option>
            ))}
          </select>
        </div>
        
        <div className="rule-value">
          <ValueInput
            value={condition.value}
            onChange={(value) => onUpdate({ value })}
            field={selectedField}
            operator={condition.operator}
            placeholder="Enter value..."
          />
        </div>
        
        {canRemove && (
          <button
            className="remove-condition-button"
            onClick={onRemove}
            title="Remove condition"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
};

export default QueryBuilder;