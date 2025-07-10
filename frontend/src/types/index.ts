export interface Document {
  id: number;
  source_id: number;
  source_name: string;
  source_type: 'primary' | 'secondary';
  external_id: string;
  url: string;
  title: string;
  content: string;
  summary: string;
  snippet?: string;
  relevance_score: number;
  created_at: string;
  scraped_at: string;
  metadata: any;
  disease_names?: string[];
  disease_tags?: string[];
  author_names?: string[];
}

export interface SearchResponse {
  results: Document[];
  total: number;
  page: number;
  page_size: number;
  query: string;
  search_type: 'keyword' | 'semantic' | 'hybrid';
}

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

export interface SearchFilters {
  sources?: string[];
  diseases?: string[];
  date_from?: string;
  date_to?: string;
  study_phase?: string[];
  publication_type?: string[];
}

export interface Source {
  id: number;
  name: string;
  type: string;
  base_url: string;
  is_active: boolean;
  document_count?: number;
}