import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api/admin';
import './Diseases.css';

interface Disease {
  id: number;
  name: string;
  category: string | null;
  synonyms: string[];
  search_terms: string[];
  created_at: string;
  document_count: number;
  source_coverage: Array<{
    source_name: string;
    document_count: number;
    last_scraped: string | null;
  }>;
}

const Diseases: React.FC = () => {
  const [diseases, setDiseases] = useState<Disease[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingDisease, setEditingDisease] = useState<Disease | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedDisease, setSelectedDisease] = useState<Disease | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    category: '',
    synonyms: [] as string[],
    search_terms: [] as string[]
  });
  const [newTerm, setNewTerm] = useState('');
  const [newSynonym, setNewSynonym] = useState('');

  useEffect(() => {
    loadDiseases();
  }, [search]);

  const loadDiseases = async () => {
    try {
      setLoading(true);
      const params: any = { limit: 1000 };
      if (search) params.search = search;
      
      const data = await adminApi.getDiseases(params);
      setDiseases(data);
    } catch (err) {
      setError('Failed to load diseases');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddSearchTerm = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && newTerm.trim()) {
      e.preventDefault();
      setFormData({
        ...formData,
        search_terms: [...formData.search_terms, newTerm.trim()]
      });
      setNewTerm('');
    }
  };

  const handleAddSynonym = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && newSynonym.trim()) {
      e.preventDefault();
      setFormData({
        ...formData,
        synonyms: [...formData.synonyms, newSynonym.trim()]
      });
      setNewSynonym('');
    }
  };

  const handleRemoveSearchTerm = (index: number) => {
    setFormData({
      ...formData,
      search_terms: formData.search_terms.filter((_, i) => i !== index)
    });
  };

  const handleRemoveSynonym = (index: number) => {
    setFormData({
      ...formData,
      synonyms: formData.synonyms.filter((_, i) => i !== index)
    });
  };

  const handleSave = async () => {
    try {
      if (editingDisease) {
        await adminApi.updateDisease(editingDisease.id, formData);
      } else {
        await adminApi.createDisease(formData);
      }
      setEditingDisease(null);
      setShowCreateForm(false);
      await loadDiseases();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save disease');
    }
  };

  const handleDeleteDisease = async (disease: Disease) => {
    const confirmMessage = disease.document_count > 0
      ? `⚠️ Cannot Delete Disease: ${disease.name}\n\nThis disease has ${disease.document_count} associated documents.\nRemove all document associations before deleting.`
      : `⚠️ Delete Disease: ${disease.name}\n\nThis will permanently delete the disease.\n\nContinue?`;
    
    if (disease.document_count > 0) {
      alert(confirmMessage);
      return;
    }
    
    if (window.confirm(confirmMessage)) {
      try {
        const result = await adminApi.deleteDisease(disease.id);
        alert(`✅ ${result.message}`);
        await loadDiseases();
      } catch (err: any) {
        alert(`❌ Failed to delete disease\n\n${err.response?.data?.detail || err.message}`);
      }
    }
  };


  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) return <div className="loading">Loading diseases...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="diseases-container">
      <div className="diseases-header">
        <h1>Disease Management</h1>
        <button 
          className="btn-primary"
          onClick={() => {
            setShowCreateForm(true);
            setFormData({
              name: '',
              category: '',
              synonyms: [],
              search_terms: []
            });
          }}
        >
          Add New Disease
        </button>
      </div>

      <div className="diseases-search">
        <input
          type="text"
          placeholder="Search diseases..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="diseases-grid">
        {diseases.map((disease) => (
          <div key={disease.id} className="disease-card">
            <div className="disease-header">
              <h3>{disease.name}</h3>
              <span className="document-count">{disease.document_count} docs</span>
            </div>
            
            {disease.category && (
              <div className="disease-category">{disease.category}</div>
            )}
            
            <div className="search-terms-section">
              <h4>Search Terms ({disease.search_terms.length})</h4>
              <div className="terms-preview">
                {disease.search_terms.length > 0 ? (
                  <code>{disease.search_terms.join(' OR ')}</code>
                ) : (
                  <span className="no-terms">No search terms configured</span>
                )}
              </div>
            </div>
            
            <div className="disease-actions">
              <button
                onClick={() => {
                  setEditingDisease(disease);
                  setFormData({
                    name: disease.name,
                    category: disease.category || '',
                    synonyms: disease.synonyms || [],
                    search_terms: disease.search_terms || []
                  });
                }}
                className="btn-sm"
              >
                Edit
              </button>
              <button
                onClick={() => setSelectedDisease(disease)}
                className="btn-sm"
              >
                Details
              </button>
              <button
                onClick={() => handleDeleteDisease(disease)}
                className="btn-sm btn-danger"
                title="Delete this disease"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {(showCreateForm || editingDisease) && (
        <div className="modal-overlay" onClick={() => {
          setShowCreateForm(false);
          setEditingDisease(null);
        }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{editingDisease ? 'Edit Disease' : 'Create New Disease'}</h2>
            
            <div className="form-group">
              <label>Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>
            
            <div className="form-group">
              <label>Category</label>
              <input
                type="text"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                placeholder="e.g., Neurological, Autoimmune"
              />
            </div>
            
            <div className="form-group">
              <label>Search Terms</label>
              <div className="terms-input-container">
                <input
                  type="text"
                  value={newTerm}
                  onChange={(e) => setNewTerm(e.target.value)}
                  onKeyPress={handleAddSearchTerm}
                  placeholder="Type a search term and press Enter"
                />
                <div className="terms-list">
                  {formData.search_terms.map((term, index) => (
                    <span key={index} className="term-tag">
                      {term}
                      <button onClick={() => handleRemoveSearchTerm(index)}>×</button>
                    </span>
                  ))}
                </div>
              </div>
              <small>These terms will be used when searching sources like PubMed</small>
            </div>
            
            <div className="form-group">
              <label>Synonyms</label>
              <div className="terms-input-container">
                <input
                  type="text"
                  value={newSynonym}
                  onChange={(e) => setNewSynonym(e.target.value)}
                  onKeyPress={handleAddSynonym}
                  placeholder="Type a synonym and press Enter"
                />
                <div className="terms-list">
                  {formData.synonyms.map((synonym, index) => (
                    <span key={index} className="term-tag">
                      {synonym}
                      <button onClick={() => handleRemoveSynonym(index)}>×</button>
                    </span>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="search-preview">
              <h4>Search Preview</h4>
              <code>
                {formData.search_terms.length > 0 
                  ? formData.search_terms.join(' OR ')
                  : 'No search terms configured'}
              </code>
            </div>
            
            <div className="form-buttons">
              <button onClick={handleSave} className="btn-primary">
                {editingDisease ? 'Update' : 'Create'}
              </button>
              <button onClick={() => {
                setShowCreateForm(false);
                setEditingDisease(null);
              }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedDisease && (
        <div className="modal-overlay" onClick={() => setSelectedDisease(null)}>
          <div className="modal-content modal-wide" onClick={(e) => e.stopPropagation()}>
            <h2>{selectedDisease.name} - Details</h2>
            
            <div className="disease-details">
              <div className="detail-section">
                <h3>General Information</h3>
                <p><strong>Category:</strong> {selectedDisease.category || 'Not specified'}</p>
                <p><strong>Documents:</strong> {selectedDisease.document_count}</p>
                <p><strong>Created:</strong> {formatDate(selectedDisease.created_at)}</p>
              </div>
              
              <div className="detail-section">
                <h3>Search Configuration</h3>
                <p><strong>Search Terms:</strong></p>
                <div className="terms-display">
                  {selectedDisease.search_terms.map((term, i) => (
                    <span key={i} className="term-tag">{term}</span>
                  ))}
                </div>
                <p><strong>Synonyms:</strong></p>
                <div className="terms-display">
                  {selectedDisease.synonyms.map((syn, i) => (
                    <span key={i} className="term-tag">{syn}</span>
                  ))}
                </div>
              </div>
              
              <div className="detail-section">
                <h3>Source Coverage</h3>
                <table className="coverage-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Documents</th>
                      <th>Last Scraped</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedDisease.source_coverage.map((coverage, i) => (
                      <tr key={i}>
                        <td>{coverage.source_name}</td>
                        <td>{coverage.document_count}</td>
                        <td>{formatDate(coverage.last_scraped)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            
            <div className="form-buttons">
              <button onClick={() => setSelectedDisease(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Diseases;