import React from 'react';
import './MetadataDisplay.css';

interface CommunityMetadataProps {
  metadata: any;
  title: string;
  summary?: string;
  url?: string;
}

const CommunityMetadata: React.FC<CommunityMetadataProps> = ({ metadata, title, summary, url }) => {
  // Helper to format date
  const formatDate = (dateStr: string) => {
    if (!dateStr) return null;
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) return 'Today';
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays} days ago`;
      if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
      if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
      
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  // Helper to format engagement ratio
  const formatEngagement = (ratio: number) => {
    if (ratio >= 0.8) return { text: 'Very High', class: 'engagement-very-high' };
    if (ratio >= 0.6) return { text: 'High', class: 'engagement-high' };
    if (ratio >= 0.4) return { text: 'Medium', class: 'engagement-medium' };
    return { text: 'Low', class: 'engagement-low' };
  };

  return (
    <div className="metadata-display community-metadata">
      <h3 className="metadata-title">{title}</h3>
      
      {summary && (
        <div className="metadata-section">
          <h4>Post Content</h4>
          <p className="post-content">{summary}</p>
        </div>
      )}

      <div className="metadata-grid">
        {metadata.community && (
          <div className="metadata-item">
            <span className="metadata-label">Community</span>
            <a 
              href={`https://reddit.com/r/${metadata.community}`}
              target="_blank"
              rel="noopener noreferrer"
              className="metadata-link"
            >
              r/{metadata.community}
            </a>
          </div>
        )}

        {metadata.author && (
          <div className="metadata-item">
            <span className="metadata-label">Author</span>
            <span className="metadata-value">{metadata.author}</span>
          </div>
        )}

        {metadata.created_date && (
          <div className="metadata-item">
            <span className="metadata-label">Posted</span>
            <span className="metadata-value">{formatDate(metadata.created_date)}</span>
          </div>
        )}

        {metadata.score !== undefined && (
          <div className="metadata-item">
            <span className="metadata-label">Score</span>
            <span className="metadata-value score">
              {metadata.score} points
            </span>
          </div>
        )}

        {metadata.reply_count !== undefined && (
          <div className="metadata-item">
            <span className="metadata-label">Comments</span>
            <span className="metadata-value">
              {metadata.reply_count} {metadata.reply_count === 1 ? 'comment' : 'comments'}
            </span>
          </div>
        )}

        {metadata.engagement_ratio !== undefined && (
          <div className="metadata-item">
            <span className="metadata-label">Engagement</span>
            <span className={`engagement-badge ${formatEngagement(metadata.engagement_ratio).class}`}>
              {formatEngagement(metadata.engagement_ratio).text}
            </span>
          </div>
        )}

        {metadata.category && (
          <div className="metadata-item">
            <span className="metadata-label">Flair</span>
            <span className="flair-badge">{metadata.category}</span>
          </div>
        )}

        {metadata.is_original_content && (
          <div className="metadata-item">
            <span className="metadata-label">Type</span>
            <span className="oc-badge">Original Content</span>
          </div>
        )}

        {metadata.top_replies && metadata.top_replies.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Top Comments</span>
            <div className="replies-list">
              {metadata.top_replies.slice(0, 3).map((reply: any, index: number) => (
                <div key={index} className="reply-item">
                  <div className="reply-header">
                    <span className="reply-author">{reply.author}</span>
                    <span className="reply-score">{reply.score} points</span>
                  </div>
                  <p className="reply-content">{reply.body}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {metadata.related_posts && metadata.related_posts.length > 0 && (
          <div className="metadata-item full-width">
            <span className="metadata-label">Related Discussions</span>
            <div className="related-list">
              {metadata.related_posts.slice(0, 3).map((post: any, index: number) => (
                <div key={index} className="related-item">
                  <a 
                    href={post.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="related-link"
                  >
                    {post.title}
                  </a>
                  <span className="related-info">
                    in r/{post.subreddit} • {post.score} points
                  </span>
                </div>
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
            View on Reddit
          </a>
        )}
        {metadata.post_id && (
          <a 
            href={`https://reddit.com${metadata.post_id}`} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="action-button secondary"
          >
            View Thread
          </a>
        )}
      </div>
    </div>
  );
};

export default CommunityMetadata;