import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api/admin';
import './Sources.css';

interface Source {
  id: number;
  name: string;
  category: string;
  base_url: string | null;
  scraper_type: string | null;
  rate_limit: number;
  is_active: boolean;
  config: Record<string, any>;
  association_method: string;
  disease_ids: number[];
  disease_names: string[];
  last_crawled: string | null;
  last_crawled_id: string | null;
  crawl_state: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  document_count: number;
  recent_job_count: number;
  daily_limit: number;
  weekly_limit: number;
}

const Sources: React.FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [diseases, setDiseases] = useState<Array<{id: number; name: string}>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingSource, setEditingSource] = useState<Source | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [filter, setFilter] = useState({ is_active: null as boolean | null, category: '' });
  const [formData, setFormData] = useState({
    name: '',
    category: 'community',
    base_url: '',
    scraper_type: '',
    rate_limit: 10,
    association_method: 'search',
    disease_ids: [] as number[],
    daily_limit: 100,
    weekly_limit: 500,
    config: {}
  });

  useEffect(() => {
    loadSources();
    loadDiseases();
  }, [filter]);

  const loadSources = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (filter.is_active !== null) params.is_active = filter.is_active;
      if (filter.category) params.category = filter.category;
      
      const data = await adminApi.getSources(params);
      setSources(data);
    } catch (err) {
      setError('Failed to load sources');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadDiseases = async () => {
    try {
      const data = await adminApi.getDiseases({ limit: 1000 });
      setDiseases(data.map((d: any) => ({ id: d.id, name: d.name })));
    } catch (err) {
      console.error('Failed to load diseases:', err);
    }
  };

  const handleToggleActive = async (source: Source) => {
    try {
      await adminApi.updateSource(source.id, { is_active: !source.is_active });
      await loadSources();
    } catch (err) {
      console.error('Failed to update source:', err);
    }
  };

  const handleTestConnection = async (sourceId: number) => {
    try {
      const result = await adminApi.testSourceConnection(sourceId);
      alert(`✅ Connection Test Results\n\nStatus: ${result.status}\nMessage: ${result.message}\n\nThis verifies that the scraper can connect to the data source.`);
    } catch (err) {
      alert('❌ Connection Test Failed\n\nThe scraper could not connect to this data source. Check the configuration and try again.');
    }
  };

  const handleTriggerScrape = async (source: Source) => {
    try {
      const confirmMessage = source.association_method === 'linked' && source.disease_names.length > 0
        ? `🔄 Run Scraper for ${source.name}\n\nThis will collect new data for:\n${source.disease_names.join(', ')}\n\nNote: This process may take several minutes depending on the amount of data.`
        : `🔄 Run Scraper for ${source.name}\n\nThis will run the scraper with its current configuration.\n\nNote: This process may take several minutes depending on the amount of data.`;
      
      if (window.confirm(confirmMessage)) {
        const result = await adminApi.triggerSourceScrape(source.id);
        alert(`✅ Scraper Started Successfully\n\nJob ID: ${result.job_id}\n${result.message}\n\nYou can monitor progress in the Jobs section.`);
      }
    } catch (err: any) {
      alert(`❌ Failed to Start Scraper\n\n${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDeleteSource = async (source: Source) => {
    const confirmMessage = source.document_count > 0
      ? `⚠️ Delete Source: ${source.name}\n\nThis source has ${source.document_count} documents.\nThe source will be deactivated instead of deleted.\n\nContinue?`
      : `⚠️ Delete Source: ${source.name}\n\nThis will permanently delete the source.\n\nContinue?`;
    
    if (window.confirm(confirmMessage)) {
      try {
        const result = await adminApi.deleteSource(source.id);
        alert(`✅ ${result.message}`);
        await loadSources();
      } catch (err: any) {
        alert(`❌ Failed to delete source\n\n${err.response?.data?.detail || err.message}`);
      }
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  if (loading) return <div className="loading">Loading sources...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="sources-container">
      <div className="sources-header">
        <h1>Sources Management</h1>
        <button 
          className="btn-primary"
          onClick={() => setShowCreateForm(true)}
        >
          Add New Source
        </button>
      </div>

      <div className="sources-filters">
        <select
          value={filter.is_active === null ? '' : filter.is_active.toString()}
          onChange={(e) => setFilter({ 
            ...filter, 
            is_active: e.target.value === '' ? null : e.target.value === 'true' 
          })}
        >
          <option value="">All Sources</option>
          <option value="true">Active Only</option>
          <option value="false">Inactive Only</option>
        </select>
        
        <select
          value={filter.category}
          onChange={(e) => setFilter({ ...filter, category: e.target.value })}
        >
          <option value="">All Categories</option>
          <option value="publications">Publications</option>
          <option value="trials">Clinical Trials</option>
          <option value="community">Community</option>
        </select>
      </div>

      <div className="sources-table-container">
        <table className="sources-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Diseases</th>
              <th>Status</th>
              <th>Documents</th>
              <th>Last Crawled</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr key={source.id}>
                <td>
                  <div className="source-name">{source.name}</div>
                  {source.base_url && (
                    <div className="source-url">{source.base_url}</div>
                  )}
                </td>
                <td>
                  <span className="association-type">
                    {source.association_method === 'linked' ? '🔗 Linked' : '🔍 Search'}
                  </span>
                  <div className="source-category">{source.category}</div>
                </td>
                <td>
                  {source.association_method === 'linked' && source.disease_names?.length > 0 ? (
                    <div className="disease-list">
                      {source.disease_names.slice(0, 2).map((name, idx) => (
                        <span key={idx} className="disease-tag">{name}</span>
                      ))}
                      {source.disease_names.length > 2 && (
                        <span className="disease-more">+{source.disease_names.length - 2} more</span>
                      )}
                    </div>
                  ) : (
                    <span className="all-diseases">All diseases</span>
                  )}
                </td>
                <td>
                  <span className={`status ${source.is_active ? 'active' : 'inactive'}`}>
                    {source.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{source.document_count.toLocaleString()}</td>
                <td>{formatDate(source.last_crawled)}</td>
                <td>
                  <div className="actions">
                    <button
                      onClick={() => handleToggleActive(source)}
                      className="btn-sm"
                    >
                      {source.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => {
                        setEditingSource(source);
                        setFormData({
                          name: source.name,
                          category: source.category,
                          base_url: source.base_url || '',
                          scraper_type: source.scraper_type || '',
                          rate_limit: source.rate_limit,
                          association_method: source.association_method || 'search',
                          disease_ids: source.disease_ids || [],
                          daily_limit: source.daily_limit || 100,
                          weekly_limit: source.weekly_limit || 500,
                          config: source.config || {}
                        });
                      }}
                      className="btn-sm"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleTestConnection(source.id)}
                      className="btn-sm"
                      title="Test if the scraper can connect to this data source"
                    >
                      Test Connection
                    </button>
                    <button
                      onClick={() => handleTriggerScrape(source)}
                      className="btn-sm btn-primary"
                      disabled={!source.is_active}
                      title={source.is_active ? 'Run the scraper to collect new data' : 'Activate source first'}
                    >
                      Run Scraper
                    </button>
                    <button
                      onClick={() => handleDeleteSource(source)}
                      className="btn-sm btn-danger"
                      title="Delete this source"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(showCreateForm || editingSource) && (
        <div className="modal-overlay" onClick={() => {
          setShowCreateForm(false);
          setEditingSource(null);
        }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{editingSource ? 'Edit Source' : 'Create New Source'}</h2>
            <form onSubmit={async (e) => {
              e.preventDefault();
              try {
                const configText = (e.target as any).config.value;
                const config = configText ? JSON.parse(configText) : {};
                
                const payload = {
                  ...formData,
                  config,
                  is_active: true
                };
                
                if (editingSource) {
                  await adminApi.updateSource(editingSource.id, payload);
                } else {
                  await adminApi.createSource(payload);
                }
                
                setShowCreateForm(false);
                setEditingSource(null);
                await loadSources();
              } catch (err: any) {
                alert(err.message || 'Failed to save source');
              }
            }}>
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
                <label>Association Method *</label>
                <select 
                  value={formData.association_method}
                  onChange={(e) => setFormData({ ...formData, association_method: e.target.value })}
                  required
                >
                  <option value="search">🔍 Search - Searches for disease terms (PubMed, ClinicalTrials)</option>
                  <option value="linked">🔗 Linked - Fixed to specific diseases (Subreddits, Blogs)</option>
                </select>
              </div>
              
              {formData.association_method === 'linked' && (
                <div className="form-group">
                  <label>Linked Diseases *</label>
                  <select 
                    multiple
                    value={formData.disease_ids.map(String)}
                    onChange={(e) => {
                      const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                      setFormData({ ...formData, disease_ids: selected });
                    }}
                    style={{ height: '150px' }}
                    required
                  >
                    {diseases.map(disease => (
                      <option key={disease.id} value={disease.id}>
                        {disease.name}
                      </option>
                    ))}
                  </select>
                  <small>Hold Ctrl/Cmd to select multiple diseases</small>
                </div>
              )}
              
              <div className="form-group">
                <label>Category *</label>
                <select 
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  required
                >
                  <option value="publications">Publications</option>
                  <option value="trials">Clinical Trials</option>
                  <option value="community">Community</option>
                </select>
              </div>
              
              <div className="form-group">
                <label>Base URL</label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                />
              </div>
              
              <div className="form-group">
                <label>Scraper Type</label>
                <select 
                  value={formData.scraper_type}
                  onChange={(e) => setFormData({ ...formData, scraper_type: e.target.value })}
                >
                  <option value="">Select scraper type...</option>
                  <option value="reddit_scraper">Reddit Scraper</option>
                  <option value="web_scraper">Web Scraper</option>
                  <option value="pubmed_api">PubMed API</option>
                  <option value="clinicaltrials_api">ClinicalTrials API</option>
                </select>
              </div>
              
              <div className="form-group">
                <label>Rate Limit (requests/second)</label>
                <input
                  type="number"
                  value={formData.rate_limit}
                  onChange={(e) => setFormData({ ...formData, rate_limit: parseInt(e.target.value) })}
                  min="1"
                  max="100"
                />
              </div>
              
              <div className="form-group">
                <label>Configuration (JSON)</label>
                <textarea
                  name="config"
                  rows={6}
                  defaultValue={JSON.stringify(formData.config, null, 2)}
                  placeholder={'{\n  "key": "value",\n  "limit": 50\n}'}
                  style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
                />
              </div>
              <div className="form-buttons">
                <button type="submit" className="btn-primary">
                  {editingSource ? 'Update' : 'Create'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false);
                    setEditingSource(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sources;