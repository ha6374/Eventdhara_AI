import axios from 'axios'
import type {
  DashboardOverviewResponse,
  CategoryTreeNode,
  ImageListResponse,
  ImageItem,
  ImageMetadata,
  DuplicateComparisonItem,
  SystemSettings,
  DriveStatusResponse,
  DriveFolderItem,
  SheetsExportResponse,
  FeedbackItem,
  ModelEvaluation,
  DynamicSheetsConfig,
  SheetsTestConnectionResult,
  SheetsSyncResult
} from '@/types'

const apiClient = axios.create({
  baseURL:
    import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.PROD
      ? 'https://eventdhara-ai.onrender.com/api/v1'
      : 'http://localhost:8000/api/v1'),
  headers: {
    'Content-Type': 'application/json',
  },
})

export const api = {
  // Dashboard
  async getDashboardOverview(): Promise<DashboardOverviewResponse> {
    const res = await apiClient.get<DashboardOverviewResponse>('/dashboard/overview')
    return res.data
  },

  // Categories
  async getCategoryTree(): Promise<CategoryTreeNode[]> {
    const res = await apiClient.get<CategoryTreeNode[]>('/categories/tree')
    return res.data
  },

  async createCategory(data: { name: string; description?: string; parent_id?: number | null }) {
    const res = await apiClient.post('/categories', data)
    return res.data
  },

  async updateCategory(id: number, data: { name?: string; description?: string; parent_id?: number | null; is_active?: boolean }) {
    const res = await apiClient.put(`/categories/${id}`, data)
    return res.data
  },

  async deleteCategory(id: number) {
    const res = await apiClient.delete(`/categories/${id}`)
    return res.data
  },

  async seedCategories() {
    const res = await apiClient.post('/categories/seed')
    return res.data
  },

  // Uploads
  async uploadImages(files: File[], categoryId?: number | null) {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    if (categoryId) formData.append('category_id', String(categoryId))

    const res = await apiClient.post('/uploads/images', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  async uploadZip(file: File, categoryId?: number | null) {
    const formData = new FormData()
    formData.append('file', file)
    if (categoryId) formData.append('category_id', String(categoryId))

    const res = await apiClient.post('/uploads/zip', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  // Images
  async getImages(params: {
    status?: string
    category_id?: number
    quality_status?: string
    is_duplicate?: boolean
    search?: string
    page?: number
    size?: number
    sort_by?: string
    sort_order?: string
  }): Promise<ImageListResponse> {
    const res = await apiClient.get<ImageListResponse>('/images', { params })
    return res.data
  },

  async getImage(id: number): Promise<ImageItem> {
    const res = await apiClient.get<ImageItem>(`/images/${id}`)
    return res.data
  },

  async updateImageStatus(id: number, status: string, reason?: string, category_id?: number, custom_feedback?: string) {
    const res = await apiClient.patch(`/images/${id}/status`, { status, reason, category_id, custom_feedback })
    return res.data
  },

  async rejectImageWithFeedback(id: number, rejection_reason: string, custom_feedback?: string) {
    const res = await apiClient.post(`/images/${id}/reject`, {
      rejection_reason,
      custom_feedback,
      user_id: 'operator',
    })
    return res.data
  },

  async deleteImage(id: number) {
    const res = await apiClient.delete(`/images/${id}`)
    return res.data
  },

  async bulkImageAction(image_ids: number[], action: string, reason?: string, category_id?: number) {
    const res = await apiClient.post('/images/bulk-action', { image_ids, action, reason, category_id })
    return res.data
  },

  async getFeedbacks(): Promise<FeedbackItem[]> {
    const res = await apiClient.get<FeedbackItem[]>('/images/feedbacks')
    return res.data
  },

  async getModelEvaluation(): Promise<ModelEvaluation> {
    const res = await apiClient.get<ModelEvaluation>('/images/evaluation')
    return res.data
  },

  // Duplicates
  async getDuplicates(): Promise<DuplicateComparisonItem[]> {
    const res = await apiClient.get<DuplicateComparisonItem[]>('/duplicates')
    return res.data
  },

  async resolveDuplicate(id: number, action: 'KEEP_AS_DUPLICATE' | 'FORCE_APPROVE' | 'REJECT') {
    const res = await apiClient.post(`/duplicates/resolve/${id}`, null, {
      params: { action },
    })
    return res.data
  },

  // Metadata
  async getAllMetadata(): Promise<ImageMetadata[]> {
    const res = await apiClient.get<ImageMetadata[]>('/metadata/all')
    return res.data
  },

  async getImageMetadata(imageId: number): Promise<ImageMetadata> {
    const res = await apiClient.get<ImageMetadata>(`/metadata/${imageId}`)
    return res.data
  },

  async generateMetadata(imageId: number): Promise<ImageMetadata> {
    const res = await apiClient.post<ImageMetadata>(`/metadata/generate/${imageId}`)
    return res.data
  },

  async regenerateMetadata(imageId: number): Promise<ImageMetadata> {
    const res = await apiClient.post<ImageMetadata>(`/metadata/regenerate/${imageId}`)
    return res.data
  },

  async updateMetadata(id: number, data: Partial<ImageMetadata>): Promise<ImageMetadata> {
    const res = await apiClient.put<ImageMetadata>(`/metadata/${id}`, data)
    return res.data
  },

  async getCategoryMetadata(categoryId: number): Promise<ImageMetadata[]> {
    const res = await apiClient.get<ImageMetadata[]>(`/metadata/category/${categoryId}`)
    return res.data
  },

  async deleteMetadata(metadataId: number) {
    const res = await apiClient.delete(`/metadata/delete/${metadataId}`)
    return res.data
  },

  async deleteMultipleMetadata(metadataIds: number[]) {
    const res = await apiClient.post('/metadata/delete/bulk', {
      metadata_ids: metadataIds,
    })
    return res.data
  },

  async deleteCategoryMetadata(categoryId: number) {
    const res = await apiClient.delete(`/metadata/category/${categoryId}`)
    return res.data
  },
  async bulkGenerateMetadata() {
    const res = await apiClient.post('/metadata/bulk-generate')
    return res.data
  },

  // Google Drive
  async getDriveStatus(): Promise<DriveStatusResponse> {
    const res = await apiClient.get<DriveStatusResponse>('/google-drive/status')
    return res.data
  },

  async browseDriveFolders(parentId?: string): Promise<DriveFolderItem[]> {
    const res = await apiClient.get<DriveFolderItem[]>('/google-drive/browse-folders', {
      params: { parent_id: parentId },
    })
    return res.data
  },

  async createDriveFolder(name: string, parentId?: string) {
    const res = await apiClient.post('/google-drive/folder', { name, parent_id: parentId })
    return res.data
  },

  async uploadSingleToDrive(imageId: number) {
    const res = await apiClient.post(`/google-drive/upload/${imageId}`)
    return res.data
  },

  async bulkUploadToDrive() {
    const res = await apiClient.post('/google-drive/bulk-upload')
    return res.data
  },

  async syncCategoryFolder(categoryId: number) {
    const res = await apiClient.post(`/google-drive/sync-folder/${categoryId}`)
    return res.data
  },

  async disconnectDrive() {
    const res = await apiClient.post('/google-drive/disconnect')
    return res.data
  },

  async exportToGoogleSheets(categoryId?: number, status?: string, titlePrefix?: string): Promise<SheetsExportResponse> {
    const res = await apiClient.post<SheetsExportResponse>('/google-drive/export-sheets', {
      category_id: categoryId,
      status: status || 'APPROVED',
      title_prefix: titlePrefix || 'EventDhara Catalog',
    })
    return res.data
  },

  // Dynamic User Connected Google Sheets
  async getDynamicSheetsConfig(): Promise<DynamicSheetsConfig> {
    const res = await apiClient.get<DynamicSheetsConfig>('/sheets/config')
    return res.data
  },

  async updateDynamicSheetsConfig(data: { spreadsheet_url: string; worksheet_name?: string }): Promise<DynamicSheetsConfig> {
    const res = await apiClient.post<DynamicSheetsConfig>('/sheets/config', data)
    return res.data
  },

  async getSheetsAuthUrl(redirectUri?: string): Promise<{ success: boolean; auth_url: string }> {
    const params = redirectUri ? { redirect_uri: redirectUri } : {}
    const res = await apiClient.get<{ success: boolean; auth_url: string }>('/sheets/oauth/authorize', { params })
    return res.data
  },

  async testDynamicSheetsConnection(): Promise<SheetsTestConnectionResult> {
    const res = await apiClient.post<SheetsTestConnectionResult>('/sheets/test')
    return res.data
  },

  async disconnectDynamicSheets(): Promise<{ success: boolean; message: string }> {
    const res = await apiClient.post<{ success: boolean; message: string }>('/sheets/disconnect')
    return res.data
  },

  async syncMetadataToDynamicSheets(payload?: { image_ids?: number[]; category_id?: number }): Promise<SheetsSyncResult> {
    const res = await apiClient.post<SheetsSyncResult>('/sheets/sync', payload || {})
    return res.data
  },

  // Processing Queue
  async getProcessingQueue() {
    const res = await apiClient.get('/processing/queue')
    return res.data
  },

  async retryProcessing(imageId: number) {
    const res = await apiClient.post(`/processing/retry/${imageId}`)
    return res.data
  },

  // Reports
  async getReportsSummary() {
    const res = await apiClient.get('/reports/summary')
    return res.data
  },

  // Settings & API Key
  async getSystemSettings(): Promise<SystemSettings> {
    const res = await apiClient.get<SystemSettings>('/settings')
    return res.data
  },

  async testGeminiConnection() {
    const res = await apiClient.post('/settings/test-gemini')
    return res.data
  },

  async updateGeminiApiKey(apiKey: string) {
    const res = await apiClient.post('/settings/gemini-key', { api_key: apiKey })
    return res.data
  },

  async removeGeminiApiKey() {
    const res = await apiClient.delete('/settings/gemini-key')
    return res.data
  },

  async updateSystemSettings(data: Partial<SystemSettings>): Promise<SystemSettings> {
    const res = await apiClient.put<SystemSettings>('/settings', data)
    return res.data
  },
}
