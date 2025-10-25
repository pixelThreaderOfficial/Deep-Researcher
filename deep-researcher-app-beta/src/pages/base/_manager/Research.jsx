import React from 'react'
import { motion } from 'framer-motion'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  BookOpen,
  Clock,
  FileText,
  Tag,
  Calendar
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const Research = () => {
  const { id } = useParams()
  const navigate = useNavigate()

  // Mock data - in real app, fetch by id
  const research = {
    id: id,
    title: 'Impact of AI on Healthcare Systems',
    createdAt: '2024-01-15T10:30:00',
    status: 'completed',
    model: 'GPT-4',
    durationMs: 245000,
    sourcesCount: 15,
    tags: ['AI', 'Healthcare', 'Technology']
  }

  // Format duration from milliseconds to mm:ss
  const formatDuration = (durationMs) => {
    if (durationMs === 0) return '--:--'
    const totalSeconds = Math.floor(durationMs / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }

  // Format date
  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Get status badge color
  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'running':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      case 'failed':
        return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'queued':
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-4"
      >
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/app/researches')}
            className="text-gray-400 hover:text-gray-200 p-2"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <motion.div
            whileHover={{ rotate: 180 }}
            transition={{ duration: 0.3 }}
          >
            <BookOpen className="w-6 h-6 text-blue-400" />
          </motion.div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-semibold text-gray-100">{research.title}</h1>
              <Badge className={`${getStatusColor(research.status)} text-xs`}>
                {research.status.charAt(0).toUpperCase() + research.status.slice(1)}
              </Badge>
            </div>
            <p className="text-sm text-gray-400">Research ID: {research.id}</p>
          </div>
        </div>

        {/* Metadata Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-gray-400">Duration</span>
            </div>
            <div className="text-lg font-bold text-gray-200">
              {formatDuration(research.durationMs)}
            </div>
          </div>

          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-green-400" />
              <span className="text-sm font-medium text-gray-400">Sources</span>
            </div>
            <div className="text-lg font-bold text-gray-200">
              {research.sourcesCount}
            </div>
          </div>

          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-medium text-gray-400">Created</span>
            </div>
            <div className="text-sm font-medium text-gray-200">
              {formatDate(research.createdAt)}
            </div>
          </div>

          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-gray-400">Model</span>
            </div>
            <div className="text-sm font-bold text-gray-200">
              {research.model}
            </div>
          </div>
        </div>

        {/* Tags */}
        {research.tags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap bg-gray-800 border border-gray-600 rounded-lg p-4">
            <Tag className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="text-sm text-gray-400">Tags:</span>
            {research.tags.map((tag, tagIndex) => (
              <Badge
                key={tagIndex}
                variant="outline"
                className="bg-gray-700/50 text-gray-300 border-gray-600"
              >
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </motion.div>

      {/* Content Placeholder */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
        className="bg-gray-800 border border-gray-600 rounded-lg p-6"
      >
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Research Content</h2>
        <p className="text-gray-400">
          Research detail content will be displayed here. This is a placeholder for the full research results,
          findings, and detailed information.
        </p>
      </motion.div>
    </div>
  )
}

export default Research