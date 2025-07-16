import React from 'react';
import './MetadataDisplay.css';

interface FAERSMetadataProps {
  metadata: any;
  title: string;
  summary?: string;
  url?: string;
}

const FAERSMetadata: React.FC<FAERSMetadataProps> = ({ metadata, title, summary, url }) => {
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

  // Helper to get seriousness color
  const getSeriousnessClass = (criteria: any) => {
    if (!criteria || typeof criteria !== 'object') return '';
    
    if (criteria.death || criteria.life_threatening) return 'seriousness-critical';
    if (criteria.hospitalization || criteria.disability) return 'seriousness-severe';
    if (criteria.congenital_anomaly || criteria.other) return 'seriousness-moderate';
    return '';
  };

  // Helper to format seriousness criteria
  const formatSeriousness = (criteria: any) => {
    if (!criteria || typeof criteria !== 'object') return 'Not specified';
    
    const serious = [];
    if (criteria.death) serious.push('Death');
    if (criteria.life_threatening) serious.push('Life Threatening');
    if (criteria.hospitalization) serious.push('Hospitalization');
    if (criteria.disability) serious.push('Disability');
    if (criteria.congenital_anomaly) serious.push('Congenital Anomaly');
    if (criteria.other) serious.push('Other Serious');
    
    return serious.length > 0 ? serious.join(', ') : 'Non-serious';
  };

  return (
    <div className="metadata-display faers-metadata">
      <h3 className="metadata-title">{title}</h3>
      
      {summary && (
        <div className="metadata-section">
          <h4>Report Summary</h4>
          <p className="summary-text">{summary}</p>
        </div>
      )}

      <div className="metadata-grid">
        {metadata.safety_report_id && (
          <div className="metadata-item">
            <span className="metadata-label">Report ID</span>
            <span className="metadata-value">{metadata.safety_report_id}</span>
          </div>
        )}

        {metadata.receive_date && (
          <div className="metadata-item">
            <span className="metadata-label">Report Date</span>
            <span className="metadata-value">{formatDate(metadata.receive_date)}</span>
          </div>
        )}

        {metadata.report_type && (
          <div className="metadata-item">
            <span className="metadata-label">Report Type</span>
            <span className="metadata-value">{metadata.report_type}</span>
          </div>
        )}

        {metadata.reporter_country && (
          <div className="metadata-item">
            <span className="metadata-label">Country</span>
            <span className="metadata-value">{metadata.reporter_country}</span>
          </div>
        )}

        {metadata.seriousness_criteria && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Seriousness</span>
            <span className={`seriousness-badge ${getSeriousnessClass(metadata.seriousness_criteria)}`}>
              {formatSeriousness(metadata.seriousness_criteria)}
            </span>
          </div>
        )}

        {metadata.patient && (
          <>
            {metadata.patient.age && (
              <div className="metadata-item">
                <span className="metadata-label">Patient Age</span>
                <span className="metadata-value">
                  {metadata.patient.age.value} {metadata.patient.age.unit}
                </span>
              </div>
            )}

            {metadata.patient.sex && (
              <div className="metadata-item">
                <span className="metadata-label">Patient Sex</span>
                <span className="metadata-value">{metadata.patient.sex}</span>
              </div>
            )}

            {metadata.patient.weight && (
              <div className="metadata-item">
                <span className="metadata-label">Patient Weight</span>
                <span className="metadata-value">
                  {metadata.patient.weight.value} {metadata.patient.weight.unit}
                </span>
              </div>
            )}
          </>
        )}

        {metadata.reactions && metadata.reactions.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Reactions</span>
            <div className="reaction-list">
              {metadata.reactions.slice(0, 5).map((reaction: any, index: number) => (
                <div key={index} className="reaction-item">
                  <span className="reaction-name">{reaction.reaction_meddra_pt}</span>
                  {reaction.reaction_outcome && (
                    <span className="reaction-outcome">Outcome: {reaction.reaction_outcome}</span>
                  )}
                </div>
              ))}
              {metadata.reactions.length > 5 && (
                <div className="more-text">+{metadata.reactions.length - 5} more reactions</div>
              )}
            </div>
          </div>
        )}

        {metadata.drugs && metadata.drugs.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Drugs</span>
            <div className="drug-list">
              {metadata.drugs.slice(0, 3).map((drug: any, index: number) => (
                <div key={index} className="drug-item">
                  <div className="drug-name">
                    {typeof drug === 'string' ? drug : (drug.drug_name || drug.medicinal_product || 'Unknown drug')}
                    {typeof drug === 'object' && drug.drug_characterization && (
                      <span className="drug-type"> ({drug.drug_characterization})</span>
                    )}
                  </div>
                  {typeof drug === 'object' && drug.drug_indication && (
                    <div className="drug-indication">Indication: {drug.drug_indication}</div>
                  )}
                  {typeof drug === 'object' && drug.drug_dosage && (
                    <div className="drug-dosage">
                      Dose: {drug.drug_dosage.dose_amount} {drug.drug_dosage.dose_unit}
                      {drug.drug_dosage.dose_frequency && ` - ${drug.drug_dosage.dose_frequency}`}
                    </div>
                  )}
                </div>
              ))}
              {metadata.drugs.length > 3 && (
                <div className="more-text">+{metadata.drugs.length - 3} more drugs</div>
              )}
            </div>
          </div>
        )}

        {metadata.reporter_qualification && (
          <div className="metadata-item">
            <span className="metadata-label">Reporter</span>
            <span className="metadata-value">{metadata.reporter_qualification}</span>
          </div>
        )}

        {metadata.outcomes && metadata.outcomes.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Outcomes</span>
            <div className="tag-list">
              {metadata.outcomes.map((outcome: string, index: number) => (
                <span key={index} className="tag outcome-tag">{outcome}</span>
              ))}
            </div>
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
            View Full Report
          </a>
        )}
        <a 
          href="https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard" 
          target="_blank" 
          rel="noopener noreferrer" 
          className="action-button secondary"
        >
          FAERS Dashboard
        </a>
      </div>
    </div>
  );
};

export default FAERSMetadata;