import React from 'react';
import './MetadataDisplay.css';

interface ClinicalTrialMetadataProps {
  metadata: any;
  title: string;
  summary?: string;
  url?: string;
}

const ClinicalTrialMetadata: React.FC<ClinicalTrialMetadataProps> = ({ metadata, title, summary, url }) => {
  // Helper to format date
  const formatDate = (dateStr: string) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  // Helper to get status color
  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase() || '';
    if (statusLower.includes('recruiting')) return 'status-recruiting';
    if (statusLower.includes('completed')) return 'status-completed';
    if (statusLower.includes('terminated')) return 'status-terminated';
    if (statusLower.includes('withdrawn')) return 'status-withdrawn';
    return 'status-other';
  };

  return (
    <div className="metadata-display clinical-trial-metadata">
      <h3 className="metadata-title">{title}</h3>
      
      {summary && (
        <div className="metadata-section">
          <h4>Brief Summary</h4>
          <p className="summary-text">{summary}</p>
        </div>
      )}

      <div className="metadata-grid">
        {metadata.nct_id && (
          <div className="metadata-item">
            <span className="metadata-label">NCT Number</span>
            <a 
              href={`https://clinicaltrials.gov/ct2/show/${metadata.nct_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="metadata-link"
            >
              {metadata.nct_id}
            </a>
          </div>
        )}

        {metadata.status && (
          <div className="metadata-item">
            <span className="metadata-label">Status</span>
            <span className={`status-badge ${getStatusColor(metadata.status)}`}>
              {metadata.status}
            </span>
          </div>
        )}

        {(metadata.phase || metadata.study_phase || metadata.phases) && (
          <div className="metadata-item">
            <span className="metadata-label">Phase</span>
            <span className="metadata-value">
              {Array.isArray(metadata.phase) 
                ? metadata.phase.join(', ') 
                : (metadata.phase || metadata.study_phase || (Array.isArray(metadata.phases) ? metadata.phases.join(', ') : metadata.phases))
              }
            </span>
          </div>
        )}

        {(metadata.enrollment || metadata.enrollment_count || metadata.target_enrollment) && (
          <div className="metadata-item">
            <span className="metadata-label">Enrollment</span>
            <span className="metadata-value">
              {metadata.enrollment || metadata.enrollment_count || metadata.target_enrollment} participants
            </span>
          </div>
        )}

        {(metadata.start_date || metadata.study_start_date) && (
          <div className="metadata-item">
            <span className="metadata-label">Start Date</span>
            <span className="metadata-value">{formatDate(metadata.start_date || metadata.study_start_date)}</span>
          </div>
        )}

        {(metadata.completion_date || metadata.study_completion_date || metadata.primary_completion_date) && (
          <div className="metadata-item">
            <span className="metadata-label">Completion Date</span>
            <span className="metadata-value">{formatDate(metadata.completion_date || metadata.study_completion_date || metadata.primary_completion_date)}</span>
          </div>
        )}

        {metadata.sponsors && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Sponsors</span>
            <span className="metadata-value">
              {metadata.sponsors.lead_sponsor?.agency || 'Not specified'}
              {metadata.sponsors.collaborators && metadata.sponsors.collaborators.length > 0 && 
                ` (+ ${metadata.sponsors.collaborators.length} collaborators)`}
            </span>
          </div>
        )}

        {metadata.conditions && metadata.conditions.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Conditions</span>
            <div className="tag-list">
              {metadata.conditions.map((condition: string, index: number) => (
                <span key={index} className="tag">{condition}</span>
              ))}
            </div>
          </div>
        )}

        {metadata.interventions && metadata.interventions.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Interventions</span>
            <div className="intervention-list">
              {metadata.interventions.slice(0, 3).map((intervention: any, index: number) => (
                <div key={index} className="intervention-item">
                  <strong>{typeof intervention === 'string' ? 'Intervention' : (intervention.intervention_type || 'Intervention')}:</strong> {typeof intervention === 'string' ? intervention : (intervention.intervention_name || intervention.name || 'Unknown intervention')}
                </div>
              ))}
              {metadata.interventions.length > 3 && (
                <div className="more-text">+{metadata.interventions.length - 3} more interventions</div>
              )}
            </div>
          </div>
        )}

        {metadata.eligibility && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Eligibility</span>
            <div className="eligibility-info">
              {metadata.eligibility.minimum_age && (
                <span>Age: {metadata.eligibility.minimum_age} - {metadata.eligibility.maximum_age || 'N/A'}</span>
              )}
              {metadata.eligibility.gender && (
                <span>Gender: {metadata.eligibility.gender}</span>
              )}
              {metadata.eligibility.healthy_volunteers && (
                <span>Healthy Volunteers: {metadata.eligibility.healthy_volunteers}</span>
              )}
            </div>
          </div>
        )}

        {metadata.primary_outcomes && metadata.primary_outcomes.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Primary Outcomes</span>
            <ul className="outcome-list">
              {metadata.primary_outcomes.slice(0, 2).map((outcome: any, index: number) => (
                <li key={index}>
                  {outcome.measure}
                  {outcome.time_frame && <span className="time-frame"> ({outcome.time_frame})</span>}
                </li>
              ))}
              {metadata.primary_outcomes.length > 2 && (
                <li className="more-text">+{metadata.primary_outcomes.length - 2} more outcomes</li>
              )}
            </ul>
          </div>
        )}

        {metadata.locations && metadata.locations.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Locations</span>
            <span className="metadata-value">
              {metadata.locations.length} site{metadata.locations.length !== 1 ? 's' : ''} in{' '}
              {Array.from(new Set(metadata.locations.map((loc: any) => loc.country))).join(', ')}
            </span>
          </div>
        )}
      </div>

      <div className="metadata-actions">
        {url && (
          <a 
            href={url} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="action-button primary"
          >
            View on ClinicalTrials.gov
          </a>
        )}
      </div>
    </div>
  );
};

export default ClinicalTrialMetadata;