"use client"

import { useState, useEffect } from "react"
import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { 
  TrendingUp, 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle,
  DollarSign,
  RefreshCw,
  FolderOpen
} from "lucide-react"
import { 
  workspacesApi, 
  documentsApi, 
  matchingApi, 
  type Workspace, 
  type Document, 
  type MatchingResult 
} from "@/lib/api"

interface AnalyticsData {
  totalWorkspaces: number
  totalDocuments: number
  totalMatchedGroups: number
  totalDiscrepancies: number
  perfectMatches: number
  partialMatches: number
  documentsByType: {
    purchase_order: number
    invoice: number
    delivery_note: number
  }
  discrepanciesByType: {
    quantity_mismatch: number
    price_change: number
    missing_item: number
    extra_item: number
    currency_mismatch: number
    tax_rate_mismatch: number
    tax_amount_mismatch: number
  }
  discrepanciesBySeverity: {
    critical: number
    high: number
    medium: number
    low: number
  }
  totalAmount: number
  totalDifference: number
  processingStatus: {
    processed: number
    processing: number
    failed: number
    uploaded: number
  }
  workspacesData?: Record<string, {
    documentCount: number
    matchedGroups: number
  }>
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [workspacesRes, setWorkspacesRes] = useState<{ data: Workspace[] } | null>(null)

  useEffect(() => {
    loadAnalytics()
  }, [])

  const loadAnalytics = async () => {
    setLoading(true)
    try {
      const workspacesRes = await workspacesApi.list()
      const workspaces: Workspace[] = workspacesRes.data || []

      let totalDocuments = 0
      let totalMatchedGroups = 0
      let totalDiscrepancies = 0
      let perfectMatches = 0
      let partialMatches = 0
      let totalAmount = 0
      let totalDifference = 0

      const documentsByType = {
        purchase_order: 0,
        invoice: 0,
        delivery_note: 0,
      }

      const discrepanciesByType: Record<string, number> = {
        quantity_mismatch: 0,
        price_change: 0,
        missing_item: 0,
        extra_item: 0,
        currency_mismatch: 0,
        tax_rate_mismatch: 0,
        tax_amount_mismatch: 0,
      }

      const discrepanciesBySeverity = {
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
      }

      const processingStatus = {
        processed: 0,
        processing: 0,
        failed: 0,
        uploaded: 0,
      }

      const workspacesData: Record<string, { documentCount: number; matchedGroups: number }> = {}

      // Aggregate data from all workspaces
      for (const workspace of workspaces) {
        try {
          const [docsRes, resultsRes] = await Promise.all([
            documentsApi.list(workspace.id).catch(() => ({ data: [] })),
            matchingApi.getResults(workspace.id).catch(() => ({ data: [] })),
          ])

          const documents: Document[] = docsRes.data || []
          const results: MatchingResult[] = resultsRes.data || []

          // Track workspace data
          workspacesData[workspace.id] = {
            documentCount: documents.length,
            matchedGroups: results.length,
          }

          totalDocuments += documents.length
          totalMatchedGroups += results.length

          // Count documents by type
          documents.forEach((doc) => {
            if (doc.document_type === "purchase_order") {
              documentsByType.purchase_order++
            } else if (doc.document_type === "invoice") {
              documentsByType.invoice++
            } else if (doc.document_type === "delivery_note") {
              documentsByType.delivery_note++
            }

            // Count by status
            if (doc.status === "PROCESSED") processingStatus.processed++
            else if (doc.status === "PROCESSING") processingStatus.processing++
            else if (doc.status === "FAILED") processingStatus.failed++
            else if (doc.status === "UPLOADED") processingStatus.uploaded++
          })

          // Process matching results
          results.forEach((result) => {
            if (result.discrepancies.length === 0) {
              perfectMatches++
            } else {
              partialMatches++
            }

            totalDiscrepancies += result.discrepancies.length
            // Sum absolute differences (each match's difference)
            totalDifference += parseFloat(result.total_difference || "0")
            // Sum invoice amounts (more representative of actual transaction value)
            // Using invoice amount as it represents what was actually billed
            totalAmount += parseFloat(result.total_invoice_amount || result.total_po_amount || "0")

            // Count discrepancies by type and severity
            result.discrepancies.forEach((disc) => {
              const type = disc.type
              if (discrepanciesByType[type] !== undefined) {
                discrepanciesByType[type]++
              }

              const severity = disc.severity
              if (severity === "critical") discrepanciesBySeverity.critical++
              else if (severity === "high") discrepanciesBySeverity.high++
              else if (severity === "medium") discrepanciesBySeverity.medium++
              else if (severity === "low") discrepanciesBySeverity.low++
            })
          })
        } catch (error) {
          console.error(`Failed to load data for workspace ${workspace.id}:`, error)
        }
      }

      setAnalytics({
        totalWorkspaces: workspaces.length,
        totalDocuments,
        totalMatchedGroups,
        totalDiscrepancies,
        perfectMatches,
        partialMatches,
        documentsByType,
        discrepanciesByType: discrepanciesByType as any,
        discrepanciesBySeverity,
        totalAmount,
        totalDifference,
        processingStatus,
        workspacesData,
      })
      setWorkspacesRes({ data: workspaces })
      setLastUpdated(new Date())
    } catch (error) {
      console.error("Failed to load analytics:", error)
    } finally {
      setLoading(false)
    }
  }

