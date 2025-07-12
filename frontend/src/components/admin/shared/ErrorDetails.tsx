import React, { useState } from 'react';
import './ErrorDetails.css';

interface ErrorDetailsProps {
  error: any;
  title?: string;
  expanded?: boolean;
}

const ErrorDetails: React.FC<ErrorDetailsProps> = ({ 
  error, 
  title = 'Error Details',
  expanded = false 
}) => {
  const [isExpanded, setIsExpanded] = useState(expanded);

  const formatError = (error: any): string => {
    if (typeof error === 'string') {
      return error;
    }
    if (error instanceof Error) {
      return error.stack || error.message;
    }
    return JSON.stringify(error, null, 2);
  };

  const getErrorSummary = (error: any): string => {
    if (typeof error === 'string') {
      return error.split('\n')[0];
    }
    if (error instanceof Error) {
      return error.message;
    }
    if (error.message) {
      return error.message;
    }
    return 'An error occurred';
  };

  return (
    <div className="error-details">
      <div className="error-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="error-icon">⚠️</span>
        <span className="error-title">{title}</span>
        <span className="error-summary">{getErrorSummary(error)}</span>
        <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▼</span>
      </div>
      {isExpanded && (
        <div className="error-body">
          <pre>{formatError(error)}</pre>
        </div>
      )}
    </div>
  );
};

export default ErrorDetails;