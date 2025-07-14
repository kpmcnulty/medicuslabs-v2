import React, { useEffect, useState } from 'react';
import { FilterOption } from '../types';
import { searchAPI } from '../api/search';
import './EnhancedFilters.css';

interface EnhancedFiltersProps {
  onFiltersChange: (filters: any) => void;
  loading?: boolean;
}

interface FilterState {
  sources: string[];
  sourceTypes: string[];
  diseases: string[];
  studyPhases: string[];
  studyTypes: string[];
  trialStatuses: string[];
  publicationTypes: string[];
  journals: string[];
  dateFrom?: string;
  dateTo?: string;
  publicationDateFrom?: string;
  publicationDateTo?: string;
}

const EnhancedFilters: React.FC<EnhancedFiltersProps> = ({ onFiltersChange, loading }) => {
  const [filterOptions, setFilterOptions] = useState<any>({
    sources: [],
    sourceTypes: [],
    diseases: [],
    studyPhases: [],
    studyTypes: [],
    trialStatuses: [],
    publicationTypes: [],
    journals: [],
    dateRanges: {}
  });

  const [filters, setFilters] = useState<FilterState>({
    sources: [],
    sourceTypes: [],
    diseases: [],
    studyPhases: [],
    studyTypes: [],
    trialStatuses: [],
    publicationTypes: [],
    journals: []
  });

  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['sources', 'diseases']));

  useEffect(() => {
    loadFilterOptions();
  }, []);

  useEffect(() => {
    onFiltersChange(filters);
  }, [filters, onFiltersChange]);

  const loadFilterOptions = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/search/filters`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const options = await response.json();
      console.log('Loaded filter options:', options);
      setFilterOptions(options || {
        sources: [],
        sourceTypes: [],
        diseases: [],
        studyPhases: [],
        studyTypes: [],
        trialStatuses: [],
        publicationTypes: [],
        journals: [],
        dateRanges: {}
      });
    } catch (error) {
      console.error('Failed to load filter options:', error);
      // Set default empty structure to prevent crashes
      setFilterOptions({
        sources: [],
        sourceTypes: [],
        diseases: [],
        studyPhases: [],
        studyTypes: [],
        trialStatuses: [],
        publicationTypes: [],
        journals: [],
        dateRanges: {}
      });
    }
  };

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  const handleFilterChange = (filterType: keyof FilterState, value: string, checked: boolean) => {
    setFilters(prev => {
      const currentValues = prev[filterType] as string[];
      let newValues: string[];
      
      if (checked) {
        newValues = [...currentValues, value];
      } else {
        newValues = currentValues.filter(v => v !== value);
      }
      
      return {
        ...prev,
        [filterType]: newValues
      };
    });
  };

  const handleDateChange = (dateType: string, value: string) => {
    setFilters(prev => ({
      ...prev,
      [dateType]: value || undefined
    }));
  };

  const clearAllFilters = () => {
    setFilters({
      sources: [],
      sourceTypes: [],
      diseases: [],
      studyPhases: [],
      studyTypes: [],
      trialStatuses: [],
      publicationTypes: [],
      journals: []
    });
  };

  const getActiveFilterCount = () => {
    return Object.values(filters).reduce((count, value) => {
      if (Array.isArray(value)) {
        return count + value.length;
      }
      return value ? count + 1 : count;
    }, 0);
  };

  const renderFilterSection = (
    title: string,
    sectionKey: string,
    options: any[],
    filterKey: keyof FilterState,
    valueKey: string = 'name'
  ) => {
    const isExpanded = expandedSections.has(sectionKey);
    const selectedCount = (filters[filterKey] as string[]).length;

    return (
      <div className="filter-section">
        <div className="filter-header" onClick={() => toggleSection(sectionKey)}>
          <span className="filter-title">
            {title}
            {selectedCount > 0 && <span className="selected-count">({selectedCount})</span>}
          </span>
          <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
        </div>
        {isExpanded && (
          <div className="filter-options">
            {(options || []).map((option) => (
              <label key={option[valueKey]} className="filter-option">
                <input
                  type="checkbox"
                  checked={(filters[filterKey] as string[]).includes(option[valueKey])}
                  onChange={(e) => handleFilterChange(filterKey, option[valueKey], e.target.checked)}
                  disabled={loading}
                />
                <span className="option-label">
                  {option[valueKey] || option.value}
                  {option.count !== undefined && (
                    <span className="option-count">({option.count})</span>
                  )}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="enhanced-filters">
      <div className="filters-header">
        <h3>Filters</h3>
        {getActiveFilterCount() > 0 && (
          <button className="clear-filters-btn" onClick={clearAllFilters}>
            Clear All ({getActiveFilterCount()})
          </button>
        )}
      </div>

      <div className="filter-sections">
        {/* Sources */}
        {renderFilterSection('Data Sources', 'sources', filterOptions.sources, 'sources')}
        
        {/* Source Types */}
        {filterOptions.sourceTypes.length > 0 && 
          renderFilterSection('Source Types', 'sourceTypes', filterOptions.sourceTypes, 'sourceTypes', 'type')}
        
        {/* Diseases */}
        {renderFilterSection('Diseases/Conditions', 'diseases', filterOptions.diseases, 'diseases')}
        
        {/* Date Filters */}
        <div className="filter-section">
          <div className="filter-header" onClick={() => toggleSection('dates')}>
            <span className="filter-title">Date Range</span>
            <span className="expand-icon">{expandedSections.has('dates') ? '▼' : '▶'}</span>
          </div>
          {expandedSections.has('dates') && (
            <div className="date-filters">
              <div className="date-group">
                <label>Added to System</label>
                <input
                  type="date"
                  value={filters.dateFrom || ''}
                  onChange={(e) => handleDateChange('dateFrom', e.target.value)}
                  disabled={loading}
                />
                <span>to</span>
                <input
                  type="date"
                  value={filters.dateTo || ''}
                  onChange={(e) => handleDateChange('dateTo', e.target.value)}
                  disabled={loading}
                />
              </div>
              <div className="date-group">
                <label>Publication Date</label>
                <input
                  type="date"
                  value={filters.publicationDateFrom || ''}
                  onChange={(e) => handleDateChange('publicationDateFrom', e.target.value)}
                  disabled={loading}
                />
                <span>to</span>
                <input
                  type="date"
                  value={filters.publicationDateTo || ''}
                  onChange={(e) => handleDateChange('publicationDateTo', e.target.value)}
                  disabled={loading}
                />
              </div>
            </div>
          )}
        </div>
        
        {/* Clinical Trials Filters */}
        {(filterOptions.studyPhases.length > 0 || filterOptions.studyTypes.length > 0 || filterOptions.trialStatuses.length > 0) && (
          <>
            <div className="filter-group-header">Clinical Trials</div>
            {filterOptions.studyPhases.length > 0 && 
              renderFilterSection('Study Phases', 'studyPhases', filterOptions.studyPhases, 'studyPhases', 'value')}
            {filterOptions.studyTypes.length > 0 && 
              renderFilterSection('Study Types', 'studyTypes', filterOptions.studyTypes, 'studyTypes', 'value')}
            {filterOptions.trialStatuses.length > 0 && 
              renderFilterSection('Trial Status', 'trialStatuses', filterOptions.trialStatuses, 'trialStatuses', 'value')}
          </>
        )}
        
        {/* PubMed Filters */}
        {(filterOptions.publicationTypes.length > 0 || filterOptions.journals.length > 0) && (
          <>
            <div className="filter-group-header">PubMed</div>
            {filterOptions.publicationTypes.length > 0 && 
              renderFilterSection('Publication Types', 'publicationTypes', filterOptions.publicationTypes, 'publicationTypes', 'value')}
            {filterOptions.journals.length > 0 && 
              renderFilterSection('Journals', 'journals', filterOptions.journals, 'journals', 'value')}
          </>
        )}
      </div>
    </div>
  );
};

export default EnhancedFilters;