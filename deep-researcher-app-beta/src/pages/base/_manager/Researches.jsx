import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Clock,
  FileText,
  Tag,
  BookOpen,
  ChevronRight
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'

const Researches = () => {
  const [searchQuery, setSearchQuery] = useState('')
  const navigate = useNavigate()

  // Mock data for researches
  const researches = [
    {
      id: '1',
      title: 'Impact of AI on Healthcare Systems',
      createdAt: '2024-01-15T10:30:00',
      status: 'completed',
      model: 'GPT-4',
      durationMs: 245000,
      sourcesCount: 15,
      tags: ['AI', 'Healthcare', 'Technology']
    },
    {
      id: '2',
      title: 'Climate Change Mitigation Strategies',
      createdAt: '2024-01-14T14:20:00',
      status: 'completed',
      model: 'Claude 3.5',
      durationMs: 180000,
      sourcesCount: 22,
      tags: ['Climate', 'Environment', 'Policy']
    },
    {
      id: '3',
      title: 'Blockchain Technology in Supply Chain',
      createdAt: '2024-01-13T09:15:00',
      status: 'running',
      model: 'GPT-4',
      durationMs: 120000,
      sourcesCount: 8,
      tags: ['Blockchain', 'Supply Chain', 'Business']
    },
    {
      id: '4',
      title: 'Quantum Computing Applications',
      createdAt: '2024-01-12T16:45:00',
      status: 'completed',
      model: 'Claude 3.5',
      durationMs: 300000,
      sourcesCount: 18,
      tags: ['Quantum', 'Computing', 'Physics']
    },
    {
      id: '5',
      title: 'Renewable Energy Investment Trends',
      createdAt: '2024-01-11T11:00:00',
      status: 'failed',
      model: 'GPT-4',
      durationMs: 90000,
      sourcesCount: 5,
      tags: ['Energy', 'Investment', 'Sustainability']
    },
    {
      id: '6',
      title: 'Machine Learning in Autonomous Vehicles',
      createdAt: '2024-01-10T13:30:00',
      status: 'completed',
      model: 'GPT-4',
      durationMs: 210000,
      sourcesCount: 12,
      tags: ['ML', 'Automotive', 'AI']
    },
    {
      id: '7',
      title: 'Cybersecurity Threats in 2024',
      createdAt: '2024-01-09T08:20:00',
      status: 'queued',
      model: 'Claude 3.5',
      durationMs: 0,
      sourcesCount: 0,
      tags: ['Security', 'Technology', 'Risk']
    },
    {
      id: '8',
      title: 'Future of Remote Work Post-Pandemic',
      createdAt: '2024-01-08T15:10:00',
      status: 'completed',
      model: 'GPT-4',
      durationMs: 195000,
      sourcesCount: 20,
      tags: ['Work', 'Business', 'Trends']
    },
    {
      id: '9',
      title: 'Gene Editing Ethics and Regulations',
      createdAt: '2024-01-07T10:00:00',
      status: 'completed',
      model: 'Claude 3.5',
      durationMs: 270000,
      sourcesCount: 16,
      tags: ['Biotech', 'Ethics', 'Healthcare']
    }
  ]

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
      month: 'short',
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

  // Filter researches
  const filteredResearches = researches.filter(research =>
    research.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    research.model.toLowerCase().includes(searchQuery.toLowerCase()) ||
    research.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase())) ||
    research.status.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <motion.div
            whileHover={{ rotate: 180 }}
            transition={{ duration: 0.3 }}
          >
            <BookOpen className="w-6 h-6 text-blue-400" />
          </motion.div>
          <div>
            <h1 className="text-xl font-semibold text-gray-100">Research History</h1>
            <p className="text-sm text-gray-400">View and manage all your research sessions</p>
          </div>
        </div>

        <div className="text-right">
          <div className="text-2xl font-bold text-blue-400">{filteredResearches.length}</div>
          <div className="text-xs text-gray-500">researches</div>
        </div>
      </motion.div>

      {/* Research Summary */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
        className="bg-gray-800/50 border border-gray-600 rounded-lg p-6"
      >
        <div className="flex items-center gap-3 mb-4">
          <motion.div
            whileHover={{ scale: 1.1 }}
            className="w-2 h-2 bg-blue-500 rounded-full"
          />
          <h3 className="text-lg font-medium text-gray-200">Research Summary</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Total</div>
            <div className="text-2xl font-bold text-blue-400">
              {researches.length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Completed</div>
            <div className="text-2xl font-bold text-green-400">
              {researches.filter(r => r.status === 'completed').length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Running</div>
            <div className="text-2xl font-bold text-blue-400">
              {researches.filter(r => r.status === 'running').length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Failed</div>
            <div className="text-2xl font-bold text-red-400">
              {researches.filter(r => r.status === 'failed').length}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Search Bar */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
        className="relative"
      >
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
        <Input
          placeholder="Search researches by title, model, status, or tags..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 bg-gray-800 border-gray-600 text-gray-100 focus:border-blue-500"
        />
      </motion.div>

      {/* Researches Grid */}
      {filteredResearches.length > 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.3 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {filteredResearches.map((research, index) => (
            <motion.div
              key={research.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2, delay: index * 0.05 }}
              onClick={() => navigate(`/app/research/${research.id}`)}
              className="bg-gray-800 border border-gray-600 rounded-lg p-4 hover:bg-gray-700 transition-all duration-200 group cursor-pointer"
            >
              {/* Research Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-gray-200 mb-2 line-clamp-2">
                    {research.title}
                  </h3>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className={`${getStatusColor(research.status)} text-xs px-2 py-0.5`}>
                      {research.status.charAt(0).toUpperCase() + research.status.slice(1)}
                    </Badge>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-blue-400 transition-colors flex-shrink-0 mt-1" />
              </div>

              {/* Research Details */}
              <div className="space-y-2 text-xs text-gray-400">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatDuration(research.durationMs)}
                  </span>
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    {research.sourcesCount} sources
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">{research.model}</span>
                  <span className="text-gray-500">{formatDate(research.createdAt)}</span>
                </div>
              </div>

              {/* Tags */}
              {research.tags.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <div className="flex items-center gap-1 flex-wrap">
                    <Tag className="w-3 h-3 text-gray-500 flex-shrink-0" />
                    {research.tags.map((tag, tagIndex) => (
                      <span
                        key={tagIndex}
                        className="text-xs px-2 py-0.5 bg-gray-700/50 text-gray-400 rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.3 }}
          className="flex items-center justify-center py-16 text-gray-500"
        >
          <div className="text-center">
            <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <h3 className="text-lg font-medium mb-2">No researches found</h3>
            <p>Try adjusting your search or start a new research</p>
            {searchQuery && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSearchQuery('')}
                className="mt-4"
              >
                Clear Search
              </Button>
            )}
          </div>
        </motion.div>
      )}

    </div>
  )
}

export default Researches