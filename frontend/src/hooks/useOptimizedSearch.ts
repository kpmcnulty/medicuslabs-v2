import { useState, useCallback, useRef } from 'react';
import axios from 'axios';

interface SearchCache {
  query: any;
  results: any[];
  totalCount: number;
  timestamp: number;
}

interface SortCache {
  [sortKey: string]: SearchCache;
}

const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
const PREFETCH_THRESHOLD = 100; // Use client-side sorting for datasets under this size

export const useOptimizedSearch = (api: any) => {
  const [cache, setCache] = useState<SortCache>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isPrefetching, setIsPrefetching] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Generate cache key from query and sort parameters
  const getCacheKey = (query: any, sortBy?: string, sortOrder?: string) => {
    const sortKey = sortBy ? `${sortBy}_${sortOrder}` : 'default';
    return `${JSON.stringify(query)}_${sortKey}`;
  };

  // Check if cache is still valid
  const isCacheValid = (cacheEntry: SearchCache) => {
    return Date.now() - cacheEntry.timestamp < CACHE_DURATION;
  };

  // Optimized search function
  const searchOptimized = useCallback(async (
    query: any,
    pagination: { pageIndex: number; pageSize: number },
    sorting?: { id: string; desc: boolean }[]
  ) => {
    // Cancel any pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    const sortBy = sorting?.[0]?.id;
    const sortOrder = sorting?.[0]?.desc ? 'desc' : 'asc';
    const cacheKey = getCacheKey(query, sortBy, sortOrder);

    // Check cache first
    const cachedData = cache[cacheKey];
    if (cachedData && isCacheValid(cachedData)) {
      // If we have all data cached and it's a small dataset, return paginated slice
      if (cachedData.totalCount <= PREFETCH_THRESHOLD) {
        const start = pagination.pageIndex * pagination.pageSize;
        const end = start + pagination.pageSize;
        return {
          results: cachedData.results.slice(start, end),
          total: cachedData.totalCount,
          fromCache: true
        };
      }
    }

    setIsLoading(true);
    
    try {
      // For small datasets, fetch all at once
      if (!cachedData && pagination.pageIndex === 0) {
        // Do a quick count query first
        const countQuery = { ...query, limit: 1, offset: 0 };
        const countResponse = await api.post('/api/search/unified', countQuery, {
          signal: abortControllerRef.current.signal
        });
        
        const totalCount = countResponse.data.total;
        
        // If small dataset, fetch all and cache
        if (totalCount <= PREFETCH_THRESHOLD) {
          setIsPrefetching(true);
          const fullQuery = {
            ...query,
            limit: totalCount,
            offset: 0,
            sort_by: sortBy,
            sort_order: sortOrder
          };
          
          const fullResponse = await api.post('/api/search/unified', fullQuery, {
            signal: abortControllerRef.current.signal
          });
          
          // Cache the full results
          const newCache = {
            query,
            results: fullResponse.data.results,
            totalCount,
            timestamp: Date.now()
          };
          
          setCache(prev => ({ ...prev, [cacheKey]: newCache }));
          setIsPrefetching(false);
          
          // Return paginated slice
          const start = pagination.pageIndex * pagination.pageSize;
          const end = start + pagination.pageSize;
          return {
            ...fullResponse.data,
            results: fullResponse.data.results.slice(start, end),
            fromCache: true
          };
        }
      }
      
      // For large datasets or non-cached queries, use standard pagination
      const paginatedQuery = {
        ...query,
        limit: pagination.pageSize,
        offset: pagination.pageIndex * pagination.pageSize,
        sort_by: sortBy,
        sort_order: sortOrder
      };
      
      const response = await api.post('/api/search/unified', paginatedQuery, {
        signal: abortControllerRef.current.signal
      });
      
      return { ...response.data, fromCache: false };
      
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        throw error;
      }
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [api, cache]);

  // Clear cache when needed
  const clearCache = useCallback(() => {
    setCache({});
  }, []);

  // Prefetch next page for smooth pagination
  const prefetchPage = useCallback(async (
    query: any,
    nextPageIndex: number,
    pageSize: number,
    sorting?: { id: string; desc: boolean }[]
  ) => {
    const sortBy = sorting?.[0]?.id;
    const sortOrder = sorting?.[0]?.desc ? 'desc' : 'asc';
    const cacheKey = getCacheKey(query, sortBy, sortOrder);
    
    // Only prefetch if we don't have cached full results
    const cachedData = cache[cacheKey];
    if (cachedData && cachedData.totalCount <= PREFETCH_THRESHOLD) {
      return; // Already have all data
    }
    
    // Prefetch in background
    const prefetchQuery = {
      ...query,
      limit: pageSize,
      offset: nextPageIndex * pageSize,
      sort_by: sortBy,
      sort_order: sortOrder
    };
    
    api.post('/api/search/unified', prefetchQuery).catch(() => {
      // Silently fail prefetch
    });
  }, [api, cache]);

  return {
    searchOptimized,
    clearCache,
    prefetchPage,
    isLoading,
    isPrefetching,
    cache
  };
};