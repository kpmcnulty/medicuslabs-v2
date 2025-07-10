import React, { useState, useEffect, useRef, useCallback } from 'react';
import { debounce } from '../utils/debounce';
import './DiseaseSelector.css';

interface Disease {
  id: number;
  name: string;
  documentCount?: number;
}

interface DiseaseSelectorProps {
  selectedDisease: string | null;
  onDiseaseChange: (disease: string | null) => void;
  sourceTypes?: string[];
  placeholder?: string;
}

const DiseaseSelector: React.FC<DiseaseSelectorProps> = ({
  selectedDisease,
  onDiseaseChange,
  sourceTypes = [],
  placeholder = "Search or select a disease/condition..."
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [diseases, setDiseases] = useState<Disease[]>([]);
  const [filteredDiseases, setFilteredDiseases] = useState<Disease[]>([]);
  const [loading, setLoading] = useState(false);
  const [popularDiseases, setPopularDiseases] = useState<Disease[]>([]);
  
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch diseases from API
  const fetchDiseases = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/search/filters`);
      const data = await response.json();
      
      const diseaseList = data.diseases?.map((d: any) => ({
        id: d.name, // Using name as ID for now
        name: d.name,
        documentCount: d.count
      })) || [];
      
      setDiseases(diseaseList);
      
      // Set popular diseases (top 5 by document count)
      const popular = [...diseaseList]
        .sort((a, b) => (b.documentCount || 0) - (a.documentCount || 0))
        .slice(0, 5);
      setPopularDiseases(popular);
      
      // Initialize filtered list
      setFilteredDiseases(diseaseList);
    } catch (error) {
      console.error('Failed to fetch diseases:', error);
      setDiseases([]);
      setFilteredDiseases([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDiseases();
  }, [sourceTypes]); // Refetch when source types change

  // Filter diseases based on search term
  const filterDiseases = useCallback(
    debounce((term: string) => {
      if (!term.trim()) {
        setFilteredDiseases(diseases);
        return;
      }

      const filtered = diseases.filter(disease =>
        disease.name.toLowerCase().includes(term.toLowerCase())
      );
      setFilteredDiseases(filtered);
    }, 300),
    [diseases]
  );

  useEffect(() => {
    filterDiseases(searchTerm);
  }, [searchTerm, filterDiseases]);

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

  const handleSelect = (disease: Disease) => {
    onDiseaseChange(disease.name);
    setSearchTerm('');
    setIsOpen(false);
  };

  const handleClear = () => {
    onDiseaseChange(null);
    setSearchTerm('');
  };

  const handleInputClick = () => {
    setIsOpen(true);
    inputRef.current?.select();
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
        <input
          ref={inputRef}
          type="text"
          className="selector-input"
          placeholder={selectedDisease || placeholder}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onClick={handleInputClick}
          onFocus={() => setIsOpen(true)}
        />
        <span className="selector-icon">🔍</span>
      </div>

      {isOpen && (
        <div className="selector-dropdown">
          {loading ? (
            <div className="dropdown-loading">Loading diseases...</div>
          ) : (
            <>
              {searchTerm === '' && popularDiseases.length > 0 && (
                <div className="dropdown-section">
                  <div className="section-header">Popular Diseases</div>
                  {popularDiseases.map(disease => (
                    <div
                      key={disease.id}
                      className={`dropdown-item ${selectedDisease === disease.name ? 'selected' : ''}`}
                      onClick={() => handleSelect(disease)}
                    >
                      <span className="disease-name">{disease.name}</span>
                      {disease.documentCount !== undefined && (
                        <span className="document-count">{disease.documentCount} docs</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <div className="dropdown-section">
                {searchTerm !== '' && (
                  <div className="section-header">
                    {filteredDiseases.length} results for "{searchTerm}"
                  </div>
                )}
                {searchTerm === '' && (
                  <div className="section-header">All Diseases</div>
                )}
                
                <div className="dropdown-list">
                  {filteredDiseases.length > 0 ? (
                    filteredDiseases.map(disease => (
                      <div
                        key={disease.id}
                        className={`dropdown-item ${selectedDisease === disease.name ? 'selected' : ''}`}
                        onClick={() => handleSelect(disease)}
                      >
                        <span className="disease-name">{disease.name}</span>
                        {disease.documentCount !== undefined && (
                          <span className="document-count">{disease.documentCount} docs</span>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="no-results">
                      No diseases found matching "{searchTerm}"
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default DiseaseSelector;