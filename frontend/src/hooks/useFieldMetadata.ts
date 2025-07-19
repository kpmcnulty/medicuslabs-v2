import { useState, useEffect } from 'react';
import axios from 'axios';
import { FieldMetadata } from '../components/QueryBuilder';

interface UseFieldMetadataOptions {
  sourceCategory?: string;
  source?: string;
  autoFetch?: boolean;
}

interface UseFieldMetadataResult {
  fields: FieldMetadata[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
  categories: Record<string, string>;
  operators: Record<string, string[]>;
}

// Configure axios with the API base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const useFieldMetadata = (options: UseFieldMetadataOptions = {}): UseFieldMetadataResult => {
  const { sourceCategory, source, autoFetch = true } = options;
  
  const [fields, setFields] = useState<FieldMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<Record<string, string>>({});
  const [operators, setOperators] = useState<Record<string, string[]>>({});

  const fetchFieldMetadata = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (sourceCategory) {
        params.append('source_category', sourceCategory);
      }
      if (source) {
        params.append('source', source);
      }

      const response = await api.get(`/api/search/unified/suggest?${params.toString()}`);
      const data = response.data;

      // Transform backend response to frontend format
      const transformedFields: FieldMetadata[] = data.fields.map((field: any) => ({
        name: field.name,
        label: field.label || field.name.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()),
        type: field.type || 'string',
        category: field.category || 'other',
        description: field.description || undefined,
        operators: field.operators || [],
        sampleValues: field.sample_values?.map((sample: any) => 
          typeof sample === 'object' ? sample.value : sample
        ) || undefined,
        // Additional metadata from backend
        documentCount: field.document_count,
        uniqueValues: field.unique_values,
        sourceCategories: field.source_categories
      }));

      setFields(transformedFields);
      setCategories(data.categories || {});
      setOperators(data.operators || {});
    } catch (err) {
      console.error('Failed to fetch field metadata:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch field metadata');
      
      // Fallback to basic field metadata
      setFields(getFallbackFields());
      setCategories(getFallbackCategories());
      setOperators(getFallbackOperators());
    } finally {
      setLoading(false);
    }
  };

  // Fallback field metadata if API call fails
  const getFallbackFields = (): FieldMetadata[] => [
    {
      name: 'title',
      label: 'Title',
      type: 'string',
      category: 'core',
      description: 'Document title',
      operators: ['$eq', '$ne', '$contains', '$startsWith', '$endsWith', '$regex', '$exists']
    },
    {
      name: 'source',
      label: 'Source',
      type: 'string', 
      category: 'core',
      description: 'Data source name',
      operators: ['$eq', '$ne', '$contains', '$in', '$nin', '$exists']
    },
    {
      name: 'created_at',
      label: 'Scraped Date',
      type: 'date',
      category: 'dates',
      description: 'Date when document was scraped/collected',
      operators: ['$eq', '$ne', '$gt', '$gte', '$lt', '$lte', '$between', '$exists']
    },
    {
      name: 'summary',
      label: 'Summary',
      type: 'string',
      category: 'core',
      description: 'Document summary',
      operators: ['$eq', '$ne', '$contains', '$regex', '$exists']
    }
  ];

  const getFallbackCategories = (): Record<string, string> => ({
    core: 'Core Fields',
    dates: 'Date Fields',
    publication: 'Publication Data',
    trial: 'Clinical Trial Data',
    community: 'Community Data',
    faers: 'Adverse Event Data',
    identifiers: 'Identifiers',
    other: 'Other Fields'
  });

  const getFallbackOperators = (): Record<string, string[]> => ({
    string: ['$eq', '$ne', '$contains', '$startsWith', '$endsWith', '$regex', '$in', '$nin', '$exists'],
    number: ['$eq', '$ne', '$gt', '$gte', '$lt', '$lte', '$between', '$in', '$nin', '$exists'],
    date: ['$eq', '$ne', '$gt', '$gte', '$lt', '$lte', '$between', '$exists'],
    array: ['$contains', '$all', '$in', '$nin', '$exists'],
    object: ['$exists'],
    boolean: ['$eq', '$ne', '$exists']
  });

  const refetch = () => {
    fetchFieldMetadata();
  };

  // Auto-fetch on mount and when dependencies change
  useEffect(() => {
    if (autoFetch) {
      fetchFieldMetadata();
    }
  }, [sourceCategory, source, autoFetch]);

  return {
    fields,
    loading,
    error,
    refetch,
    categories,
    operators
  };
};

export default useFieldMetadata;