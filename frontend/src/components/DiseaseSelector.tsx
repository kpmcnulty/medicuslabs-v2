import React, { useState, useEffect, useRef } from 'react';
import './DiseaseSelector.css';

interface Disease {
  value: string;
  count: number;
  category?: string;
}

interface DiseaseSelectorProps {
  selectedDiseases: string[];
  onDiseasesChange: (diseases: string[]) => void;
  placeholder?: string;
}

const DiseaseSelector: React.FC<DiseaseSelectorProps> = ({
  selectedDiseases,
  onDiseasesChange,
  placeholder = "Select diseases..."
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [diseases, setDiseases] = useState<Disease[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectAll, setSelectAll] = useState(true);
  
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
        
        // Auto-select all diseases on load
        if (selectedDiseases.length === 0 && diseaseList.length > 0) {
          onDiseasesChange(diseaseList.map((d: Disease) => d.value));
        }
      } catch (error) {
        console.error('Failed to fetch diseases:', error);
        setDiseases([]);
      } finally {
        setLoading(false);
      }
    };

    fetchDiseases();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  const handleToggleDisease = (disease: string) => {
    if (selectedDiseases.includes(disease)) {
      const newSelection = selectedDiseases.filter(d => d !== disease);
      onDiseasesChange(newSelection);
      setSelectAll(false);
    } else {
      const newSelection = [...selectedDiseases, disease];
      onDiseasesChange(newSelection);
      setSelectAll(newSelection.length === diseases.length);
    }
  };

  const handleSelectAll = () => {
    if (selectAll) {
      onDiseasesChange([]);
      setSelectAll(false);
    } else {
      onDiseasesChange(diseases.map(d => d.value));
      setSelectAll(true);
    }
  };

  const handleClear = () => {
    onDiseasesChange([]);
    setSelectAll(false);
  };

  // Update selectAll state when diseases change
  useEffect(() => {
    if (diseases.length > 0) {
      setSelectAll(selectedDiseases.length === diseases.length);
    }
  }, [selectedDiseases, diseases]);

  return (
    <div className="disease-selector" ref={dropdownRef}>
      <div className="selector-label">
        <span className="label-text">Disease/Condition</span>
        {selectedDiseases.length > 0 && (
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
          {selectedDiseases.length === 0 
            ? placeholder 
            : selectedDiseases.length === diseases.length 
            ? `All diseases (${diseases.length})`
            : selectedDiseases.length === 1
            ? selectedDiseases[0]
            : `${selectedDiseases.length} diseases selected`}
        </div>
        <span className="selector-icon">▼</span>
      </div>

      {isOpen && (
        <div className="selector-dropdown">
          {loading ? (
            <div className="dropdown-loading">Loading diseases...</div>
          ) : (
            <>
              <div className="select-all-section">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={selectAll}
                    onChange={handleSelectAll}
                  />
                  <span>Select All</span>
                </label>
              </div>
              <div className="dropdown-list">
                {diseases.length > 0 ? (
                  diseases.map(disease => (
                    <div
                      key={disease.value}
                      className={`dropdown-item ${selectedDiseases.includes(disease.value) ? 'selected' : ''}`}
                      onClick={() => handleToggleDisease(disease.value)}
                    >
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={selectedDiseases.includes(disease.value)}
                          onChange={() => {}}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <span className="disease-name">{disease.value}</span>
                      </label>
                      {disease.count > 0 && (
                        <span className="document-count">{disease.count}</span>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="no-results">No diseases available</div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default DiseaseSelector;