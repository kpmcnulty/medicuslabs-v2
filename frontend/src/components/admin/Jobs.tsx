import React, { useEffect, useState, useCallback, useRef } from 'react';
import { adminApi } from '../../api/admin';
import StatusBadge from './shared/StatusBadge';
import LoadingSpinner from './shared/LoadingSpinner';
import ErrorDetails from './shared/ErrorDetails';
import ConfirmDialog from './shared/ConfirmDialog';
import './Jobs.css';

interface Job {
  id: number;
  source_id: number;
  source_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  documents_found: number | null;
  documents_processed: number | null;
  errors: number | null;
  error_details: any[] | null;
  config: any;
  created_at: string;
  updated_at: string;
  duration_seconds: number | null;
}

interface JobStats {
  period_days: number;
  overall: {
    total_jobs: number;
    completed: number;
    failed: number;
    running: number;
    cancelled: number;
    total_documents_found: number;
    total_documents_processed: number;
    avg_duration_seconds: number;
  };
  by_source: Array<{
    source_name: string;
    job_count: number;
    completed: number;
    failed: number;
    documents_found: number;
    documents_processed: number;
    avg_duration: number;
  }>;
  daily_trends: Array<{
    date: string;
    jobs: number;
    completed: number;
    documents: number;
  }>;
  recent_errors: Array<{
    id: number;
    source_name: string;
    started_at: string;
    errors: number;
    error_sample: string;
  }>;
}