  const StatCard = ({ 
    title, 
    value, 
    icon: Icon, 
    trend 
  }: { 
    title: string
    value: string | number
    icon: any
    trend?: string
  }) => (
    <Card className="border border-[#E5E5E5] bg-white">
      <div className="p-5">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs text-[#404040]">{title}</div>
          <Icon className="h-4 w-4 text-[#404040]" />
        </div>
        <div className="text-2xl font-semibold text-black">{value}</div>
        {trend && (
          <div className="text-xs text-[#404040] mt-1">{trend}</div>
        )}
      </div>
    </Card>
  )

  const BarChart = ({ 
    data, 
    title 
  }: { 
    data: Record<string, number>
    title: string
  }) => {
    const maxValue = Math.max(...Object.values(data), 1)
    
    return (
      <Card className="border border-[#E5E5E5] bg-white">
        <div className="p-5">
          <h3 className="text-sm font-semibold text-black mb-4">{title}</h3>
          <div className="space-y-3">
            {Object.entries(data).map(([key, value]) => (
              <div key={key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-[#404040] capitalize">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs font-semibold text-black">{value}</span>
                </div>
                <div className="h-2 bg-[#F5F5F5] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-black transition-all"
                    style={{ width: `${(value / maxValue) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>
    )
  }

  const PieChart = ({ 
    data, 
    title 
  }: { 
    data: Record<string, number>
    title: string
  }) => {
    const total = Object.values(data).reduce((sum, val) => sum + val, 0)
    if (total === 0) {
      return (
        <Card className="border border-[#E5E5E5] bg-white">
          <div className="p-5">
            <h3 className="text-sm font-semibold text-black mb-4">{title}</h3>
            <div className="text-center py-8 text-[#404040] text-sm">No data available</div>
          </div>
        </Card>
      )
    }

    const colors = ["#000000", "#404040", "#808080", "#C0C0C0"]
    let currentAngle = 0

    return (
      <Card className="border border-[#E5E5E5] bg-white">
        <div className="p-5">
          <h3 className="text-sm font-semibold text-black mb-4">{title}</h3>
          <div className="flex items-center gap-6">
            <div className="relative w-32 h-32">
              <svg viewBox="0 0 100 100" className="transform -rotate-90">
                {Object.entries(data).map(([key, value], index) => {
                  const percentage = (value / total) * 100
                  const angle = (percentage / 100) * 360
                  const largeArc = percentage > 50 ? 1 : 0
                  
                  const x1 = 50 + 50 * Math.cos((currentAngle * Math.PI) / 180)
                  const y1 = 50 + 50 * Math.sin((currentAngle * Math.PI) / 180)
                  const x2 = 50 + 50 * Math.cos(((currentAngle + angle) * Math.PI) / 180)
                  const y2 = 50 + 50 * Math.sin(((currentAngle + angle) * Math.PI) / 180)
                  
                  const pathData = [
                    `M 50 50`,
                    `L ${x1} ${y1}`,
                    `A 50 50 0 ${largeArc} 1 ${x2} ${y2}`,
                    `Z`,
                  ].join(" ")

                  currentAngle += angle
                  
                  return (
                    <path
                      key={key}
                      d={pathData}
                      fill={colors[index % colors.length]}
                    />
                  )
                })}
              </svg>
            </div>
            <div className="flex-1 space-y-2">
              {Object.entries(data).map(([key, value], index) => (
                <div key={key} className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: colors[index % colors.length] }}
                  />
                  <span className="text-xs text-[#404040] capitalize flex-1">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs font-semibold text-black">
                    {value} ({(value / total * 100).toFixed(1)}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    )
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-white p-6">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-black">Analytics</h1>
                <p className="text-sm text-[#404040] mt-1">
                  {lastUpdated && `Last updated: ${lastUpdated.toLocaleString()}`}
                </p>
              </div>
              <Button
                variant="outline"
                onClick={loadAnalytics}
                disabled={loading}
                className="h-9"
              >
                <RefreshCw className={`mr-2 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>

            {loading ? (
              <div className="text-center py-12">
                <p className="text-[#404040]">Loading analytics...</p>
              </div>
            ) : !analytics ? (
              <Card className="border border-[#E5E5E5] bg-white">
                <div className="p-12 text-center">
                  <p className="text-[#404040]">No data available</p>
                </div>
              </Card>
            ) : (
              <>
                {/* Key Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatCard
                    title="Total Workspaces"
                    value={analytics.totalWorkspaces}
                    icon={FolderOpen}
                  />
                  <StatCard
                    title="Total Documents"
                    value={analytics.totalDocuments}
                    icon={FileText}
                  />
                  <StatCard
                    title="Matched Groups"
                    value={analytics.totalMatchedGroups}
                    icon={CheckCircle2}
                  />
                  <StatCard
                    title="Total Discrepancies"
                    value={analytics.totalDiscrepancies}
                    icon={AlertTriangle}
                  />
                </div>

                {/* Secondary Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatCard
                    title="Perfect Matches"
                    value={analytics.perfectMatches}
                    icon={CheckCircle2}
                  />
                  <StatCard
                    title="Partial Matches"
                    value={analytics.partialMatches}
                    icon={XCircle}
                  />
                  <StatCard
                    title="Total Amount"
                    value={`$${analytics.totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                    icon={DollarSign}
                    trend="Sum of invoice amounts"
                  />
                  <StatCard
                    title="Total Difference"
                    value={`$${analytics.totalDifference.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                    icon={TrendingUp}
                    trend="Sum of absolute differences"
                  />
                </div>

                {/* Charts Row 1 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <PieChart
                    data={analytics.documentsByType}
                    title="Documents by Type"
                  />
                  <PieChart
                    data={analytics.processingStatus}
                    title="Processing Status"
                  />
                </div>

                {/* Charts Row 2 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <BarChart
                    data={analytics.discrepanciesByType}
                    title="Discrepancies by Type"
                  />
                  <BarChart
                    data={analytics.discrepanciesBySeverity}
                    title="Discrepancies by Severity"
                  />
                </div>

                {/* Workspaces List */}
                <Card className="border border-[#E5E5E5] bg-white">
                  <div className="p-5">
                    <h3 className="text-sm font-semibold text-black mb-4">Workspaces Overview</h3>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {workspacesRes?.data?.map((workspace) => {
                        const workspaceData = analytics.workspacesData?.[workspace.id]
                        return (
                          <div
                            key={workspace.id}
                            className="flex items-center justify-between p-3 bg-[#FAFAFA] rounded border border-[#E5E5E5]"
                          >
                            <div className="flex-1">
                              <div className="font-medium text-sm text-black">{workspace.name}</div>
                              <div className="text-xs text-[#404040] mt-1">
                                {workspaceData?.documentCount || 0} documents • {workspaceData?.matchedGroups || 0} matches
                              </div>
                            </div>
                            <div className="text-xs text-[#404040]">
                              {new Date(workspace.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </Card>
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

