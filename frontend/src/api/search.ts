import axios from 'axios';
import { SearchResponse, SearchFilters, FilterOption, Source } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const searchAPI = {
  search: async (
    query: string,
    filters?: SearchFilters,
    page: number = 1,
    pageSize: number = 20,
    searchType: 'keyword' | 'semantic' | 'hybrid' = 'keyword'
  ): Promise<SearchResponse> => {
    const params = new URLSearchParams({
      q: query,
      page: page.toString(),
      limit: pageSize.toString(),
      search_type: searchType,
    });

    if (filters?.sources?.length) {
      params.append('sources', filters.sources.join(','));
    }
    if (filters?.diseases?.length) {
      params.append('diseases', filters.diseases.join(','));
    }
    if (filters?.date_from) {
      params.append('date_from', filters.date_from);
    }
    if (filters?.date_to) {
      params.append('date_to', filters.date_to);
    }

    const response = await api.get(`/api/search/?${params}`);
    return response.data;
  },

  getSources: async (): Promise<Source[]> => {
    const response = await api.get('/api/sources/');
    return response.data;
  },

  getFilterOptions: async (): Promise<{
    sources: FilterOption[];
    diseases: FilterOption[];
  }> => {
    const response = await api.get('/api/search/filters/');
    return response.data;
  },

  getSuggestions: async (query: string): Promise<string[]> => {
    const response = await api.get('/api/search/suggestions/', {
      params: { q: query },
    });
    return response.data.suggestions;
  },
};