const Jobs: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<JobStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [cancelConfirm, setCancelConfirm] = useState<Job | null>(null);
  const [showTriggerDialog, setShowTriggerDialog] = useState(false);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [isPageVisible, setIsPageVisible] = useState(true);
  const refreshIntervalRef = useRef<NodeJS.Timer | null>(null);
  
  // Trigger dialog state
  const [sources, setSources] = useState<any[]>([]);
  const [diseases, setDiseases] = useState<any[]>([]);
  const [triggerForm, setTriggerForm] = useState({
    source_id: 0,
    disease_ids: [] as number[],
    job_type: 'full' as 'full' | 'incremental',
    options: {}
  });

  const loadJobs = useCallback(async () => {
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      if (sourceFilter) params.source_id = parseInt(sourceFilter);
      
      const data = await adminApi.getJobs(params);
      setJobs(data);
    } catch (err) {
      setError('Failed to load jobs');
      console.error(err);
    }
  }, [statusFilter, sourceFilter]);

  const loadStats = async () => {
    try {
      const data = await adminApi.getJobStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };
  
  const loadSourcesAndDiseases = async () => {
    try {
      const [sourcesData, diseasesData] = await Promise.all([
        adminApi.getSources(),
        adminApi.getDiseases({ limit: 1000 })
      ]);
      // Filter only active sources
      const activeSources = sourcesData.filter((source: any) => source.is_active);
      setSources(activeSources);
      setDiseases(diseasesData);
    } catch (err) {
      console.error('Failed to load sources/diseases:', err);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      await Promise.all([loadJobs(), loadStats(), loadSourcesAndDiseases()]);
      setLoading(false);
    };
    
    fetchData();
  }, [loadJobs]);

  // Handle page visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsPageVisible(!document.hidden);
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  useEffect(() => {
    // Clear any existing interval
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
    
    if (autoRefresh && isPageVisible) {
      const interval = setInterval(() => {
        loadJobs();
      }, 5000); // Refresh every 5 seconds
      refreshIntervalRef.current = interval;
    }
    
    // Cleanup on unmount or dependency change
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    };
  }, [autoRefresh, isPageVisible, loadJobs]);

  const handleCancelJob = async () => {
    if (!cancelConfirm) return;
    
    try {
      await adminApi.cancelJob(cancelConfirm.id);
      setCancelConfirm(null);
      await loadJobs();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to cancel job');
    }
  };
  
  const handleTriggerJob = async () => {
    try {
      if (triggerForm.source_id === 0) {
        // Bulk job for all sources
        const result = await adminApi.triggerBulkJobs({
          source_ids: [],
          disease_ids: triggerForm.disease_ids,
          job_type: triggerForm.job_type,
          options: triggerForm.options
        });
        alert(`✅ Bulk job triggered successfully!\n\nGroup ID: ${result.group_id}\nJob Type: ${result.job_type}\nSources: ${result.sources.join(', ')}\nDiseases: ${result.diseases.join(', ')}`);
      } else {
        // Single source job
        const result = await adminApi.triggerJob({
          source_id: triggerForm.source_id,
          disease_ids: triggerForm.disease_ids,
          options: triggerForm.options
        });
        alert(`✅ Job triggered successfully!\n\nJob ID: ${result.job_id}\nSource: ${result.source}\nDiseases: ${result.diseases.join(', ')}`);
      }
      
      setShowTriggerDialog(false);
      setTriggerForm({
        source_id: 0,
        disease_ids: [],
        job_type: 'full',
        options: {}
      });
      loadJobs();
    } catch (err: any) {
      alert(`❌ Failed to trigger job\n\n${err.response?.data?.detail || err.message}`);
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getProgress = (job: Job) => {
    if (!job.documents_found || job.documents_found === 0) return 0;
    return Math.round((job.documents_processed || 0) / job.documents_found * 100);
  };

  if (loading) return <LoadingSpinner text="Loading jobs..." />;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="jobs-container">
      <div className="jobs-header">
        <h1>Job Management</h1>
        <div className="header-actions">
          <label className="auto-refresh">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>
          <button 
            className="btn-primary"
            onClick={() => setShowTriggerDialog(true)}
          >
            Trigger New Job
          </button>
        </div>
      </div>

      {stats && (
        <div className="jobs-stats">
          <div className="stat-card">
            <h3>{stats.overall.total_jobs}</h3>
            <p>Total Jobs (7d)</p>
          </div>
          <div className="stat-card success">
            <h3>{stats.overall.completed}</h3>
            <p>Completed</p>
          </div>
          <div className="stat-card danger">
            <h3>{stats.overall.failed}</h3>
            <p>Failed</p>
          </div>
          <div className="stat-card info">
            <h3>{stats.overall.running}</h3>
            <p>Running</p>
          </div>
          <div className="stat-card">
            <h3>{formatDuration(stats.overall.avg_duration_seconds)}</h3>
            <p>Avg Duration</p>
          </div>
        </div>
      )}

      <div className="jobs-filters">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="status-filter"
        >
          <option value="">All Statuses</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="source-filter"
        >
          <option value="">All Sources</option>
          {stats?.by_source.map(source => (
            <option key={source.source_name} value={source.source_name}>
              {source.source_name}
            </option>
          ))}
        </select>
        
        <label className="auto-refresh-toggle">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          Auto-refresh (5s)
        </label>
        
        <button 
          className="btn-secondary"
          onClick={loadJobs}
        >
          Refresh Now
        </button>
      </div>

      <div className="jobs-table-container">
        <table className="jobs-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Source</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Documents</th>
              <th>Started</th>
              <th>Duration</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td className="job-id">#{job.id}</td>
                <td className="job-source">{job.source_name}</td>
                <td>
                  <StatusBadge status={job.status} />
                </td>
                <td>
                  {job.status === 'running' && (
                    <div className="progress-bar">
                      <div 
                        className="progress-fill"
                        style={{ width: `${getProgress(job)}%` }}
                      />
                      <span className="progress-text">{getProgress(job)}%</span>
                    </div>
                  )}
                  {job.status !== 'running' && '-'}
                </td>
                <td className="text-center">
                  {job.documents_processed || 0} / {job.documents_found || 0}
                </td>
                <td className="job-date">{formatDate(job.started_at)}</td>
                <td>{formatDuration(job.duration_seconds)}</td>
                <td>
                  <div className="actions">
                    <button
                      onClick={() => setSelectedJob(job)}
                      className="btn-sm"
                    >
                      Details
                    </button>
                    {job.status === 'running' && (
                      <button
                        onClick={() => setCancelConfirm(job)}
                        className="btn-sm btn-danger"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {jobs.length === 0 && (
          <div className="no-jobs">
            No jobs found matching the selected filters.
          </div>
        )}
      </div>

      {/* Recent Errors Section */}
      {stats && stats.recent_errors.length > 0 && (
        <div className="recent-errors">
          <h2>Recent Errors</h2>
          <div className="errors-list">
            {stats.recent_errors.map((error) => (
              <ErrorDetails
                key={error.id}
                error={error.error_sample}
                title={`Job #${error.id} - ${error.source_name}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Job Details Modal */}
      {selectedJob && (
        <div className="modal-overlay" onClick={() => setSelectedJob(null)}>
          <div className="modal-content job-details" onClick={(e) => e.stopPropagation()}>
            <h2>Job Details - #{selectedJob.id}</h2>
            
            <div className="job-info">
              <div className="info-row">
                <span className="label">Source:</span>
                <span className="value">{selectedJob.source_name}</span>
              </div>
              <div className="info-row">
                <span className="label">Status:</span>
                <StatusBadge status={selectedJob.status} />
              </div>
              <div className="info-row">
                <span className="label">Started:</span>
                <span className="value">{formatDate(selectedJob.started_at)}</span>
              </div>
              <div className="info-row">
                <span className="label">Completed:</span>
                <span className="value">{formatDate(selectedJob.completed_at)}</span>
              </div>
              <div className="info-row">
                <span className="label">Duration:</span>
                <span className="value">{formatDuration(selectedJob.duration_seconds)}</span>
              </div>
              <div className="info-row">
                <span className="label">Documents Found:</span>
                <span className="value">{selectedJob.documents_found || 0}</span>
              </div>
              <div className="info-row">
                <span className="label">Documents Processed:</span>
                <span className="value">{selectedJob.documents_processed || 0}</span>
              </div>
              <div className="info-row">
                <span className="label">Errors:</span>
                <span className="value">{selectedJob.errors || 0}</span>
              </div>
            </div>
            
            {selectedJob.config && (
              <div className="job-config">
                <h3>Configuration</h3>
                <pre>{JSON.stringify(selectedJob.config, null, 2)}</pre>
              </div>
            )}
            
            {selectedJob.error_details && selectedJob.error_details.length > 0 && (
              <div className="job-errors">
                <h3>Error Details</h3>
                {selectedJob.error_details.map((error, idx) => (
                  <ErrorDetails key={idx} error={error} expanded={idx === 0} />
                ))}
              </div>
            )}
            
            <div className="form-buttons">
              <button onClick={() => setSelectedJob(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Trigger Job Dialog */}
      {showTriggerDialog && (
        <div className="modal-overlay" onClick={() => setShowTriggerDialog(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Trigger New Scraping Job</h2>
            
            <div className="form-group">
              <label>Source</label>
              <select
                value={triggerForm.source_id}
                onChange={(e) => setTriggerForm({ ...triggerForm, source_id: parseInt(e.target.value) })}
              >
                <option value="0">All Active Sources</option>
                {sources.map(source => (
                  <option key={source.id} value={source.id}>
                    {source.name} ({source.association_method === 'linked' ? '🔗 Linked' : '🔍 Search'})
                  </option>
                ))}
              </select>
            </div>
            
            <div className="form-group">
              <label>Diseases</label>
              <select
                multiple
                value={triggerForm.disease_ids.map(String)}
                onChange={(e) => {
                  const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                  setTriggerForm({ ...triggerForm, disease_ids: selected });
                }}
                style={{ height: '200px' }}
              >
                {diseases.map(disease => (
                  <option key={disease.id} value={disease.id}>
                    {disease.name}
                  </option>
                ))}
              </select>
              <small>Hold Ctrl/Cmd to select multiple diseases. Leave empty for all diseases.</small>
            </div>
            
            {triggerForm.source_id === 0 && (
              <div className="form-group">
                <label>Job Type</label>
                <select
                  value={triggerForm.job_type}
                  onChange={(e) => setTriggerForm({ ...triggerForm, job_type: e.target.value as 'full' | 'incremental' })}
                >
                  <option value="full">Full Scrape</option>
                  <option value="incremental">Incremental Update</option>
                </select>
              </div>
            )}
            
            <div className="form-buttons">
              <button className="btn-primary" onClick={handleTriggerJob}>
                Start Scraping
              </button>
              <button onClick={() => {
                setShowTriggerDialog(false);
                setTriggerForm({
                  source_id: 0,
                  disease_ids: [],
                  job_type: 'full',
                  options: {}
                });
              }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel Confirmation */}
      <ConfirmDialog
        isOpen={!!cancelConfirm}
        title="Cancel Job"
        message={`Are you sure you want to cancel job #${cancelConfirm?.id}? This action cannot be undone.`}
        confirmLabel="Cancel Job"
        variant="warning"
        onConfirm={handleCancelJob}
        onCancel={() => setCancelConfirm(null)}
      />
    </div>
  );
};

export default Jobs;