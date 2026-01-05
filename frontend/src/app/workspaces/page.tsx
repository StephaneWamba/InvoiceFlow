"use client"

import { useState, useEffect } from "react"
import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Plus, Trash2, FolderOpen, Calendar, FileText, AlertCircle, CheckCircle2, Trash } from "lucide-react"
import { workspacesApi, documentsApi, matchingApi, type Workspace, type Document, type MatchingResult } from "@/lib/api"
import { useRouter } from "next/navigation"

export default function WorkspacesPage() {
  const router = useRouter()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspaceStats, setWorkspaceStats] = useState<Record<string, {
    documentCount: number
    matchedGroups: number
    totalDiscrepancies: number
    status: string
  }>>({})
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [deletingAll, setDeletingAll] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    loadWorkspaces()
  }, [])

  const loadWorkspaces = async () => {
    setLoading(true)
    try {
      const response = await workspacesApi.list()
      setWorkspaces(response.data)
      
      // Load stats for each workspace
      const stats: Record<string, any> = {}
      await Promise.all(
        response.data.map(async (workspace) => {
          try {
            const [docsRes, resultsRes] = await Promise.all([
              documentsApi.list(workspace.id).catch(() => ({ data: [] })),
              matchingApi.getResults(workspace.id).catch(() => ({ data: [] })),
            ])
            
            const documents: Document[] = docsRes.data || []
            const results: MatchingResult[] = resultsRes.data || []
            
            const totalDiscrepancies = results.reduce(
              (sum, r) => sum + r.discrepancies.length,
              0
            )
            
            const perfectMatches = results.filter((r) => r.discrepancies.length === 0).length
            let status = "No Data"
            if (results.length > 0) {
              status = perfectMatches === results.length ? "Perfect" : "Partial"
            } else if (documents.length > 0) {
              status = "Processing"
            }
            
            stats[workspace.id] = {
              documentCount: documents.length,
              matchedGroups: results.length,
              totalDiscrepancies,
              status,
            }
          } catch (error) {
            console.error(`Failed to load stats for workspace ${workspace.id}:`, error)
            stats[workspace.id] = {
              documentCount: 0,
              matchedGroups: 0,
              totalDiscrepancies: 0,
              status: "Unknown",
            }
          }
        })
      )
      setWorkspaceStats(stats)
    } catch (error) {
      console.error("Failed to load workspaces:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateWorkspace = async () => {
    setCreating(true)
    try {
      const name = `Workspace ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()}`
      await workspacesApi.create(name, true)
      await loadWorkspaces()
    } catch (error) {
      console.error("Failed to create workspace:", error)
      alert("Failed to create workspace. Please try again.")
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteWorkspace = async (workspaceId: string) => {
    if (!confirm("Are you sure you want to delete this workspace? This will delete all associated documents and matching results.")) {
      return
    }
    
    setDeleting(workspaceId)
    try {
      const response = await workspacesApi.delete(workspaceId)
      console.log("Delete response:", response.data)
      
      // Check for warnings
      if (response.data?.storage_warnings && response.data.storage_warnings.length > 0) {
        console.warn("Some storage files failed to delete:", response.data.storage_warnings)
        // Don't show alert for storage warnings - deletion succeeded
      }
      
      await loadWorkspaces()
    } catch (error: any) {
      console.error("Failed to delete workspace:", error)
      const errorMessage = error.response?.data?.detail || error.message || "Failed to delete workspace. Please try again."
      alert(`Failed to delete workspace: ${errorMessage}`)
    } finally {
      setDeleting(null)
    }
  }

  const handleDeleteAll = async () => {
    if (workspaces.length === 0) return
    
    const confirmMessage = `Are you sure you want to delete ALL ${workspaces.length} workspace(s)?\n\nThis will permanently delete:\n- All workspaces\n- All documents\n- All matching results\n\nThis action cannot be undone!`
    
    if (!confirm(confirmMessage)) {
      return
    }
    
    setDeletingAll(true)
    const workspaceIds = [...workspaces.map(w => w.id)] // Store IDs before deletion
    try {
      // Delete all workspaces in parallel
      const results = await Promise.allSettled(
        workspaceIds.map(workspaceId => 
          workspacesApi.delete(workspaceId)
        )
      )
      
      // Check results
      const successful = results.filter(r => r.status === 'fulfilled').length
      const failed = results.filter(r => r.status === 'rejected').length
      
      if (failed > 0) {
        results.forEach((result, index) => {
          if (result.status === 'rejected') {
            console.error(`Failed to delete workspace ${workspaceIds[index]}:`, result.reason)
          }
        })
      }
      
      // Reload workspaces to get updated list
      await loadWorkspaces()
      
      if (failed === 0) {
        alert(`Successfully deleted ${successful} workspace(s).`)
      } else {
        alert(`Deleted ${successful} workspace(s), but ${failed} failed. Please check the console for details.`)
      }
    } catch (error) {
      console.error("Failed to delete all workspaces:", error)
      alert("Failed to delete workspaces. Please check the console for details.")
      // Still reload to get current state
      await loadWorkspaces()
    } finally {
      setDeletingAll(false)
    }
  }

  const handleOpenWorkspace = (workspaceId: string) => {
    router.push(`/?workspace=${workspaceId}`)
  }

  // Prevent hydration mismatch by not rendering until mounted
  if (!mounted) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto bg-white p-6">
            <div className="max-w-7xl mx-auto space-y-6">
              <div className="text-center py-12">
                <p className="text-[#404040]">Loading...</p>
              </div>
            </div>
          </main>
        </div>
      </div>
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
                <h1 className="text-2xl font-semibold tracking-tight text-black">Workspaces</h1>
                <p className="text-sm text-[#404040] mt-1">
                  Manage your document workspaces and view their status
                </p>
              </div>
              <div className="flex items-center gap-2">
                {workspaces.length > 0 && (
                  <Button
                    variant="outline"
                    onClick={handleDeleteAll}
                    disabled={deletingAll || creating || loading}
                    className="h-9 text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash className="mr-2 h-3.5 w-3.5" />
                    {deletingAll ? "Deleting..." : "Delete All"}
                  </Button>
                )}
                <Button
                  onClick={handleCreateWorkspace}
                  disabled={creating || loading}
                  className="h-9"
                >
                  <Plus className="mr-2 h-3.5 w-3.5" />
                  {creating ? "Creating..." : "New Workspace"}
                </Button>
              </div>
            </div>

            {/* Workspaces Grid */}
            {loading ? (
              <div className="text-center py-12">
                <p className="text-[#404040]">Loading workspaces...</p>
              </div>
            ) : workspaces.length === 0 ? (
              <Card className="border border-[#E5E5E5] bg-white">
                <div className="p-12 text-center">
                  <FolderOpen className="h-12 w-12 text-[#404040] mx-auto mb-4" />
                  <p className="text-[#404040] mb-4">No workspaces yet</p>
                  <Button onClick={handleCreateWorkspace} disabled={creating}>
                    <Plus className="mr-2 h-3.5 w-3.5" />
                    Create Your First Workspace
                  </Button>
                </div>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {workspaces.map((workspace) => {
                  const stats = workspaceStats[workspace.id] || {
                    documentCount: 0,
                    matchedGroups: 0,
                    totalDiscrepancies: 0,
                    status: "Unknown",
                  }
                  
                  // Format date consistently to avoid hydration issues
                  const createdDate = mounted ? new Date(workspace.created_at).toLocaleDateString() : workspace.created_at
                  
                  return (
                    <Card
                      key={workspace.id}
                      className="border border-[#E5E5E5] bg-white hover:shadow-md transition-shadow"
                    >
                      <div className="p-5">
                        {/* Header */}
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex-1">
                            <h3 className="font-semibold text-black mb-1 truncate">
                              {workspace.name}
                            </h3>
                            <div className="flex items-center gap-2 text-xs text-[#404040]">
                              <Calendar className="h-3 w-3" />
                              <span>
                                {createdDate}
                              </span>
                              <span className="text-[#E5E5E5]">•</span>
                              <span>
                                {workspace.is_temporary ? "Temporary" : "Saved"}
                              </span>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-[#404040] hover:text-red-600"
                            onClick={() => handleDeleteWorkspace(workspace.id)}
                            disabled={deleting === workspace.id || deletingAll}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>

                        {/* Stats */}
                        <div className="space-y-3 mb-4">
                          <div className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2 text-[#404040]">
                              <FileText className="h-4 w-4" />
                              <span>Documents</span>
                            </div>
                            <span className="font-semibold text-black">{stats.documentCount}</span>
                          </div>
                          <div className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2 text-[#404040]">
                              <CheckCircle2 className="h-4 w-4" />
                              <span>Matched Groups</span>
                            </div>
                            <span className="font-semibold text-black">{stats.matchedGroups}</span>
                          </div>
                          <div className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2 text-[#404040]">
                              <AlertCircle className="h-4 w-4" />
                              <span>Discrepancies</span>
                            </div>
                            <span className="font-semibold text-black">{stats.totalDiscrepancies}</span>
                          </div>
                        </div>

                        {/* Status Badge */}
                        <div className="flex items-center justify-between pt-4 border-t border-[#E5E5E5]">
                          <div className="flex items-center gap-2">
                            <div
                              className={`h-2 w-2 rounded-full ${
                                stats.status === "Perfect"
                                  ? "bg-green-500"
                                  : stats.status === "Partial"
                                  ? "bg-yellow-500"
                                  : stats.status === "Processing"
                                  ? "bg-blue-500"
                                  : "bg-gray-400"
                              }`}
                            />
                            <span className="text-xs text-[#404040]">{stats.status}</span>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenWorkspace(workspace.id)}
                            className="h-7 text-xs"
                          >
                            Open
                          </Button>
                        </div>
                      </div>
                    </Card>
                  )
                })}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}


