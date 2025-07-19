import React, { useState } from 'react';
import { QueryGroup, OPERATORS } from './QueryBuilder';
import './QueryPreview.css';

interface QueryPreviewProps {
  query: QueryGroup;
  isValid: boolean;
  className?: string;
}

interface GeneratedQuery {
  metadata?: Record<string, any>;
  columnFilters?: any[];
  humanReadable: string;
  mongoQuery: Record<string, any>;
  fieldCount: number;
  conditionCount: number;
}

const QueryPreview: React.FC<QueryPreviewProps> = ({ 
  query, 
  isValid, 
  className = "" 
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [activeTab, setActiveTab] = useState<'human' | 'json' | 'mongo'>('human');

  // Convert QueryBuilder format to backend API format
  const generateQuery = (group: QueryGroup): GeneratedQuery => {
    const metadata: Record<string, any> = {};
    const columnFilters: any[] = [];
    let fieldCount = 0;
    let conditionCount = 0;

    const processGroup = (grp: QueryGroup, level: number = 0): string[] => {
      const groupConditions: string[] = [];
      
      // Process conditions
      grp.conditions.forEach(condition => {
        if (!condition.field || !condition.operator) return;
        
        conditionCount++;
        const fieldName = condition.field;
        
        // Track unique fields
        if (!fieldCount || !Object.keys(metadata).includes(fieldName)) {
          fieldCount++;
        }

        // Generate human readable condition
        const operatorMeta = OPERATORS[condition.operator as keyof typeof OPERATORS];
        const operatorLabel = operatorMeta?.label || condition.operator;
        const fieldLabel = condition.field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        let valueDisplay = '';
        if (condition.operator === '$exists') {
          valueDisplay = condition.value ? 'exists' : 'does not exist';
        } else if (Array.isArray(condition.value)) {
          if (condition.operator === '$between') {
            valueDisplay = `${condition.value[0]} and ${condition.value[1]}`;
          } else {
            valueDisplay = `[${condition.value.join(', ')}]`;
          }
        } else {
          valueDisplay = String(condition.value || '');
        }

        const humanCondition = `${fieldLabel} ${operatorLabel.toLowerCase()} ${valueDisplay}`;
        groupConditions.push(humanCondition);

        // Generate metadata filter for backend
        if (condition.field.startsWith('metadata.')) {
          const metadataField = condition.field.substring(9); // Remove 'metadata.' prefix
          if (condition.operator === '$exists') {
            metadata[metadataField] = { [condition.operator]: condition.value };
          } else if (condition.value !== '' && condition.value != null) {
            metadata[metadataField] = { [condition.operator]: condition.value };
          }
        } else {
          // Core field - add to column filters
          columnFilters.push({
            id: condition.field,
            value: {
              conditions: [{
                operator: mapOperatorToColumnFilter(condition.operator),
                value: condition.value
              }],
              joinOperator: 'AND'
            }
          });
        }
      });

      // Process nested groups
      grp.groups.forEach(nestedGroup => {
        const nestedConditions = processGroup(nestedGroup, level + 1);
        if (nestedConditions.length > 0) {
          const nestedString = nestedConditions.length > 1 
            ? `(${nestedConditions.join(` ${nestedGroup.operator.toLowerCase()} `)})`
            : nestedConditions[0];
          groupConditions.push(nestedString);
        }
      });

      return groupConditions;
    };

    const allConditions = processGroup(query);
    const humanReadable = allConditions.length > 0 
      ? allConditions.join(` ${query.operator.toLowerCase()} `)
      : 'No conditions specified';

    // Generate MongoDB-style query representation
    const mongoQuery = generateMongoQuery(query);

    return {
      metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      columnFilters: columnFilters.length > 0 ? columnFilters : undefined,
      humanReadable,
      mongoQuery,
      fieldCount,
      conditionCount
    };
  };

  // Map QueryBuilder operators to column filter operators
  const mapOperatorToColumnFilter = (operator: string): string => {
    const mapping: Record<string, string> = {
      '$eq': 'equals',
      '$ne': 'notEqual',
      '$contains': 'contains',
      '$startsWith': 'startsWith',
      '$endsWith': 'endsWith',
      '$gt': 'greaterThan',
      '$gte': 'greaterThanOrEqual',
      '$lt': 'lessThan',
      '$lte': 'lessThanOrEqual',
      '$between': 'inRange',
      '$in': 'equals', // Simplified for column filters
      '$exists': 'notBlank'
    };
    return mapping[operator] || 'contains';
  };

  // Generate MongoDB-style query representation
  const generateMongoQuery = (group: QueryGroup): Record<string, any> => {
    const conditions: any[] = [];

    // Process conditions
    group.conditions.forEach(condition => {
      if (!condition.field || !condition.operator) return;
      
      if (condition.operator === '$exists') {
        conditions.push({ [condition.field]: { $exists: condition.value } });
      } else if (condition.value !== '' && condition.value != null) {
        conditions.push({ [condition.field]: { [condition.operator]: condition.value } });
      }
    });

    // Process nested groups
    group.groups.forEach(nestedGroup => {
      const nestedQuery = generateMongoQuery(nestedGroup);
      if (Object.keys(nestedQuery).length > 0) {
        conditions.push(nestedQuery);
      }
    });

    if (conditions.length === 0) {
      return {};
    } else if (conditions.length === 1) {
      return conditions[0];
    } else {
      return { [`$${group.operator.toLowerCase()}`]: conditions };
    }
  };

  const generatedQuery = generateQuery(query);

  const formatJSON = (obj: any): string => {
    return JSON.stringify(obj, null, 2);
  };

  const getValidationMessages = (): string[] => {
    const messages: string[] = [];
    
    if (generatedQuery.conditionCount === 0) {
      messages.push('No search conditions specified');
    }
    
    if (generatedQuery.fieldCount === 0) {
      messages.push('No fields selected');
    }

    // Check for incomplete conditions
    const checkGroup = (group: QueryGroup): void => {
      group.conditions.forEach(condition => {
        if (condition.field && !condition.operator) {
          messages.push(`Condition for "${condition.field}" is missing an operator`);
        }
        if (condition.field && condition.operator && condition.operator !== '$exists' && 
            (condition.value === '' || condition.value == null)) {
          messages.push(`Condition for "${condition.field}" is missing a value`);
        }
      });
      
      group.groups.forEach(checkGroup);
    };

    checkGroup(query);

    return messages;
  };

  const validationMessages = getValidationMessages();

  return (
    <div className={`query-preview ${className}`}>
      <div className="preview-header">
        <div className="preview-info">
          <h4>Query Preview</h4>
          <div className="query-stats">
            <span className="stat">
              <strong>{generatedQuery.fieldCount}</strong> field{generatedQuery.fieldCount !== 1 ? 's' : ''}
            </span>
            <span className="stat">
              <strong>{generatedQuery.conditionCount}</strong> condition{generatedQuery.conditionCount !== 1 ? 's' : ''}
            </span>
            <span className={`validation-status ${isValid ? 'valid' : 'invalid'}`}>
              {isValid ? '✓ Valid' : '⚠ Invalid'}
            </span>
          </div>
        </div>
        
        <button
          className="toggle-details"
          onClick={() => setShowDetails(!showDetails)}
        >
          {showDetails ? 'Hide Details' : 'Show Details'}
        </button>
      </div>

      <div className="preview-content">
        <div className="human-readable">
          <strong>Query:</strong> {generatedQuery.humanReadable}
        </div>

        {!isValid && validationMessages.length > 0 && (
          <div className="validation-messages">
            <h5>Issues:</h5>
            <ul>
              {validationMessages.map((message, index) => (
                <li key={index}>{message}</li>
              ))}
            </ul>
          </div>
        )}

        {showDetails && (
          <div className="query-details">
            <div className="detail-tabs">
              <button
                className={`tab-button ${activeTab === 'human' ? 'active' : ''}`}
                onClick={() => setActiveTab('human')}
              >
                Human Readable
              </button>
              <button
                className={`tab-button ${activeTab === 'json' ? 'active' : ''}`}
                onClick={() => setActiveTab('json')}
              >
                API Request
              </button>
              <button
                className={`tab-button ${activeTab === 'mongo' ? 'active' : ''}`}
                onClick={() => setActiveTab('mongo')}
              >
                MongoDB Style
              </button>
            </div>

            <div className="detail-content">
              {activeTab === 'human' && (
                <div className="human-detail">
                  <p>{generatedQuery.humanReadable}</p>
                  <div className="query-breakdown">
                    <h6>Query Breakdown:</h6>
                    <QueryBreakdown group={query} level={0} />
                  </div>
                </div>
              )}

              {activeTab === 'json' && (
                <div className="json-detail">
                  <h6>API Request Body:</h6>
                  <pre className="code-block">
                    {formatJSON({
                      ...(generatedQuery.metadata && { metadata: generatedQuery.metadata }),
                      ...(generatedQuery.columnFilters && { columnFilters: generatedQuery.columnFilters }),
                      // Add other common search parameters
                      limit: 50,
                      offset: 0
                    })}
                  </pre>
                </div>
              )}

              {activeTab === 'mongo' && (
                <div className="mongo-detail">
                  <h6>MongoDB-style Query:</h6>
                  <pre className="code-block">
                    {formatJSON(generatedQuery.mongoQuery)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Component to show hierarchical query breakdown
interface QueryBreakdownProps {
  group: QueryGroup;
  level: number;
}

const QueryBreakdown: React.FC<QueryBreakdownProps> = ({ group, level }) => {
  const indent = '  '.repeat(level);
  
  return (
    <div className="query-breakdown-group">
      {level > 0 && <div className="group-indicator">{indent}Group ({group.operator}):</div>}
      
      {group.conditions.map((condition, index) => (
        <div key={condition.id || index} className="condition-breakdown">
          {indent}• {condition.field || '(no field)'} {condition.operator || '(no operator)'} {
            condition.operator === '$exists' 
              ? (condition.value ? 'exists' : 'does not exist')
              : (condition.value || '(no value)')
          }
        </div>
      ))}
      
      {group.groups.map((nestedGroup, index) => (
        <QueryBreakdown key={nestedGroup.id || index} group={nestedGroup} level={level + 1} />
      ))}
    </div>
  );
};

export default QueryPreview;