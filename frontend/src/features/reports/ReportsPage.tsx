import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  FileText,
  Download,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  CopyCheck,
  Cloud,
  FileBarChart
} from 'lucide-react'
import { api } from '@/services/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

export const ReportsPage: React.FC = () => {
  const { data: summary, isLoading } = useQuery({
    queryKey: ['reports-summary'],
    queryFn: () => api.getReportsSummary(),
  })

  const exportTypes = [
    {
      title: 'Approved Catalog Metadata Report',
      desc: 'Complete production catalog export with copy, inclusions, tags, and drive URLs.',
      csvUrl: '/api/v1/reports/export?format=csv&status=APPROVED',
      excelUrl: '/api/v1/reports/export?format=excel&status=APPROVED',
      badge: 'Production Ready',
      color: 'border-emerald-200',
    },
    {
      title: 'All Ingested Photos Master Audit',
      desc: 'Full operational record including quality blur scores, hashes, and pipeline durations.',
      csvUrl: '/api/v1/reports/export?format=csv',
      excelUrl: '/api/v1/reports/export?format=excel',
      badge: 'Full Dataset',
      color: 'border-blue-200',
    },
    {
      title: 'Rejections & Quality Failures Log',
      desc: 'Detailed log of all rejected photos, reasons, blur scores, and corrupt file flags.',
      csvUrl: '/api/v1/reports/export?format=csv&status=REJECTED',
      excelUrl: '/api/v1/reports/export?format=excel&status=REJECTED',
      badge: 'Audit Log',
      color: 'border-rose-200',
    },
    {
      title: 'Review Queue Pending Evaluations',
      desc: 'Uncertain classifications and edge cases awaiting operator manual confirmation.',
      csvUrl: '/api/v1/reports/export?format=csv&status=REVIEW_REQUIRED',
      excelUrl: '/api/v1/reports/export?format=excel&status=REVIEW_REQUIRED',
      badge: 'Action Required',
      color: 'border-amber-200',
    },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Reports & Data Exports</h1>
        <p className="text-xs text-slate-500 mt-1">
          Export verified decoration inventory records, audit logs, and performance metrics in standardized Excel (.xlsx) or CSV formats.
        </p>
      </div>

      {/* Export Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {exportTypes.map((item) => (
          <Card key={item.title} className={`${item.color} shadow-xs`}>
            <CardHeader className="p-4 border-b">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">{item.title}</CardTitle>
                <Badge variant="neutral">{item.badge}</Badge>
              </div>
              <CardDescription>{item.desc}</CardDescription>
            </CardHeader>
            <CardContent className="p-4 flex items-center justify-end gap-3">
              <a href={item.csvUrl} download>
                <Button variant="outline" size="sm" className="gap-2">
                  <FileText className="w-4 h-4 text-slate-600" />
                  Download CSV
                </Button>
              </a>
              <a href={item.excelUrl} download>
                <Button size="sm" className="gap-2">
                  <FileSpreadsheet className="w-4 h-4" />
                  Download Excel (.xlsx)
                </Button>
              </a>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
