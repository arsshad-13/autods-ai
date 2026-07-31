import axios from 'axios';
import { useAuthStore } from './store';
import { HealthResponse, Dataset, DatasetListResponse, DatasetProfile, DatasetPreprocessingResponse } from '@/types/api';

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const accessToken = useAuthStore.getState().accessToken;
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const { refreshToken, logout } = useAuthStore.getState();

      if (refreshToken) {
        try {
          const response = await axios.post(
            `${api.defaults.baseURL}/api/v1/auth/refresh`,
            { refresh_token: refreshToken }
          );

          const { access_token, refresh_token } = response.data;

          useAuthStore.setState({
            accessToken: access_token,
            refreshToken: refresh_token,
          });

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          logout();
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      } else {
        logout();
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

export async function getHealth(): Promise<HealthResponse> {
  try {
    const res = await api.get('/api/v1/health');
    return res.data;
  } catch (error) {
    console.error("Health check failed:", error);
    throw new ApiError("Failed to fetch health status");
  }
}

// Dataset APIs
export async function uploadDataset(file: File): Promise<Dataset> {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await api.post('/api/v1/datasets/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to upload dataset");
  }
}

export async function listDatasets(page: number = 1, pageSize: number = 20): Promise<DatasetListResponse> {
  try {
    const res = await api.get('/api/v1/datasets/', {
      params: { page, page_size: pageSize },
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Expires': '0',
      }
    });
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to list datasets");
  }
}

export async function getDataset(uuid: string): Promise<Dataset> {
  try {
    const res = await api.get(`/api/v1/datasets/${uuid}`, {
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Expires': '0',
      }
    });
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to get dataset");
  }
}

export async function deleteDataset(uuid: string): Promise<void> {
  try {
    await api.delete(`/api/v1/datasets/${uuid}`);
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to delete dataset");
  }
}

export async function getDatasetProfile(uuid: string): Promise<DatasetProfile> {
  try {
    const res = await api.get(`/api/v1/datasets/${uuid}/profile`, {
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Expires': '0',
      }
    });
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to retrieve dataset profile");
  }
}

export async function generateDatasetProfile(uuid: string): Promise<Dataset> {
  try {
    const res = await api.post(`/api/v1/datasets/${uuid}/profile`);
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to trigger dataset analysis");
  }
}

// Preprocessing APIs
export async function getPreprocessingPlan(uuid: string): Promise<DatasetPreprocessingResponse> {
  try {
    const res = await api.get(`/api/v1/datasets/${uuid}/preprocess/plan`, {
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Expires': '0',
      }
    });
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to retrieve preprocessing plan");
  }
}

export async function generatePreprocessingPlan(uuid: string): Promise<DatasetPreprocessingResponse> {
  try {
    const res = await api.post(`/api/v1/datasets/${uuid}/preprocess/plan`);
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to generate preprocessing plan");
  }
}

export async function applyPreprocessingPlan(uuid: string, selectedActions: string[]): Promise<DatasetPreprocessingResponse> {
  try {
    const res = await api.post(`/api/v1/datasets/${uuid}/preprocess/apply`, {
      selected_actions: selectedActions
    });
    return res.data;
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to apply preprocessing");
  }
}

export async function downloadCleanedDataset(uuid: string): Promise<void> {
  try {
    const res = await api.get(`/api/v1/datasets/${uuid}/preprocess/download`, {
      responseType: 'blob',
    });
    
    let filename = `cleaned_dataset.csv`;
    const disposition = res.headers['content-disposition'];
    if (disposition && disposition.indexOf('attachment') !== -1) {
      const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
      const matches = filenameRegex.exec(disposition);
      if (matches != null && matches[1]) { 
        filename = matches[1].replace(/['"]/g, '');
      }
    }
    
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.parentNode?.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error: any) {
    throw new ApiError(error.response?.data?.detail || "Failed to download dataset");
  }
}
