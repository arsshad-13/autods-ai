export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
}

export interface Dataset {
  id: number;
  uuid: string;
  original_filename: string;
  file_size: number;
  mime_type: string;
  extension: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Dataset[];
}

