import axios from 'axios'
import type {
  DashboardOverviewResponse,
  CategoryTreeNode,
  ImageListResponse,
  ImageItem,
  ImageMetadata,
  DuplicateComparisonItem,
  SystemSettings
} from '@/types'

const apiClient = axios.create({
  baseURL: '/api/v1',
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

  async updateImageStatus(id: number, status: string, reason?: string, category_id?: number) {
    const res = await apiClient.patch(`/images/${id}/status`, { status, reason, category_id })
    return res.data
  },

  async bulkImageAction(image_ids: number[], action: string, reason?: string, category_id?: number) {
    const res = await apiClient.post('/images/bulk-action', { image_ids, action, reason, category_id })
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

  async updateMetadata(id: number, data: Partial<ImageMetadata>): Promise<ImageMetadata> {
    const res = await apiClient.put<ImageMetadata>(`/metadata/${id}`, data)
    return res.data
  },

  async bulkGenerateMetadata() {
    const res = await apiClient.post('/metadata/bulk-generate')
    return res.data
  },

  // Google Drive
  async getDriveStatus() {
    const res = await apiClient.get('/google-drive/status')
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

  // Settings
  async getSystemSettings(): Promise<SystemSettings> {
    const res = await apiClient.get<SystemSettings>('/settings')
    return res.data
  },

  async updateSystemSettings(data: Partial<SystemSettings>): Promise<SystemSettings> {
    const res = await apiClient.put<SystemSettings>('/settings', data)
    return res.data
  },
}
