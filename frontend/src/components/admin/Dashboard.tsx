import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api/admin';
import './Dashboard.css';

interface DashboardStats {
  overview: {
    sources: number;
    diseases: number;
    documents: number;
    recent_jobs: number;
  };
  job_stats: Array<{
    status: string;
    count: number;
    total_found: number;
    total_processed: number;
    total_errors: number;
  }>;
  top_diseases: Array<{
    name: string;
    document_count: number;
  }>;
  source_activity: Array<{
    name: string;
    last_crawled: string | null;
    document_count: number;
    job_count: number;
  }>;
  last_updated: string;
}

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardStats();
  }, []);

  const loadDashboardStats = async () => {
    try {
      setLoading(true);
      const data = await adminApi.getDashboardStats();
      setStats(data);
    } catch (err) {
      setError('Failed to load dashboard statistics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString();
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) return <div className="loading">Loading dashboard...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!stats) return null;

  return (
    <div className="dashboard">
      <h1>Admin Dashboard</h1>
      
      <div className="overview-cards">
        <div className="stat-card">
          <h3>Active Sources</h3>
          <div className="stat-value">{stats.overview.sources}</div>
        </div>
        <div className="stat-card">
          <h3>Diseases</h3>
          <div className="stat-value">{stats.overview.diseases}</div>
        </div>
        <div className="stat-card">
          <h3>Documents</h3>
          <div className="stat-value">{stats.overview.documents.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <h3>Recent Jobs (24h)</h3>
          <div className="stat-value">{stats.overview.recent_jobs}</div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-section">
          <h2>Job Statistics (Last 7 Days)</h2>
          <table className="stats-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Count</th>
                <th>Documents Found</th>
                <th>Processed</th>
                <th>Errors</th>
              </tr>
            </thead>
            <tbody>
              {stats.job_stats.map((job) => (
                <tr key={job.status}>
                  <td>
                    <span className={`status status-${job.status}`}>
                      {job.status}
                    </span>
                  </td>
                  <td>{job.count}</td>
                  <td>{job.total_found?.toLocaleString() || 0}</td>
                  <td>{job.total_processed?.toLocaleString() || 0}</td>
                  <td>{job.total_errors || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="dashboard-section">
          <h2>Top Diseases by Documents</h2>
          <table className="stats-table">
            <thead>
              <tr>
                <th>Disease</th>
                <th>Documents</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_diseases.map((disease) => (
                <tr key={disease.name}>
                  <td>{disease.name}</td>
                  <td>{disease.document_count.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="dashboard-section full-width">
        <h2>Source Activity</h2>
        <table className="stats-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Last Crawled</th>
              <th>Documents</th>
              <th>Jobs (7d)</th>
            </tr>
          </thead>
          <tbody>
            {stats.source_activity.map((source) => (
              <tr key={source.name}>
                <td>{source.name}</td>
                <td>{formatDate(source.last_crawled)}</td>
                <td>{source.document_count.toLocaleString()}</td>
                <td>{source.job_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="last-updated">
        Last updated: {formatDateTime(stats.last_updated)}
      </div>
    </div>
  );
};

export default Dashboard;