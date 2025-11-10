import React, { useState, useMemo, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useParams, useNavigate } from 'react-router-dom'
import {
    FileText,
    FileSpreadsheet,
    Presentation,
    File,
    Music,
    Image,
    ArrowLeft,
    Search,
    Download,
    Eye,
    Trash2,
    SortAsc,
    SortDesc,
    Filter,
    RefreshCw,
    AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
    DropdownMenuLabel,
    DropdownMenuPortal
} from "@/components/ui/dropdown-menu"
import { fetchFiles, deleteFile, getDownloadUrl } from '@/lib/filesApi'
import { toast } from 'sonner'

const FileView = () => {
    const { category } = useParams()
    const navigate = useNavigate()
    const [searchQuery, setSearchQuery] = useState('')
    const [sortBy, setSortBy] = useState('date')
    const [sortOrder, setSortOrder] = useState('desc')
    const [filterBy, setFilterBy] = useState('all')
    const [allFiles, setAllFiles] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    // Load files from API
    useEffect(() => {
        loadFiles()
    }, [category])

    const loadFiles = async () => {
        try {
            setLoading(true)
            setError(null)
            const { files } = await fetchFiles({
                category: getCategoryApiName(category),
                limit: 1000
            })
            setAllFiles(files)
        } catch (err) {
            console.error('Failed to load files:', err)
            setError(err.message)
            toast.error('Failed to load files: ' + err.message)
        } finally {
            setLoading(false)
        }
    }

    // Map UI category names to API category names
    const getCategoryApiName = (cat) => {
        switch (cat) {
            case 'docs':
                return 'documents'
            case 'audio':
                return 'audios'
            case 'images':
                return 'images'
            case 'videos':
                return 'videos'
            default:
                return 'documents'
        }
    }

    // Get category info
    const getCategoryInfo = (cat) => {
        switch (cat) {
            case 'docs':
                return {
                    title: 'Documents',
                    description: 'All documents from your conversations',
                    icon: FileText,
                    color: 'text-blue-400'
                }
            case 'audio':
                return {
                    title: 'Audio Files',
                    description: 'All audio recordings from your conversations',
                    icon: Music,
                    color: 'text-purple-400'
                }
            case 'images':
                return {
                    title: 'Images',
                    description: 'All images from your conversations',
                    icon: Image,
                    color: 'text-cyan-400'
                }
            default:
                return {
                    title: 'Files',
                    description: 'All files from your conversations',
                    icon: File,
                    color: 'text-gray-400'
                }
        }
    }

    const categoryInfo = getCategoryInfo(category)

    // Sorting and filtering functions
    const sortFiles = (files) => {
        return [...files].sort((a, b) => {
            let comparison = 0

            switch (sortBy) {
                case 'name':
                    comparison = a.name.localeCompare(b.name)
                    break
                case 'date':
                    // Use raw date string for more accurate comparison
                    const dateA = a.dateCreated || a.date || 0
                    const dateB = b.dateCreated || b.date || 0
                    comparison = new Date(dateA).getTime() - new Date(dateB).getTime()
                    // Fallback if dates are invalid
                    if (isNaN(comparison)) {
                        comparison = String(dateA).localeCompare(String(dateB))
                    }
                    break
                case 'size':
                    comparison = (a.sizeBytes || 0) - (b.sizeBytes || 0)
                    break
                default:
                    comparison = 0
            }

            return sortOrder === 'asc' ? comparison : -comparison
        })
    }

    const filterBySource = (files) => {
        if (filterBy === 'all') return files
        if (filterBy === 'ai') return files.filter(file => file.ioTag === 'generated')
        if (filterBy === 'user') return files.filter(file => file.ioTag === 'uploaded')
        if (filterBy === 'downloaded') return files.filter(file => file.ioTag === 'downloaded')
        return files
    }

    // Filter files by category, search query, source, then sort
    const filteredFiles = useMemo(() => {
        let categoryFiles = [...allFiles]

        // Apply search filter
        if (searchQuery) {
            categoryFiles = categoryFiles.filter(file =>
                file.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                file.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (file.chat && file.chat.toLowerCase().includes(searchQuery.toLowerCase())) ||
                file.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (file.tags && file.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase())))
            )
        }

        // Apply source filter
        categoryFiles = filterBySource(categoryFiles)

        // Apply sorting
        return sortFiles(categoryFiles)
    }, [allFiles, searchQuery, sortBy, sortOrder, filterBy])

    const getFileIcon = (fileName) => {
        const ext = fileName.split('.').pop()?.toLowerCase()
        switch (ext) {
            case 'docx':
            case 'doc':
                return <FileText className="w-5 h-5 text-blue-400" />
            case 'xlsx':
            case 'xls':
            case 'csv':
                return <FileSpreadsheet className="w-5 h-5 text-green-400" />
            case 'pptx':
            case 'ppt':
                return <Presentation className="w-5 h-5 text-orange-400" />
            case 'pdf':
                return <File className="w-5 h-5 text-red-400" />
            case 'txt':
            case 'md':
            case 'markdown':
                return <FileText className="w-5 h-5 text-gray-400" />
            case 'mp3':
            case 'wav':
            case 'ogg':
            case 'flac':
                return <Music className="w-5 h-5 text-purple-400" />
            case 'jpg':
            case 'jpeg':
            case 'png':
            case 'webp':
            case 'gif':
            case 'svg':
            case 'bmp':
                return <Image className="w-5 h-5 text-cyan-400" />
            default:
                return <File className="w-5 h-5 text-gray-400" />
        }
    }

    const handleDeleteFile = async (file) => {
        if (window.confirm(`Are you sure you want to delete "${file.name}"?`)) {
            try {
                await deleteFile(file.id)
                toast.success(`File "${file.name}" deleted successfully`)
                // Reload files
                loadFiles()
            } catch (err) {
                console.error('Delete failed:', err)
                toast.error('Failed to delete file: ' + err.message)
            }
        }
    }

    const handleDownloadFile = (file) => {
        const url = getDownloadUrl(file.id)
        window.open(url, '_blank')
    }

    const handleViewFile = (file) => {
        // TODO: Implement file preview modal
        toast.info('File preview coming soon!')
        console.log('View file:', file)
    }

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
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate('/app/files')}
                        className="text-gray-400 hover:text-gray-200 p-2"
                    >
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <motion.div
                        whileHover={{ rotate: 180 }}
                        transition={{ duration: 0.3 }}
                    >
                        <categoryInfo.icon className={`w-6 h-6 ${categoryInfo.color}`} />
                    </motion.div>
                    <div>
                        <h1 className="text-xl font-semibold text-gray-100">{categoryInfo.title}</h1>
                        <p className="text-sm text-gray-400">{categoryInfo.description}</p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={loadFiles}
                        disabled={loading}
                        className="text-gray-400 hover:text-gray-200"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    <div className="text-right">
                        <div className="text-2xl font-bold text-blue-400">{filteredFiles.length}</div>
                        <div className="text-xs text-gray-500">files</div>
                    </div>
                </div>
            </motion.div>

            {/* Error Alert */}
            {error && (
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-red-500/10 border border-red-500/50 rounded-lg p-4 flex items-center gap-3"
                >
                    <AlertCircle className="w-5 h-5 text-red-400" />
                    <div>
                        <p className="text-sm text-red-400 font-medium">Failed to load files</p>
                        <p className="text-xs text-red-400/70">{error}</p>
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={loadFiles}
                        className="ml-auto text-red-400 hover:text-red-300"
                    >
                        Retry
                    </Button>
                </motion.div>
            )}

            {/* Search and Controls */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.1 }}
                className="flex flex-col sm:flex-row gap-4"
            >
                {/* Search Bar */}
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                        placeholder={`Search ${categoryInfo.title.toLowerCase()} by name, type, or chat...`}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-10 bg-gray-800 border-gray-600 text-gray-100 focus:border-blue-500"
                    />
                </div>

                {/* Sort and Filter Controls */}
                <div className="flex gap-2">
                    {/* Sort Dropdown */}
                    <DropdownMenu>
                        <DropdownMenuTrigger>
                            <Button variant="outline" className="bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700">
                                <SortAsc className="w-4 h-4 mr-2" />
                                Sort
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuPortal>
                            <DropdownMenuContent className="bg-gray-800 border-gray-600 z-50">
                                <DropdownMenuLabel className="text-gray-300">Sort by</DropdownMenuLabel>
                                <DropdownMenuSeparator className="bg-gray-600" />
                                <DropdownMenuItem
                                    onClick={() => setSortBy('name')}
                                    className="text-gray-300 hover:bg-gray-700 focus:bg-gray-700"
                                >
                                    Name {sortBy === 'name' && (sortOrder === 'asc' ? '↑' : '↓')}
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => setSortBy('date')}
                                    className="text-gray-300 hover:bg-gray-700 focus:bg-gray-700"
                                >
                                    Date {sortBy === 'date' && (sortOrder === 'asc' ? '↑' : '↓')}
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => setSortBy('size')}
                                    className="text-gray-300 hover:bg-gray-700 focus:bg-gray-700"
                                >
                                    Size {sortBy === 'size' && (sortOrder === 'asc' ? '↑' : '↓')}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator className="bg-gray-600" />
                                <DropdownMenuItem
                                    onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                                    className="text-gray-300 hover:bg-gray-700 focus:bg-gray-700"
                                >
                                    {sortOrder === 'asc' ? <SortDesc className="w-4 h-4 mr-2" /> : <SortAsc className="w-4 h-4 mr-2" />}
                                    {sortOrder === 'asc' ? 'Descending' : 'Ascending'}
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenuPortal>
                    </DropdownMenu>

                    {/* Filter Dropdown */}
                    <DropdownMenu>
                        <DropdownMenuTrigger>
                            <Button variant="outline" className="bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700">
                                <Filter className="w-4 h-4 mr-2" />
                                Filter
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuPortal>
                            <DropdownMenuContent className="bg-gray-800 border-gray-600 z-50">
                                <DropdownMenuLabel className="text-gray-300">Filter by source</DropdownMenuLabel>
                                <DropdownMenuSeparator className="bg-gray-600" />
                                <DropdownMenuItem
                                    onClick={() => setFilterBy('all')}
                                    className={`text-gray-300 hover:bg-gray-700 focus:bg-gray-700 ${filterBy === 'all' ? 'bg-blue-500/20 text-blue-400' : ''}`}
                                >
                                    All Files
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => setFilterBy('ai')}
                                    className={`text-gray-300 hover:bg-gray-700 focus:bg-gray-700 ${filterBy === 'ai' ? 'bg-blue-500/20 text-blue-400' : ''}`}
                                >
                                    Generated by AI
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => setFilterBy('user')}
                                    className={`text-gray-300 hover:bg-gray-700 focus:bg-gray-700 ${filterBy === 'user' ? 'bg-blue-500/20 text-blue-400' : ''}`}
                                >
                                    Uploaded by User
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => setFilterBy('downloaded')}
                                    className={`text-gray-300 hover:bg-gray-700 focus:bg-gray-700 ${filterBy === 'downloaded' ? 'bg-blue-500/20 text-blue-400' : ''}`}
                                >
                                    Downloaded
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenuPortal>
                    </DropdownMenu>
                </div>
            </motion.div>

            {/* Files Grid */}
            {loading ? (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex items-center justify-center py-16"
                >
                    <div className="text-center">
                        <RefreshCw className="w-12 h-12 mx-auto mb-4 text-blue-400 animate-spin" />
                        <p className="text-gray-400">Loading files...</p>
                    </div>
                </motion.div>
            ) : filteredFiles.length > 0 ? (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.2 }}
                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
                >
                    {filteredFiles.map((file, index) => (
                        <motion.div
                            key={file.id}
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.2, delay: index * 0.05 }}
                            className="bg-gray-800 border border-gray-600 rounded-lg p-4 hover:bg-gray-700 transition-all duration-200 group"
                        >
                            {/* File Header */}
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                    {getFileIcon(file.name)}
                                    <div className="flex-1 min-w-0">
                                        <h3 className="text-sm font-medium text-gray-200 truncate" title={file.name}>
                                            {file.name}
                                        </h3>
                                        <p className="text-xs text-gray-500">{file.type}</p>
                                        {file.chat && file.chat !== 'N/A' && (
                                            <p className="text-xs text-gray-400 mt-1 truncate" title={`Chat: ${file.chat}`}>
                                                <span className="font-medium">Chat:</span> {file.chat}
                                            </p>
                                        )}
                                    </div>
                                </div>

                                {/* Action Buttons */}
                                <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 ml-2">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleViewFile(file)}
                                        className="h-6 w-6 p-0 text-gray-400 hover:text-blue-400"
                                        title="Preview file"
                                    >
                                        <Eye className="w-3 h-3" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleDownloadFile(file)}
                                        className="h-6 w-6 p-0 text-gray-400 hover:text-green-400"
                                        title="Download file"
                                    >
                                        <Download className="w-3 h-3" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleDeleteFile(file)}
                                        className="h-6 w-6 p-0 text-gray-400 hover:text-red-400"
                                        title="Delete file"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </Button>
                                </div>
                            </div>

                            {/* File Details */}
                            <div className="space-y-2 text-xs text-gray-500">
                                <div className="flex justify-between">
                                    <span>Size: {file.size}</span>
                                    <span>{file.date}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className={`px-2 py-1 rounded-full text-xs ${file.ioTag === 'generated' ? 'bg-blue-500/20 text-blue-400' :
                                        file.ioTag === 'uploaded' ? 'bg-green-500/20 text-green-400' :
                                            'bg-purple-500/20 text-purple-400'
                                        }`}>
                                        {file.user}
                                    </span>
                                    {file.tags && file.tags.length > 0 && (
                                        <span className="text-xs text-gray-400" title={file.tags.join(', ')}>
                                            🏷️ {file.tags.length}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </motion.div>
            ) : (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.2 }}
                    className="flex items-center justify-center py-16 text-gray-500"
                >
                    <div className="text-center">
                        <categoryInfo.icon className="w-16 h-16 mx-auto mb-4 opacity-50" />
                        <h3 className="text-lg font-medium mb-2">No files found</h3>
                        <p>Try adjusting your search or check back later</p>
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

export default FileView