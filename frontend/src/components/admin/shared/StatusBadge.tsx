import React from 'react';
import './StatusBadge.css';

interface StatusBadgeProps {
  status: string;
  size?: 'small' | 'medium' | 'large';
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'medium' }) => {
  const getStatusClass = () => {
    switch (status.toLowerCase()) {
      case 'active':
      case 'completed':
      case 'success':
        return 'status-success';
      case 'inactive':
      case 'disabled':
      case 'pending':
        return 'status-warning';
      case 'failed':
      case 'error':
      case 'cancelled':
        return 'status-danger';
      case 'running':
      case 'in_progress':
        return 'status-info';
      default:
        return 'status-default';
    }
  };

  const formatStatus = (status: string) => {
    return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase().replace('_', ' ');
  };

  return (
    <span className={`status-badge ${getStatusClass()} ${size}`}>
      {formatStatus(status)}
    </span>
  );
};

export default StatusBadge;