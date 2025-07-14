import React, { useState, useEffect } from 'react';
import './SourceTypeSelector.css';

export interface SourceType {
  id: string;
  label: string;
  icon: string;
  sources: string[];
  description: string;
  color: string;
}

interface SourceData {
  id: number;
  name: string;
  type: string;
  category: string;
  document_count: number;
  rate_limit: number;
  requires_auth: boolean;
  scraper_type: string;
}

interface SourceTypeSelectorProps {
  selectedTypes: string[];
  onSelectionChange: (types: string[]) => void;
  loading?: boolean;
}

// Category metadata will be populated from API response
const CATEGORY_METADATA: Record<string, { label: string; icon: string; description: string; color: string }> = {
  publications: {
    label: 'Publications',
    icon: '📚',
    description: 'Peer-reviewed medical literature and research papers',
    color: '#2196F3'
  },
  trials: {
    label: 'Clinical Trials',
    icon: '🧪',
    description: 'Ongoing and completed clinical research studies',
    color: '#4CAF50'
  },
  community: {
    label: 'Community',
    icon: '👥',
    description: 'Patient experiences and community discussions',
    color: '#FF9800'
  }
};

const SourceTypeSelector: React.FC<SourceTypeSelectorProps> = ({
  selectedTypes,
  onSelectionChange,
  loading = false
}) => {
  const [sourceTypes, setSourceTypes] = useState<SourceType[]>([]);
  const [fetchingData, setFetchingData] = useState(false);

  // Fetch source data from API and build dynamic source types
  useEffect(() => {
    const fetchSourceData = async () => {
      setFetchingData(true);
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/search/filters`);
        if (response.ok) {
          const filterData = await response.json();
          
          // Build source types from categories in filter response
          const types: SourceType[] = [];
          
          if (filterData.categories) {
            filterData.categories.forEach((category: any) => {
              const metadata = CATEGORY_METADATA[category.value];
              if (metadata) {
                // Get sources for this category
                const categorySources = filterData.sources
                  .filter((s: any) => s.category === category.value)
                  .map((s: any) => s.value);
                
                types.push({
                  id: category.value,
                  label: metadata.label,
                  icon: metadata.icon,
                  sources: categorySources,
                  description: metadata.description,
                  color: metadata.color,
                  documentCount: category.count || 0
                } as SourceType & { documentCount: number });
              }
            });
          }
          
          // Sort by category order
          types.sort((a, b) => {
            const order = ['publications', 'trials', 'community'];
            return order.indexOf(a.id) - order.indexOf(b.id);
          });
          
          setSourceTypes(types);
        }
      } catch (error) {
        console.error('Failed to fetch source data:', error);
      } finally {
        setFetchingData(false);
      }
    };

    fetchSourceData();
  }, []);
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
    if (selectedTypes.length === sourceTypes.length) {
      // Deselect all
      onSelectionChange([]);
    } else {
      // Select all
      onSelectionChange(sourceTypes.map(t => t.id));
    }
  };

  const isAllSelected = selectedTypes.length === sourceTypes.length && sourceTypes.length > 0;

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
        {fetchingData ? (
          <div className="loading-message">Loading source data...</div>
        ) : sourceTypes.length === 0 ? (
          <div className="no-sources-message">No sources available</div>
        ) : (
          sourceTypes.map(type => {
            const isSelected = selectedTypes.includes(type.id);
            const documentCount = (type as any).documentCount || 0;
          
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
          })
        )}
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