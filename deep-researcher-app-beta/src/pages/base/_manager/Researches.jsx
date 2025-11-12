import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Clock,
  FileText,
  Tag,
  BookOpen,
  ChevronRight,
  RefreshCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { fetchResearches, getStats } from '@/lib/researchApi'

const Researches = () => {
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [researches, setResearches] = useState([])
  const [stats, setStats] = useState(null)
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchResearches()
      setResearches(data)
    } catch (e) {
      setError(e?.message || 'Failed to load research history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    const loadStats = async () => {
      try {
        const s = await getStats()
        setStats(s)
      } catch (e) {
        // non-fatal; keep stats null
      }
    }
    loadStats()
  }, [])

  // Format duration from milliseconds to mm:ss
  const formatDuration = (durationSec) => {
    if (!durationSec || durationSec <= 0) return '--:--'
    const totalSeconds = Math.floor(durationSec)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return '—'
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
  const filteredResearches = useMemo(() => {
    const q = searchQuery.toLowerCase().trim()
    if (!q) return researches
    return researches.filter(research =>
      (research.title || '').toLowerCase().includes(q) ||
      (research.model || '').toLowerCase().includes(q) ||
      (Array.isArray(research.tags) ? research.tags : []).some(tag => (tag || '').toLowerCase().includes(q)) ||
      (research.status || '').toLowerCase().includes(q)
    )
  }, [researches, searchQuery])

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
          <motion.div>
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

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Total</div>
            <div className="text-2xl font-bold text-blue-400">{stats?.total_researches ?? researches.length}</div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Completed</div>
            <div className="text-2xl font-bold text-green-400">
              {stats?.completed ?? researches.filter(r => r.status === 'completed').length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Running</div>
            <div className="text-2xl font-bold text-blue-400">
              {stats?.running ?? researches.filter(r => r.status === 'running').length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-400 mb-1">Failed</div>
            <div className="text-2xl font-bold text-red-400">
              {stats?.failed ?? researches.filter(r => r.status === 'failed').length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-gray-400 mb-1">Actions</div>
              <div className="text-xs text-gray-500">Reload latest</div>
            </div>
            <Button size="sm" variant="outline" onClick={load} disabled={loading} className="gap-2">
              <RefreshCcw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
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

      {/* Loading / Error */}
      {loading && (
        <div className="flex items-center justify-center py-16 text-gray-400">Loading researches…</div>
      )}
      {error && !loading && (
        <div className="flex items-center justify-center py-4">
          <div className="text-red-400 text-sm">{error}</div>
        </div>
      )}

      {/* Researches Grid */}
      {!loading && filteredResearches.length > 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.3 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {filteredResearches.map((research, index) => (
            <motion.div
              key={research.slug || research.id || index}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2, delay: index * 0.05 }}
              onClick={() => navigate(`/app/research/${research.slug || research.id}`)}
              className="bg-gray-800 border border-gray-600 rounded-lg p-4 hover:bg-gray-700 transition-all duration-200 group cursor-pointer"
            >
              {/* Research Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-gray-200 mb-2 line-clamp-2">{research.title}</h3>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className={`${getStatusColor(research.status)} text-xs px-2 py-0.5`}>
                      {(research.status || '').charAt(0).toUpperCase() + (research.status || '').slice(1)}
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
                    {formatDuration(research.durationSec)}
                  </span>
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    {(research.resources_used?.length ?? 0)} sources
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">{research.model || '—'}</span>
                  <span className="text-gray-500">{formatDate(research.datetime_start)}</span>
                </div>
              </div>

              {/* Tags */}
              {Array.isArray(research.tags) && research.tags.length > 0 && (
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