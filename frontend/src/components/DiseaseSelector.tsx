import React, { useState, useEffect, useRef } from 'react';
import './DiseaseSelector.css';

interface Disease {
  value: string;
  count: number;
  category?: string;
}

interface DiseaseSelectorProps {
  selectedDisease: string | null;
  onDiseaseChange: (disease: string | null) => void;
  placeholder?: string;
}

const DiseaseSelector: React.FC<DiseaseSelectorProps> = ({
  selectedDisease,
  onDiseaseChange,
  placeholder = "Select a disease..."
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [diseases, setDiseases] = useState<Disease[]>([]);
  const [loading, setLoading] = useState(false);
  
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch diseases from API
  useEffect(() => {
    const fetchDiseases = async () => {
      setLoading(true);
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/search/filters`);
        const data = await response.json();
        
        const diseaseList = data.diseases || [];
        setDiseases(diseaseList);
      } catch (error) {
        console.error('Failed to fetch diseases:', error);
        setDiseases([]);
      } finally {
        setLoading(false);
      }
    };

    fetchDiseases();
  }, []);

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (disease: string) => {
    onDiseaseChange(disease);
    setIsOpen(false);
  };

  const handleClear = () => {
    onDiseaseChange(null);
  };

  return (
    <div className="disease-selector" ref={dropdownRef}>
      <div className="selector-label">
        <span className="label-text">Disease/Condition</span>
        {selectedDisease && (
          <button className="clear-btn" onClick={handleClear} title="Clear selection">
            ✕
          </button>
        )}
      </div>
      
      <div className="selector-input-wrapper">
        <div 
          className="selector-input"
          onClick={() => setIsOpen(!isOpen)}
        >
          {selectedDisease || placeholder}
        </div>
        <span className="selector-icon">▼</span>
      </div>

      {isOpen && (
        <div className="selector-dropdown">
          {loading ? (
            <div className="dropdown-loading">Loading diseases...</div>
          ) : (
            <div className="dropdown-list">
              {diseases.length > 0 ? (
                diseases.map(disease => (
                  <div
                    key={disease.value}
                    className={`dropdown-item ${selectedDisease === disease.value ? 'selected' : ''}`}
                    onClick={() => handleSelect(disease.value)}
                  >
                    <span className="disease-name">{disease.value}</span>
                    {disease.count > 0 && (
                      <span className="document-count">{disease.count}</span>
                    )}
                  </div>
                ))
              ) : (
                <div className="no-results">No diseases available</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DiseaseSelector;