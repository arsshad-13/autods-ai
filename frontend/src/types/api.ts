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
  status: string; // 'uploaded', 'pending', 'profiling', 'completed', 'failed'
  error_message?: string | null;
  created_at: string;
  updated_at: string;

}

export interface DatasetListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Dataset[];
}

export interface ColumnProfile {
  name: string;
  type: 'numeric' | 'categorical' | 'boolean' | 'datetime';
  missing_count: number;
  missing_percentage: number;
  cardinality: number;
  statistics: {
    mean?: number;
    median?: number;
    mode?: any;
    std?: number;
    var?: number;
    min?: number;
    max?: number;
    q1?: number;
    q3?: number;
    unique_values?: string[];
    most_frequent?: any;
  };
}

export interface DataQuality {
  score: number;
  level: 'Excellent' | 'Good' | 'Fair' | 'Poor';
  penalties: {
    missing_values: {
      penalty: number;
      percentage: number;
      count: number;
    };
    duplicate_rows: {
      penalty: number;
      percentage: number;
      count: number;
    };
    columns: {
      empty: { count: number; penalty: number };
      constant: { count: number; penalty: number };
      high_cardinality: { count: number; penalty: number };
    };
  };
}

export interface MlRecommendation {
  recommended_task: 'Classification' | 'Regression' | 'Clustering' | 'Time Series';
  recommended_target: string | null;
  confidence: number;
  explanation: {
    inferred_target: string | null;
    confidence: number;
    recommended_task: string;
    reasons: string[];
  };
}

export interface DatasetProfile {
  id: number;
  uuid: string;
  dataset_id: number;
  quality_score: number;
  quality_level: 'Excellent' | 'Good' | 'Fair' | 'Poor';
  recommended_task: 'Classification' | 'Regression' | 'Clustering' | 'Time Series';
  recommended_target: string | null;
  row_count: number;
  column_count: number;
  profile_data: {
    general: {
      row_count: number;
      column_count: number;
      memory_usage: number;
      column_types: {
        numeric: string[];
        categorical: string[];
        boolean: string[];
        datetime: string[];
      };
    };
    missing_values: {
      columns: Record<string, { count: number; percentage: number }>;
      total_missing_count: number;
      total_missing_percentage: number;
    };
    duplicates: {
      count: number;
      percentage: number;
    };
    columns: Record<string, ColumnProfile>;
    quality: DataQuality;
    ml_recommendation: MlRecommendation;
    preview: Record<string, any>[];
  };
  created_at: string;
  updated_at: string;
}

export interface RecommendationSchema {
  id: string;
  action: string;
  recommendation: string;
  reason: string;
  affected_columns: string[];
  estimated_impact: string;
}

export interface DatasetPreprocessingResponse {
  uuid: string;
  dataset_id: number;
  recommendations?: RecommendationSchema[];
  actions_applied?: RecommendationSchema[];
  processing_summary?: {
    messages?: string[];
    quality_before?: number;
    quality_after?: number;
  };
  clean_dataset_path?: string;
  quality_before?: number | Record<string, any>;
  quality_after?: number | Record<string, any>;
  processing_time?: number;
  status: 'NOT_GENERATED' | 'PLAN_GENERATED' | 'APPLYING' | 'COMPLETED' | 'FAILED';
  error_message?: string;
  created_at: string;
  updated_at: string;
}
