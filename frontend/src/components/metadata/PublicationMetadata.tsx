import React from 'react';
import './MetadataDisplay.css';

interface PublicationMetadataProps {
  metadata: any;
  title: string;
  summary?: string;
  url?: string;
}

const PublicationMetadata: React.FC<PublicationMetadataProps> = ({ metadata, title, summary, url }) => {
  // Helper to format author names
  const formatAuthors = (authors: any) => {
    if (!authors) return null;
    
    if (Array.isArray(authors)) {
      if (typeof authors[0] === 'string') {
        // Simple author list
        return authors.join(', ');
      } else if (authors[0]?.name) {
        // Detailed author objects
        return authors.map(a => a.name).join(', ');
      }
    }
    return String(authors);
  };

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

  return (
    <div className="metadata-display publication-metadata">
      <h3 className="metadata-title">{title}</h3>
      
      {summary && (
        <div className="metadata-section">
          <h4>Abstract</h4>
          <p className="abstract-text">{summary}</p>
        </div>
      )}

      <div className="metadata-grid">
        {metadata.journal && (
          <div className="metadata-item">
            <span className="metadata-label">Journal</span>
            <span className="metadata-value">{metadata.journal}</span>
          </div>
        )}

        {metadata.publication_date && (
          <div className="metadata-item">
            <span className="metadata-label">Publication Date</span>
            <span className="metadata-value">{formatDate(metadata.publication_date)}</span>
          </div>
        )}

        {metadata.authors && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Authors</span>
            <span className="metadata-value">{formatAuthors(metadata.authors)}</span>
          </div>
        )}

        {metadata.pmid && (
          <div className="metadata-item">
            <span className="metadata-label">PMID</span>
            <a 
              href={`https://pubmed.ncbi.nlm.nih.gov/${metadata.pmid}`}
              target="_blank"
              rel="noopener noreferrer"
              className="metadata-link"
            >
              {metadata.pmid}
            </a>
          </div>
        )}

        {metadata.doi && (
          <div className="metadata-item">
            <span className="metadata-label">DOI</span>
            <a 
              href={`https://doi.org/${metadata.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="metadata-link"
            >
              {metadata.doi}
            </a>
          </div>
        )}

        {metadata.pmc_id && (
          <div className="metadata-item">
            <span className="metadata-label">PMC</span>
            <a 
              href={`https://www.ncbi.nlm.nih.gov/pmc/articles/${metadata.pmc_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="metadata-link"
            >
              {metadata.pmc_id}
            </a>
          </div>
        )}

        {metadata.publication_type && (
          <div className="metadata-item">
            <span className="metadata-label">Publication Type</span>
            <span className="metadata-value">
              {Array.isArray(metadata.publication_type) 
                ? metadata.publication_type.join(', ')
                : metadata.publication_type}
            </span>
          </div>
        )}

        {metadata.mesh_terms && metadata.mesh_terms.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">MeSH Terms</span>
            <div className="tag-list">
              {metadata.mesh_terms.slice(0, 10).map((term: any, index: number) => (
                <span key={index} className="tag">
                  {typeof term === 'string' ? term : term.descriptor_name}
                  {term.is_major_topic && <span className="tag-indicator">*</span>}
                </span>
              ))}
              {metadata.mesh_terms.length > 10 && (
                <span className="tag more">+{metadata.mesh_terms.length - 10} more</span>
              )}
            </div>
          </div>
        )}

        {metadata.keywords && metadata.keywords.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Keywords</span>
            <div className="tag-list">
              {metadata.keywords.map((keyword: string, index: number) => (
                <span key={index} className="tag">{keyword}</span>
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
            View on PubMed
          </a>
        )}
      </div>
    </div>
  );
};

export default PublicationMetadata;