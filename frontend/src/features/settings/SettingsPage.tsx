import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Settings as SettingsIcon,
  Save,
  Key,
  Sliders,
  Database,
  Cloud,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  XCircle,
  Trash2,
  ExternalLink
} from 'lucide-react'
import { api } from '@/services/api'
import type { SystemSettings } from '@/types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

export const SettingsPage: React.FC = () => {
  const queryClient = useQueryClient()

  const { data: currentSettings, isLoading } = useQuery({
    queryKey: ['system-settings'],
    queryFn: () => api.getSystemSettings(),
  })

  // Form states
  const [minWidth, setMinWidth] = useState(800)
  const [minHeight, setMinHeight] = useState(600)
  const [minSizeKb, setMinSizeKb] = useState(50)
  const [blurThreshold, setBlurThreshold] = useState(100.0)
  const [phashThreshold, setPhashThreshold] = useState(5)
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.75)
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash')
  const [geminiApiKey, setGeminiApiKey] = useState('')
  const [connectionTestResult, setConnectionTestResult] = useState<{
    success: boolean
    status: string
    message: string
  } | null>(null)

  useEffect(() => {
    if (currentSettings) {
      setMinWidth(currentSettings.min_image_width)
      setMinHeight(currentSettings.min_image_height)
      setMinSizeKb(currentSettings.min_file_size_kb)
      setBlurThreshold(currentSettings.blur_threshold)
      setPhashThreshold(currentSettings.phash_threshold)
      setConfidenceThreshold(currentSettings.ai_confidence_threshold)
      setGeminiModel(currentSettings.gemini_model)
    }
  }, [currentSettings])

  const testConnectionMutation = useMutation({
    mutationFn: () => api.testGeminiConnection(),
    onSuccess: (data) => {
      setConnectionTestResult(data)
    },
    onError: (err: any) => {
      setConnectionTestResult({
        success: false,
        status: 'ERROR',
        message: err.response?.data?.detail || 'Connection test failed',
      })
    },
  })

  const saveKeyMutation = useMutation({
    mutationFn: (key: string) => api.updateGeminiApiKey(key),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['system-settings'] })
      setGeminiApiKey('')
      setConnectionTestResult(res.test_result)
      alert(res.message)
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to update key')
    },
  })

  const removeKeyMutation = useMutation({
    mutationFn: () => api.removeGeminiApiKey(),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['system-settings'] })
      setConnectionTestResult(null)
      alert(res.message)
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to remove key')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: any) => api.updateSystemSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-settings'] })
      alert('System thresholds updated successfully.')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to update settings')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate({
      min_image_width: Number(minWidth),
      min_image_height: Number(minHeight),
      min_file_size_kb: Number(minSizeKb),
      blur_threshold: Number(blurThreshold),
      phash_threshold: Number(phashThreshold),
      ai_confidence_threshold: Number(confidenceThreshold),
      gemini_model: geminiModel,
    })
  }

  if (isLoading || !currentSettings) {
    return <div className="p-16 text-center text-xs text-slate-400">Loading settings...</div>
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          System Settings & Thresholds
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Configure runtime quality parameters, duplicate sensitivity, Google Drive cloud integration, and Google Gemini vision models.
        </p>
      </div>

      {/* Google Gemini Vision Configuration */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Key className="w-4 h-4 text-indigo-600" />
            <CardTitle className="text-sm">Google Gemini Vision API Key & AI Engine</CardTitle>
          </div>
          <CardDescription>Official Google Gen AI SDK integration for category classification and catalog metadata</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 bg-slate-50 rounded-xl border gap-3">
            <div className="text-xs space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-800">Current Key Status:</span>
                <Badge variant={currentSettings.gemini_api_key_configured ? 'approved' : 'review'}>
                  {currentSettings.gemini_api_key_configured ? 'Key Configured' : 'Heuristic Mode Active'}
                </Badge>
              </div>
              <p className="text-[11px] text-slate-500">
                Secrets are never exposed to browser storage and are masked in all API responses.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => testConnectionMutation.mutate()}
                isLoading={testConnectionMutation.isPending}
                className="gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Test Connection
              </Button>
              {currentSettings.gemini_api_key_configured && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="text-rose-600 hover:bg-rose-50 border-rose-200"
                  onClick={() => {
                    if (confirm('Revert to Heuristic Mode and remove the configured Gemini API key?')) {
                      removeKeyMutation.mutate()
                    }
                  }}
                  isLoading={removeKeyMutation.isPending}
                >
                  <Trash2 className="w-3.5 h-3.5" /> Remove Key
                </Button>
              )}
            </div>
          </div>

          {/* Connection Test Diagnostics Alert */}
          {connectionTestResult && (
            <div
              className={`p-3.5 rounded-xl border text-xs flex items-start gap-3 ${
                connectionTestResult.success
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : connectionTestResult.status === 'QUOTA_OR_BILLING_REQUIRED'
                  ? 'bg-amber-50 border-amber-200 text-amber-900'
                  : 'bg-rose-50 border-rose-200 text-rose-900'
              }`}
            >
              {connectionTestResult.success ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              ) : connectionTestResult.status === 'QUOTA_OR_BILLING_REQUIRED' ? (
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1">
                <div className="font-semibold flex items-center gap-2">
                  <span>Status: {connectionTestResult.status}</span>
                </div>
                <p className="text-[11px]">{connectionTestResult.message}</p>
                {connectionTestResult.status === 'QUOTA_OR_BILLING_REQUIRED' && (
                  <p className="text-[11px] pt-1">
                    To use the Gemini API on your project, ensure billing is active at{' '}
                    <a
                      href="https://aistudio.google.com/billing"
                      target="_blank"
                      rel="noreferrer"
                      className="underline font-semibold inline-flex items-center gap-1"
                    >
                      Google AI Studio Billing <ExternalLink className="w-3 h-3" />
                    </a>{' '}
                    or update to another valid API key below.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Update Key Input */}
          <div className="space-y-2 pt-1">
            <label className="block text-xs font-semibold text-slate-700">
              Update / Enter New Gemini API Key
            </label>
            <div className="flex items-center gap-2">
              <input
                type="password"
                placeholder="AIzaSy..."
                value={geminiApiKey}
                onChange={(e) => setGeminiApiKey(e.target.value)}
                className="flex-1 px-3 py-2 border rounded-lg text-xs font-mono bg-white focus:ring-1 focus:ring-indigo-500"
              />
              <Button
                type="button"
                size="sm"
                variant="primary"
                disabled={!geminiApiKey.trim()}
                onClick={() => saveKeyMutation.mutate(geminiApiKey.trim())}
                isLoading={saveKeyMutation.isPending}
              >
                Save Key
              </Button>
            </div>
            <p className="text-[11px] text-slate-400">
              Your key is saved encrypted to the backend environment file and masked in responses.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Main Settings Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Quality Check Parameters */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-blue-600" />
              <CardTitle className="text-sm">Image Quality & Verification Parameters</CardTitle>
            </div>
            <CardDescription>Rules applied at Step 1 and Step 3 of the ingestion pipeline</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Min Resolution Width (px)</label>
                <input
                  type="number"
                  value={minWidth}
                  onChange={(e) => setMinWidth(Number(e.target.value))}
                  className="w-full px-3 py-1.5 border rounded-lg text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Min Resolution Height (px)</label>
                <input
                  type="number"
                  value={minHeight}
                  onChange={(e) => setMinHeight(Number(e.target.value))}
                  className="w-full px-3 py-1.5 border rounded-lg text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Min File Size (KB)</label>
                <input
                  type="number"
                  value={minSizeKb}
                  onChange={(e) => setMinSizeKb(Number(e.target.value))}
                  className="w-full px-3 py-1.5 border rounded-lg text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  OpenCV Laplacian Blur Threshold
                </label>
                <input
                  type="number"
                  step="5"
                  value={blurThreshold}
                  onChange={(e) => setBlurThreshold(Number(e.target.value))}
                  className="w-full px-3 py-1.5 border rounded-lg text-xs"
                />
                <p className="text-[11px] text-slate-400 mt-1">Variance of the Laplacian. Scores below this are flagged blurry.</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  pHash Duplicate Max Hamming Distance
                </label>
                <input
                  type="number"
                  value={phashThreshold}
                  onChange={(e) => setPhashThreshold(Number(e.target.value))}
                  className="w-full px-3 py-1.5 border rounded-lg text-xs"
                />
                <p className="text-[11px] text-slate-400 mt-1">Distance &lt;= 5 triggers perceptual duplicate flag.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Gemini Vision Model</label>
                <select
                  value={geminiModel}
                  onChange={(e) => setGeminiModel(e.target.value)}
                  className="w-full px-3 py-1.5 border rounded-lg text-xs"
                >
                  <option value="gemini-2.5-flash">gemini-2.5-flash (Fast & Structured)</option>
                  <option value="gemini-2.5-pro">gemini-2.5-pro (High Precision)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Confidence Threshold for Auto-Approval
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                  className="w-full px-3 py-1.5 border rounded-lg text-xs"
                />
                <p className="text-[11px] text-slate-400 mt-1">Default 0.75. Lower scores divert to Review Queue.</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Action Button */}
        <div className="flex justify-end">
          <Button type="submit" size="md" isLoading={updateMutation.isPending} className="gap-2">
            <Save className="w-4 h-4" /> Save System Thresholds
          </Button>
        </div>
      </form>
    </div>
  )
}
