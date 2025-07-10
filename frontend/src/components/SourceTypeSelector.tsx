import React from 'react';
import './SourceTypeSelector.css';

export interface SourceType {
  id: string;
  label: string;
  icon: string;
  sources: string[];
  description: string;
  color: string;
}

interface SourceTypeSelectorProps {
  selectedTypes: string[];
  onSelectionChange: (types: string[]) => void;
  loading?: boolean;
}

const SOURCE_TYPES: SourceType[] = [
  {
    id: 'publications',
    label: 'Publications',
    icon: '📚',
    sources: ['PubMed'],
    description: 'Peer-reviewed medical literature and research papers',
    color: '#2196F3'
  },
  {
    id: 'trials',
    label: 'Clinical Trials',
    icon: '🧪',
    sources: ['ClinicalTrials.gov'],
    description: 'Ongoing and completed clinical research studies',
    color: '#4CAF50'
  },
  {
    id: 'secondary',
    label: 'Community',
    icon: '👥',
    sources: ['Reddit Medical', 'HealthUnlocked', 'Patient.info Forums'],
    description: 'Patient experiences and community discussions',
    color: '#FF9800'
  }
];

const SourceTypeSelector: React.FC<SourceTypeSelectorProps> = ({
  selectedTypes,
  onSelectionChange,
  loading = false
}) => {
  const handleTypeClick = (typeId: string) => {
    if (loading) return;
    
    if (selectedTypes.includes(typeId)) {
      // Remove type
      onSelectionChange(selectedTypes.filter(t => t !== typeId));
    } else {
      // Add type
      onSelectionChange([...selectedTypes, typeId]);
    }
  };

  const handleSelectAll = () => {
    if (selectedTypes.length === SOURCE_TYPES.length) {
      // Deselect all
      onSelectionChange([]);
    } else {
      // Select all
      onSelectionChange(SOURCE_TYPES.map(t => t.id));
    }
  };

  const isAllSelected = selectedTypes.length === SOURCE_TYPES.length;

  return (
    <div className="source-type-selector">
      <div className="selector-header">
        <h3>Data Sources</h3>
        <button 
          className={`select-all-btn ${isAllSelected ? 'active' : ''}`}
          onClick={handleSelectAll}
          disabled={loading}
        >
          {isAllSelected ? 'Deselect All' : 'Select All'}
        </button>
      </div>
      
      <div className="source-type-grid">
        {SOURCE_TYPES.map(type => {
          const isSelected = selectedTypes.includes(type.id);
          const documentCount = 0; // TODO: Get from API
          
          return (
            <div
              key={type.id}
              className={`source-type-card ${isSelected ? 'selected' : ''} ${loading ? 'loading' : ''}`}
              onClick={() => handleTypeClick(type.id)}
              style={{
                borderColor: isSelected ? type.color : 'transparent',
                backgroundColor: isSelected ? `${type.color}10` : 'transparent'
              }}
            >
              <div className="type-header">
                <span className="type-icon">{type.icon}</span>
                <span className="type-label">{type.label}</span>
              </div>
              
              <div className="type-description">
                {type.description}
              </div>
              
              <div className="type-sources">
                {type.sources.map(source => (
                  <span key={source} className="source-chip">
                    {source}
                  </span>
                ))}
              </div>
              
              <div className="type-footer">
                <span className="document-count">
                  {documentCount} documents
                </span>
                <span className={`selection-indicator ${isSelected ? 'selected' : ''}`}>
                  {isSelected ? '✓' : '○'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      
      {selectedTypes.length === 0 && (
        <div className="no-selection-warning">
          Please select at least one data source to search
        </div>
      )}
    </div>
  );
};

export default SourceTypeSelector;