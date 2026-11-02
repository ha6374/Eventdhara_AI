import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '@/layouts/AppLayout'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { CategoryPage } from '@/features/categories/CategoryPage'
import { UploadPage } from '@/features/uploads/UploadPage'
import { ProcessingQueuePage } from '@/features/processing/ProcessingQueuePage'
import { GalleryView } from '@/features/galleries/GalleryView'
import { DuplicatePage } from '@/features/duplicates/DuplicatePage'
import { MetadataStudioPage } from '@/features/metadata/MetadataStudioPage'
import { GoogleDrivePage } from '@/features/google-drive/GoogleDrivePage'
import { AnalyticsPage } from '@/features/analytics/AnalyticsPage'
import { ReportsPage } from '@/features/reports/ReportsPage'
import { SettingsPage } from '@/features/settings/SettingsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5000,
      retry: 1,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="uploads" element={<UploadPage />} />
            <Route path="processing" element={<ProcessingQueuePage />} />
            <Route path="categories" element={<CategoryPage />} />
            <Route
              path="galleries/approved"
              element={
                <GalleryView
                  status="APPROVED"
                  title="Approved Gallery"
                  description="Curated collection of decoration photographs approved for metadata generation and Google Drive sync."
                />
              }
            />
            <Route
              path="galleries/review"
              element={
                <GalleryView
                  status="REVIEW_REQUIRED"
                  title="Review Queue"
                  description="Images requiring human confirmation due to AI uncertainty or edge-case sharpness scoring."
                />
              }
            />
            <Route
              path="galleries/rejected"
              element={
                <GalleryView
                  status="REJECTED"
                  title="Rejected Images"
                  description="Photos filtered out by quality heuristics, duplicate collision, or clear non-decoration mismatch."
                />
              }
            />
            <Route path="duplicates" element={<DuplicatePage />} />
            <Route path="metadata" element={<MetadataStudioPage />} />
            <Route path="google-drive" element={<GoogleDrivePage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
