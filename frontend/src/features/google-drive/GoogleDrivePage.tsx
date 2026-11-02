import React from 'react'
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
  ArrowUpRight
} from 'lucide-react'
import { api } from '@/services/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

export const GoogleDrivePage: React.FC = () => {
  const queryClient = useQueryClient()

  const { data: driveStatus, isLoading: statusLoading, refetch } = useQuery({
    queryKey: ['drive-status'],
    queryFn: () => api.getDriveStatus(),
  })

  const { data: approvedImages } = useQuery({
    queryKey: ['approved-drive-images'],
    queryFn: () => api.getImages({ status: 'APPROVED', size: 50 }),
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

  const items = approvedImages?.items || []

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            Google Drive Cloud Sync
            <Badge variant="approved">Enterprise Cloud Integration</Badge>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Automated structured cloud replication into canonical directory hierarchy: <code>Decoration Images / [Category] / [Subcategory]</code>.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            onClick={() => bulkUploadMutation.mutate()}
            isLoading={bulkUploadMutation.isPending}
            className="gap-2"
          >
            <Cloud className="w-4 h-4" />
            Sync All Approved Images
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Refresh Sync State
          </Button>
        </div>
      </div>

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
            <span className="text-[11px] text-slate-500 font-medium">Cloud Target Directory</span>
            <div className="text-sm font-semibold text-slate-800 mt-2 truncate">
              {driveStatus?.drive_root || 'Decoration Images'}
            </div>
          </CardContent>
        </Card>
      </div>

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
                        alt=""
                        className="w-10 h-10 rounded-lg object-cover bg-slate-100"
                      />
                      <span className="truncate max-w-[200px]">{item.original_filename}</span>
                    </td>
                    <td className="py-3.5 px-6 font-mono text-[11px] text-slate-600">
                      Decoration Images / {item.category_name || 'General'}
                    </td>
                    <td className="py-3.5 px-6">
                      <Badge variant={item.drive_status === 'COMPLETED' ? 'approved' : 'pending'} dot>
                        {item.drive_status}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-6">
                      {item.drive_url ? (
                        <a
                          href={item.drive_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 hover:underline flex items-center gap-1 font-mono text-[11px]"
                        >
                          {item.drive_file_id} <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-slate-400 font-mono text-[11px]">Unsynced</span>
                      )}
                    </td>
                    <td className="py-3.5 px-6 text-right">
                      {item.drive_status !== 'COMPLETED' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => uploadSingleMutation.mutate(item.id)}
                          isLoading={uploadSingleMutation.isPending}
                        >
                          Sync Now
                        </Button>
                      ) : (
                        <span className="text-emerald-600 text-xs font-semibold flex items-center justify-end gap-1">
                          <CheckCircle2 className="w-4 h-4" /> Verified
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400 text-xs">
                    No approved decoration photos ready for Google Drive synchronization.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
