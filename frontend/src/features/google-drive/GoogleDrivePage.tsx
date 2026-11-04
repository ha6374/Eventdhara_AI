import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Cloud,
  FolderCheck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ExternalLink,
  RefreshCw,
  FolderTree,
  ShieldCheck,
  ArrowUpRight,
  UserCheck,
  HardDrive,
  Plus,
  FileSpreadsheet,
  Unlink,
  FolderPlus
} from 'lucide-react'
import { api } from '@/services/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'

export const GoogleDrivePage: React.FC = () => {
  const queryClient = useQueryClient()
  const [newFolderModalOpen, setNewFolderModalOpen] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')

  const { data: driveStatus, isLoading: statusLoading, refetch } = useQuery({
    queryKey: ['drive-status'],
    queryFn: () => api.getDriveStatus(),
  })

  const { data: approvedImages } = useQuery({
    queryKey: ['approved-drive-images'],
    queryFn: () => api.getImages({ status: 'APPROVED', size: 50 }),
  })

  const { data: subfolders = [] } = useQuery({
    queryKey: ['drive-browse-folders'],
    queryFn: () => api.browseDriveFolders(),
    enabled: !!driveStatus?.connected,
  })

  const bulkUploadMutation = useMutation({
    mutationFn: () => api.bulkUploadToDrive(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['drive-status'] })
      queryClient.invalidateQueries({ queryKey: ['approved-drive-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      alert(`Google Drive Sync complete: ${data.uploaded} uploaded, ${data.failed} failed.`)
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Sync failed')
    },
  })

  const uploadSingleMutation = useMutation({
    mutationFn: (id: number) => api.uploadSingleToDrive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drive-status'] })
      queryClient.invalidateQueries({ queryKey: ['approved-drive-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Single sync failed')
    },
  })

  const createFolderMutation = useMutation({
    mutationFn: (name: string) => api.createDriveFolder(name),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['drive-browse-folders'] })
      setNewFolderModalOpen(false)
      setNewFolderName('')
      alert(`Folder '${res.folder_name}' created in Google Drive.`)
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to create folder')
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: () => api.disconnectDrive(),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['drive-status'] })
      alert(res.message)
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to disconnect')
    },
  })

  const exportSheetsMutation = useMutation({
    mutationFn: () => api.exportToGoogleSheets(undefined, 'APPROVED'),
    onSuccess: (res) => {
      alert(`Published ${res.total_rows} catalog records to Google Sheets!\nURL: ${res.sheet_url}`)
      if (res.sheet_url) {
        window.open(res.sheet_url, '_blank')
      }
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Google Sheets export failed')
    },
  })

  const items = approvedImages?.items || []

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            Google Drive Cloud Sync
            <Badge variant={driveStatus?.connected ? 'approved' : 'review'}>
              {driveStatus?.connected ? 'Live Connected' : 'Local Mirror Mode'}
            </Badge>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Automated structured cloud replication into category hierarchy: <code>EventDhara / [Category] / Approved</code>.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            size="sm"
            onClick={() => bulkUploadMutation.mutate()}
            isLoading={bulkUploadMutation.isPending}
            className="gap-2"
          >
            <Cloud className="w-4 h-4" />
            Sync All Approved Images
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportSheetsMutation.mutate()}
            isLoading={exportSheetsMutation.isPending}
            className="gap-2"
          >
            <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
            Export to Google Sheets
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Connected Account & Quota Banner */}
      <Card className="border-indigo-100 bg-gradient-to-r from-slate-50 via-indigo-50/20 to-white">
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-lg shadow-sm">
              <HardDrive className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-slate-900">
                  {driveStatus?.display_name || 'Google Cloud Identity'}
                </span>
                <span className="text-xs text-indigo-700 font-mono bg-indigo-100 px-2 py-0.5 rounded-full">
                  {driveStatus?.email || 'OAuth 2.0 Installed App Client'}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Target Drive Folder: <strong className="text-slate-800">{driveStatus?.root_folder_name || 'Eventdhara_decorations'}</strong>
                <span className="text-slate-400 font-mono ml-1.5">({driveStatus?.root_folder_id})</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setNewFolderModalOpen(true)}
              className="gap-1.5"
            >
              <FolderPlus className="w-3.5 h-3.5" /> New Destination Folder
            </Button>
            {driveStatus?.connected && (
              <Button
                size="sm"
                variant="outline"
                className="text-rose-600 hover:bg-rose-50 border-rose-200 gap-1.5"
                onClick={() => {
                  if (confirm('Are you sure you want to disconnect Google Drive?')) {
                    disconnectMutation.mutate()
                  }
                }}
              >
                <Unlink className="w-3.5 h-3.5 text-rose-500" /> Disconnect
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Sync Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <span className="text-[11px] text-slate-500 font-medium">Approved Candidates</span>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {driveStatus?.total_approved || 0}
            </div>
          </CardContent>
        </Card>
        <Card className="border-emerald-200">
          <CardContent className="p-4 text-emerald-700">
            <span className="text-[11px] font-medium">Successfully Synced</span>
            <div className="text-2xl font-bold mt-1">
              {driveStatus?.synced_to_drive || 0}
            </div>
          </CardContent>
        </Card>
        <Card className="border-amber-200">
          <CardContent className="p-4 text-amber-700">
            <span className="text-[11px] font-medium">Pending Transfer</span>
            <div className="text-2xl font-bold mt-1">
              {driveStatus?.pending_sync || 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <span className="text-[11px] text-slate-500 font-medium">Google Drive Storage</span>
            <div className="text-base font-bold text-slate-800 mt-1">
              {driveStatus?.storage_used_gb ?? 0} GB used
            </div>
            <span className="text-[10px] text-slate-400">
              Limit: {driveStatus?.storage_limit_gb ?? 'N/A'} GB
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Subfolder Browser */}
      {subfolders.length > 0 && (
        <Card>
          <CardHeader className="py-3 px-4 border-b bg-slate-50/50">
            <CardTitle className="text-xs uppercase tracking-wider text-slate-600">
              Live Google Drive Category Folders ({subfolders.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div className="flex flex-wrap gap-2">
              {subfolders.map((f) => (
                <div key={f.id} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 rounded-lg text-xs font-medium text-slate-700 border">
                  <FolderCheck className="w-3.5 h-3.5 text-blue-600" />
                  <span>{f.name}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Approved Images Cloud Sync Queue */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Approved Images Drive Telemetry</CardTitle>
            <CardDescription>Verified upload state and Drive URL mappings</CardDescription>
          </div>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 font-semibold uppercase text-[10px]">
                <th className="py-3 px-6">Image</th>
                <th className="py-3 px-6">Drive Target Folder</th>
                <th className="py-3 px-6">Sync Status</th>
                <th className="py-3 px-6">Cloud File ID / URL</th>
                <th className="py-3 px-6 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.length > 0 ? (
                items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-6 font-medium text-slate-800 flex items-center gap-3">
                      <img
                        src={`/${item.storage_path}`}
                        alt={item.original_filename}
                        className="w-9 h-9 object-cover rounded-md border"
                      />
                      <span className="truncate max-w-[200px]" title={item.original_filename}>
                        {item.original_filename}
                      </span>
                    </td>
                    <td className="py-3.5 px-6 text-slate-500 font-mono text-[11px]">
                      {item.category_name ? `${item.category_name} / Approved` : 'Unassigned / Approved'}
                    </td>
                    <td className="py-3.5 px-6">
                      <Badge
                        variant={
                          item.drive_status === 'COMPLETED'
                            ? 'approved'
                            : item.drive_status === 'UPLOADING'
                            ? 'review'
                            : 'neutral'
                        }
                        dot
                      >
                        {item.drive_status}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-6 font-mono text-[11px]">
                      {item.drive_url ? (
                        <a
                          href={item.drive_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 hover:underline flex items-center gap-1"
                        >
                          {item.drive_file_id || 'Open Link'}
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-slate-400">Not Uploaded</span>
                      )}
                    </td>
                    <td className="py-3.5 px-6 text-right">
                      {item.drive_status !== 'COMPLETED' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => uploadSingleMutation.mutate(item.id)}
                          isLoading={uploadSingleMutation.isPending}
                        >
                          Sync Now
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    No approved images pending sync.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Create New Folder Modal */}
      <Modal
        isOpen={newFolderModalOpen}
        onClose={() => setNewFolderModalOpen(false)}
        title="Create Google Drive Destination Folder"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            Create a top-level category or event folder directly inside your Google Drive repository.
          </p>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Folder Name *</label>
            <input
              type="text"
              required
              placeholder="e.g. Wedding 2026 Season"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-2 border-t">
            <Button variant="outline" size="sm" onClick={() => setNewFolderModalOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={!newFolderName.trim()}
              onClick={() => createFolderMutation.mutate(newFolderName.trim())}
              isLoading={createFolderMutation.isPending}
            >
              Create Folder
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
