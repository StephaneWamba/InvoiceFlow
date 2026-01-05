"use client"

import { useState, useEffect, useCallback } from "react"
import { X, Download, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { documentsApi } from "@/lib/api"

interface PDFViewerProps {
  documentId: string
  fileName: string
  onClose: () => void
}

export function PDFViewer({ documentId, fileName, onClose }: PDFViewerProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  const loadPDF = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await documentsApi.download(documentId)
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      setPdfUrl(url)
    } catch (err: any) {
      console.error("Failed to load PDF:", err)
      setError(err.response?.data?.detail || "Failed to load PDF document")
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    loadPDF()
  }, [loadPDF])

  // Cleanup: revoke object URL when component unmounts or PDF changes
  useEffect(() => {
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl)
      }
    }
  }, [pdfUrl])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const response = await documentsApi.download(documentId)
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', fileName)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error("Failed to download PDF:", err)
      alert("Failed to download document. Please try again.")
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
      <div className="relative w-full h-full max-w-7xl max-h-[90vh] m-4 bg-white rounded-lg shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#E5E5E5]">
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-semibold text-black truncate">{fileName}</h2>
          </div>
          <div className="flex items-center gap-2 ml-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={downloading || !pdfUrl}
              className="h-8"
            >
              <Download className={`mr-2 h-3.5 w-3.5 ${downloading ? 'animate-spin' : ''}`} />
              {downloading ? "Downloading..." : "Download"}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-8 w-8"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* PDF Content */}
        <div className="flex-1 overflow-hidden relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white">
              <div className="text-center">
                <Loader2 className="h-8 w-8 animate-spin text-[#404040] mx-auto mb-2" />
                <p className="text-sm text-[#404040]">Loading PDF...</p>
              </div>
            </div>
          )}
          
          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-white">
              <div className="text-center p-6">
                <p className="text-sm text-red-600 mb-4">{error}</p>
                <Button variant="outline" onClick={loadPDF} size="sm">
                  Retry
                </Button>
              </div>
            </div>
          )}

          {pdfUrl && !loading && !error && (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              title={fileName}
            />
          )}
        </div>
      </div>
    </div>
  )
}

