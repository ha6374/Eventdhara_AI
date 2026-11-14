import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FileSpreadsheet,
  Link2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  LogOut,
  ExternalLink,
  ShieldCheck,
  Check,
  Zap,
  ArrowRight
} from 'lucide-react'
import { api } from '@/services/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { formatDate } from '@/lib/utils'

interface GoogleSheetsSectionProps {
  onSyncSuccess?: (result: any) => void
  showSyncButton?: boolean
  selectedImageIds?: number[]
  selectedCategoryId?: number | null
}

export const GoogleSheetsSection: React.FC<GoogleSheetsSectionProps> = ({
  onSyncSuccess,
  showSyncButton = true,
  selectedImageIds,
  selectedCategoryId = null,
}) => {
  const queryClient = useQueryClient()

  const { data: config, isLoading, refetch } = useQuery({
    queryKey: ['dynamic-sheets-config'],
    queryFn: () => api.getDynamicSheetsConfig(),
  })

  const [spreadsheetUrl, setSpreadsheetUrl] = useState('')
  const [worksheetName, setWorksheetName] = useState('EventDhara Catalog')
  const [notification, setNotification] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null)
  const [testResult, setTestResult] = useState<any | null>(null)

  useEffect(() => {
    if (config) {
      if (config.spreadsheet_url) setSpreadsheetUrl(config.spreadsheet_url)
      if (config.worksheet_name) setWorksheetName(config.worksheet_name)
    }
  }, [config])

  // Listen for OAuth success message from popup window
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'GOOGLE_SHEETS_AUTH_SUCCESS') {
        setNotification({
          type: 'success',
          message: `Google Account successfully connected as ${event.data.email}!`,
        })
        queryClient.invalidateQueries({ queryKey: ['dynamic-sheets-config'] })
        refetch()
      } else if (event.data?.type === 'GOOGLE_SHEETS_AUTH_ERROR') {
        setNotification({
          type: 'error',
          message: `Google connection failed: ${event.data.error}`,
        })
      }
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [queryClient, refetch])

  // Save Configuration Mutation
  const saveConfigMutation = useMutation({
    mutationFn: () =>
      api.updateDynamicSheetsConfig({
        spreadsheet_url: spreadsheetUrl,
        worksheet_name: worksheetName,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['dynamic-sheets-config'] })
      setNotification({
        type: 'success',
        message: `Spreadsheet connected and saved! (ID: ${data.spreadsheet_id})`,
      })
      setTestResult(null)
    },
    onError: (err: any) => {
      setNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to save spreadsheet configuration.',
      })
    },
  })

  // Test Connection Mutation
  const testConnectionMutation = useMutation({
    mutationFn: () => api.testDynamicSheetsConnection(),
    onSuccess: (data) => {
      setTestResult(data)
      setNotification({
        type: 'success',
        message: data.message || 'Connection verified successfully! Editor access confirmed.',
      })
    },
    onError: (err: any) => {
      setTestResult(null)
      setNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Spreadsheet connection test failed.',
      })
    },
  })

  // Connect Google Account (OAuth popup)
  const connectAccountMutation = useMutation({
    mutationFn: () => api.getSheetsAuthUrl(),
    onSuccess: (data) => {
      if (data.auth_url) {
        // Open OAuth consent in a standardized centered popup
        const width = 600
        const height = 700
        const left = window.screen.width / 2 - width / 2
        const top = window.screen.height / 2 - height / 2
        window.open(
          data.auth_url,
          'GoogleOAuthPopup',
          `width=${width},height=${height},top=${top},left=${left},toolbar=no,menubar=no`
        )
      }
    },
    onError: (err: any) => {
      setNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Could not initiate Google OAuth flow. Please ensure GOOGLE_CLIENT_ID is configured.',
      })
    },
  })

  // Disconnect Mutation
  const disconnectMutation = useMutation({
    mutationFn: () => api.disconnectDynamicSheets(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dynamic-sheets-config'] })
      setTestResult(null)
      setNotification({
        type: 'info',
        message: 'Google Account and spreadsheet disconnected.',
      })
    },
    onError: (err: any) => {
      setNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Disconnect failed.',
      })
    },
  })

  // Sync Metadata to Sheets Mutation
  const syncMutation = useMutation({
    mutationFn: () =>
      api.syncMetadataToDynamicSheets({
        image_ids: selectedImageIds && selectedImageIds.length > 0 ? selectedImageIds : undefined,
        category_id: selectedCategoryId ?? undefined,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['dynamic-sheets-config'] })
      setNotification({
        type: 'success',
        message: data.message,
      })
      if (onSyncSuccess) {
        onSyncSuccess(data)
      }
    },
    onError: (err: any) => {
      setNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to save metadata to Google Sheets.',
      })
    },
  })

  const isFormDirty =
    (config?.spreadsheet_url || '') !== spreadsheetUrl ||
    (config?.worksheet_name || 'EventDhara Catalog') !== worksheetName

  return (
    <Card className="border-emerald-200 shadow-sm bg-gradient-to-b from-white to-emerald-50/20">
      <CardHeader className="pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold shadow-xs">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <CardTitle className="text-base flex items-center gap-2 text-slate-900">
                Google Sheets Integration
                <Badge variant={config?.is_connected ? 'approved' : 'neutral'}>
                  {config?.is_connected ? 'Account Connected' : 'Not Connected'}
                </Badge>
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Connect your personal or enterprise Google Spreadsheet to automatically sync 10-column catalog metadata with zero code changes.
              </CardDescription>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {config?.spreadsheet_url && (
              <a
                href={config.spreadsheet_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-emerald-700 hover:text-emerald-800 font-medium flex items-center gap-1 bg-emerald-50 border border-emerald-200 px-2.5 py-1.5 rounded-lg"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Open Sheet
              </a>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetch()
                setNotification(null)
              }}
              title="Refresh status"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Notification Banner */}
        {notification && (
          <div
            className={`p-3 rounded-lg text-xs flex items-start justify-between gap-2 border ${
              notification.type === 'success'
                ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
                : notification.type === 'error'
                ? 'bg-rose-50 text-rose-900 border-rose-200'
                : 'bg-blue-50 text-blue-900 border-blue-200'
            }`}
          >
            <div className="flex items-center gap-2">
              {notification.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              )}
              <span>{notification.message}</span>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="text-slate-400 hover:text-slate-600 font-bold ml-2"
            >
              ×
            </button>
          </div>
        )}

        {/* OAuth Authentication Row */}
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-0.5">
            <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Google Account Authorization (OAuth 2.0)
            </span>
            <p className="text-[11px] text-slate-500">
              {config?.is_connected ? (
                <>
                  Connected as <span className="font-semibold text-slate-800">{config.connected_email}</span>{' '}
                  {config.connected_account_name && `(${config.connected_account_name})`}
                </>
              ) : (
                'Grant write permission to append metadata rows into your Google Spreadsheets.'
              )}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {config?.is_connected ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => disconnectMutation.mutate()}
                isLoading={disconnectMutation.isPending}
                className="text-rose-600 border-rose-200 hover:bg-rose-50 gap-1.5 text-xs"
              >
                <LogOut className="w-3.5 h-3.5" />
                Disconnect Account
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => connectAccountMutation.mutate()}
                isLoading={connectAccountMutation.isPending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 text-xs"
              >
                <Zap className="w-3.5 h-3.5" />
                Connect Google Account
              </Button>
            )}
          </div>
        </div>

        {/* Spreadsheet Configuration Form */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          <div className="md:col-span-2 space-y-1">
            <label className="text-xs font-semibold text-slate-700 flex items-center justify-between">
              <span>Google Spreadsheet URL</span>
              <span className="text-[10px] text-slate-400 font-normal">
                Format: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
              </span>
            </label>
            <div className="relative">
              <Link2 className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
              <input
                type="url"
                value={spreadsheetUrl}
                onChange={(e) => setSpreadsheetUrl(e.target.value)}
                placeholder="https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
                className="w-full text-xs pl-9 pr-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">
              Worksheet / Tab Name
            </label>
            <input
              type="text"
              value={worksheetName}
              onChange={(e) => setWorksheetName(e.target.value)}
              placeholder="EventDhara Catalog"
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        {/* Action Controls & Last Sync Telemetry */}
        <div className="pt-2 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => saveConfigMutation.mutate()}
              isLoading={saveConfigMutation.isPending}
              disabled={!spreadsheetUrl.trim()}
              className="bg-slate-900 hover:bg-slate-800 text-white text-xs gap-1.5"
            >
              <Check className="w-3.5 h-3.5" />
              Connect & Save
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => testConnectionMutation.mutate()}
              isLoading={testConnectionMutation.isPending}
              disabled={!config?.is_connected || !config?.spreadsheet_id}
              className="text-xs gap-1.5 border-slate-300 hover:bg-slate-50"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              Test Connection
            </Button>

            {showSyncButton && (
              <Button
                size="sm"
                onClick={() => syncMutation.mutate()}
                isLoading={syncMutation.isPending}
                disabled={!config?.is_connected || !config?.spreadsheet_id}
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs gap-1.5 shadow-xs"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                {selectedImageIds && selectedImageIds.length > 0
                  ? `Save ${selectedImageIds.length} Selected to Sheets`
                  : 'Save to Google Sheets'}
              </Button>
            )}
          </div>

          <div className="text-[11px] text-slate-500 flex items-center gap-3 font-mono">
            <span>
              Last Sync: <strong className="text-slate-700">{formatDate(config?.last_synced_at)}</strong>
            </span>
            {config?.last_sync_status && (
              <Badge
                variant={
                  config.last_sync_status === 'SUCCESS' || config.last_sync_status === 'CONNECTED'
                    ? 'approved'
                    : 'review'
                }
              >
                {config.last_sync_status}
              </Badge>
            )}
          </div>
        </div>

        {/* Test Result Verification Box */}
        {testResult && (
          <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-lg text-xs space-y-1">
            <div className="font-semibold text-emerald-950 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Connection Verified: {testResult.spreadsheet_title}
            </div>
            <div className="text-slate-600 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
              <div>• Spreadsheet ID: <span className="font-mono text-slate-800">{testResult.spreadsheet_id}</span></div>
              <div>• Target Tab: <span className="font-semibold text-slate-800">{testResult.worksheet_name}</span> {testResult.worksheet_exists ? '(Exists)' : '(Will create on sync)'}</div>
              <div>• Connected User: <span className="font-mono text-slate-800">{testResult.connected_email}</span></div>
              <div>• Permission: <span className="text-emerald-700 font-semibold">Editor (Write Access Verified)</span></div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
