import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface LoginRequest {
  username: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
}

class AdminApi {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load token from localStorage
    this.token = localStorage.getItem('admin_token');
    if (this.token) {
      this.setAuthHeader(this.token);
    }

    // Add response interceptor for auth errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          this.logout();
          window.location.href = '/admin/login';
        }
        return Promise.reject(error);
      }
    );
  }

  private setAuthHeader(token: string) {
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  async login(username: string, password: string): Promise<boolean> {
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await this.client.post<LoginResponse>('/api/admin/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      this.token = response.data.access_token;
      localStorage.setItem('admin_token', this.token);
      this.setAuthHeader(this.token);
      return true;
    } catch (error) {
      console.error('Login failed:', error);
      return false;
    }
  }

  logout() {
    this.token = null;
    localStorage.removeItem('admin_token');
    delete this.client.defaults.headers.common['Authorization'];
  }

  isAuthenticated(): boolean {
    return this.token !== null;
  }

  // Dashboard
  async getDashboardStats() {
    const response = await this.client.get('/api/admin/dashboard/stats');
    return response.data;
  }

  async getHealthCheck() {
    const response = await this.client.get('/api/admin/health');
    return response.data;
  }

  // Sources
  async getSources(params?: { status?: string; type?: string }) {
    const response = await this.client.get('/api/admin/sources', { params });
    return response.data;
  }

  async getSource(id: number) {
    const response = await this.client.get(`/api/admin/sources/${id}`);
    return response.data;
  }

  async createSource(data: any) {
    const response = await this.client.post('/api/admin/sources', data);
    return response.data;
  }

  async updateSource(id: number, data: any) {
    const response = await this.client.patch(`/api/admin/sources/${id}`, data);
    return response.data;
  }

  async deleteSource(id: number) {
    const response = await this.client.delete(`/api/admin/sources/${id}`);
    return response.data;
  }

  async testSourceConnection(id: number) {
    const response = await this.client.post(`/api/admin/sources/${id}/test-connection`);
    return response.data;
  }

  async triggerSourceScrape(sourceId: number, diseaseIds?: number[], options?: any) {
    const response = await this.client.post(`/api/admin/sources/${sourceId}/trigger-scrape`, {
      disease_ids: diseaseIds,
      options
    });
    return response.data;
  }

  // Diseases
  async getDiseases(params?: { category?: string; search?: string; limit?: number; offset?: number }) {
    const response = await this.client.get('/api/admin/diseases', { params });
    return response.data;
  }

  async getDisease(id: number) {
    const response = await this.client.get(`/api/admin/diseases/${id}`);
    return response.data;
  }

  async createDisease(data: any) {
    const response = await this.client.post('/api/admin/diseases', data);
    return response.data;
  }

  async updateDisease(id: number, data: any) {
    const response = await this.client.patch(`/api/admin/diseases/${id}`, data);
    return response.data;
  }

  async deleteDisease(id: number) {
    const response = await this.client.delete(`/api/admin/diseases/${id}`);
    return response.data;
  }

  async getDiseaseCategories() {
    const response = await this.client.get('/api/admin/diseases/categories/list');
    return response.data;
  }


  // Jobs
  async getJobs(params?: {
    source_id?: number;
    status?: string;
    since?: string;
    limit?: number;
    offset?: number;
  }) {
    const response = await this.client.get('/api/admin/jobs', { params });
    return response.data;
  }

  async getJob(id: number) {
    const response = await this.client.get(`/api/admin/jobs/${id}`);
    return response.data;
  }

  async triggerJob(data: { source_id: number; disease_ids: number[]; options?: any }) {
    const response = await this.client.post('/api/admin/jobs/trigger', data);
    return response.data;
  }

  async triggerBulkJobs(data: {
    source_ids: number[];
    disease_ids: number[];
    job_type: 'full' | 'incremental';
    options?: any;
  }) {
    const response = await this.client.post('/api/admin/jobs/trigger-bulk', data);
    return response.data;
  }


  async cancelJob(id: number) {
    const response = await this.client.post(`/api/admin/jobs/${id}/cancel`);
    return response.data;
  }

  async getJobStats(days: number = 7) {
    const response = await this.client.get('/api/admin/jobs/stats/summary', {
      params: { days },
    });
    return response.data;
  }

  // Schedules
  async getSchedules() {
    const response = await this.client.get('/api/admin/schedules');
    return response.data;
  }

  async getSchedule(name: string) {
    const response = await this.client.get(`/api/admin/schedules/${name}`);
    return response.data;
  }

  async updateSchedule(name: string, data: any) {
    const response = await this.client.patch(`/api/admin/schedules/${name}`, data);
    return response.data;
  }

  async runScheduleNow(name: string) {
    const response = await this.client.post(`/api/admin/schedules/${name}/run-now`);
    return response.data;
  }

  async triggerAllSources() {
    const response = await this.client.post('/api/admin/schedules/custom/trigger-all');
    return response.data;
  }

  async getAvailableTasks() {
    const response = await this.client.get('/api/admin/schedules/available-tasks/list');
    return response.data;
  }
}

export const adminApi = new AdminApi();