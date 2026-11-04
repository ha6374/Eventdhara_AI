export interface DashboardStats {
  total_images: number
  approved: number
  rejected: number
  review_required: number
  duplicates: number
  metadata_completed: number
  pending_metadata: number
  drive_uploads: number
}

export interface DailyProcessingVolume {
  date: string
  total: number
  approved: number
  rejected: number
  review_required: number
  duplicates: number
}

export interface CategoryDistributionItem {
  category_id?: number | null
  category_name: string
  count: number
  percentage: number
}

export interface QualityDistribution {
  passed: number
  failed: number
  average_blur_score: number
}

export interface ProcessingPerformance {
  average_duration_ms: number
  fastest_duration_ms: number
  slowest_duration_ms: number
}

export interface RecentActivityItem {
  id: number
  filename: string
  category: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'REVIEW_REQUIRED' | 'DUPLICATE'
  created_at: string
  processing_duration_ms?: number | null
  quality_status: string
}

export interface DashboardOverviewResponse {
  stats: DashboardStats
  daily_volume: DailyProcessingVolume[]
  category_distribution: CategoryDistributionItem[]
  quality_distribution: QualityDistribution
  processing_performance: ProcessingPerformance
  recent_activity: RecentActivityItem[]
}

export interface CategoryTreeNode {
  id: number
  name: string
  slug: string
  description?: string | null
  parent_id?: number | null
  is_active: boolean
  image_count: number
  depth: number
  children: CategoryTreeNode[]
}

export interface ImageItem {
  id: number
  uuid: string
  filename: string
  original_filename: string
  file_path: string
  storage_path: string
  file_size: number
  width: number
  height: number
  format: string
  sha256: string
  phash: string
  blur_score?: number | null
  quality_status: 'PASSED' | 'FAILED' | 'PENDING'
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'REVIEW_REQUIRED' | 'DUPLICATE'
  rejection_reason?: string | null
  review_reason?: string | null
  is_duplicate: boolean
  duplicate_of_id?: number | null
  duplicate_similarity?: number | null
  duplicate_type?: string | null
  ai_classification?: string | null
  ai_confidence?: number | null
  category_id?: number | null
  category_name?: string | null
  metadata_status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  drive_status: 'PENDING' | 'UPLOADING' | 'COMPLETED' | 'FAILED'
  drive_file_id?: string | null
  drive_url?: string | null
  drive_uploaded_at?: string | null
  batch_id?: string | null
  processing_duration_ms?: number | null
  created_at: string
  updated_at: string
}

export interface ImageListResponse {
  items: ImageItem[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ImageMetadata {
  id: number
  image_id: number
  name: string
  short_description: string
  long_description: string
  inclusion: string[]
  faq: { question: string; answer: string }[]
  note?: string | null
  keywords: string[]
  tags: string[]
  custom_fields?: Record<string, any> | null
  created_at: string
  updated_at: string
  image_filename?: string | null
  original_filename?: string | null
  image_url?: string | null
  photo?: string | null
  category_name?: string | null
  approval_status?: string | null
  processing_status?: string | null
}

export interface DuplicateComparisonItem {
  duplicate_image: ImageItem
  original_image?: ImageItem | null
  similarity_percentage: number
  duplicate_type: string
}

export interface SystemSettings {
  min_image_width: number
  min_image_height: number
  min_file_size_kb: number
  blur_threshold: number
  phash_threshold: number
  ai_confidence_threshold: number
  gemini_model: string
  gemini_api_key_configured: boolean
  google_drive_configured: boolean
  storage_root: string
  environment: string
}

export interface DriveStatusResponse {
  connected: boolean
  status: string
  email?: string
  display_name?: string
  photo_url?: string
  drive_root?: string
  root_folder_id?: string
  root_folder_name?: string
  storage_used_gb?: number
  storage_limit_gb?: number | string
  total_approved: number
  synced_to_drive: number
  pending_sync: number
  failed_sync: number
  message?: string
}

export interface DriveFolderItem {
  id: string
  name: string
  modifiedTime?: string
}

export interface SheetsExportResponse {
  success: boolean
  status: string
  sheet_id?: string
  sheet_title?: string
  sheet_url?: string
  total_rows: number
  message: string
}

export interface FeedbackItem {
  id: number
  image_id: number
  original_filename: string
  original_category?: string | null
  predicted_category?: string | null
  rejection_reason: string
  custom_feedback?: string | null
  insights?: string | null
  created_at: string
}

export interface ModelEvaluation {
  total_evaluated: number
  approved_count: number
  rejected_count: number
  review_count: number
  total_feedbacks: number
  precision: number
  recall: number
  f1_score: number
  accuracy: number
  model_version: string
  active_learning_status: string
}
