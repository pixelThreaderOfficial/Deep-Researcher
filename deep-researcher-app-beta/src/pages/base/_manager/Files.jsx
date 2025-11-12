import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
    FileText,
    FileSpreadsheet,
    Presentation,
    File,
    Music,
    Image,
    Folder,
    Search,
    Download,
    Eye,
    Trash2,
    ArrowRight,
    RefreshCw,
    AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { fetchFiles, getFileStats, deleteFile, getDownloadUrl } from '@/lib/filesApi'
import { toast } from 'sonner'

const Files = () => {
    const [searchQuery, setSearchQuery] = useState('')
    const [allFiles, setAllFiles] = useState([])
    const [stats, setStats] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const navigate = useNavigate()

    // Load files and stats on mount
    useEffect(() => {
        loadData()
    }, [])

    const loadData = async () => {
        try {
            setLoading(true)
            setError(null)

            // Fetch all files and stats in parallel
            const [filesResult, statsResult] = await Promise.all([
                fetchFiles({ limit: 1000 }),
                getFileStats().catch(() => null) // Don't fail if stats aren't available
            ])

            setAllFiles(filesResult.files)
            setStats(statsResult)
        } catch (err) {
            console.error('Failed to load data:', err)
            setError(err.message)
            toast.error('Failed to load files: ' + err.message)
        } finally {
            setLoading(false)
        }
    }

    // Group files by category
    const fileSections = [
        {
            title: 'Documents',
            icon: FileText,
            description: 'Documents uploaded or generated in conversations',
            category: 'documents',
            files: allFiles.filter(f => f.category === 'documents' || f.category === 'docs')
        },
        {
            title: 'Audio Files',
            icon: Music,
            description: 'Audio recordings from chat sessions',
            category: 'audios',
            files: allFiles.filter(f => f.category === 'audios' || f.category === 'audio')
        },
        {
            title: 'Images',
            icon: Image,
            description: 'Images shared or generated in conversations',
            category: 'images',
            files: allFiles.filter(f => f.category === 'images')
        }
    ]

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
                loadData() // Reload data
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

    const filteredSections = fileSections.map(section => ({
        ...section,
        files: section.files.filter(file =>
            file.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            file.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (file.chat && file.chat.toLowerCase().includes(searchQuery.toLowerCase())) ||
            file.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (file.tags && file.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase())))
        )
    }))

    const viewAllFiles = (category) => {
        const categoryMap = {
            'Documents': 'docs',
            'Audio Files': 'audio',
            'Images': 'images'
        }
        navigate(`/app/files/${categoryMap[category]}`)
    }

    // Calculate totals
    const totalFiles = allFiles.length
    const aiFiles = allFiles.filter(f => f.ioTag === 'generated').length
    const userFiles = allFiles.filter(f => f.ioTag === 'uploaded').length

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
                        <Folder className="w-6 h-6 text-blue-400" />
                    </motion.div>
                    <div>
                        <h1 className="text-xl font-semibold text-gray-100">Chat Files</h1>
                        <p className="text-sm text-gray-400">Track files uploaded or generated in your conversations</p>
                    </div>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={loadData}
                    disabled={loading}
                    className="text-gray-400 hover:text-gray-200"
                >
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
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
                        onClick={loadData}
                        className="ml-auto text-red-400 hover:text-red-300"
                    >
                        Retry
                    </Button>
                </motion.div>
            )}

            {/* File Sections */}
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
            ) : (
                <div className="space-y-8">
                    {filteredSections.map((section, sectionIndex) => {
                        const SectionIcon = section.icon
                        return (
                            <motion.div
                                key={section.title}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.3, delay: 0.2 + sectionIndex * 0.1 }}
                                className="space-y-4"
                            >
                                {/* Section Header */}
                                <div className="flex items-center gap-3">
                                    <div className="flex items-center gap-2">
                                        <motion.div
                                            whileHover={{ scale: 1.1 }}
                                            className="w-2 h-2 bg-blue-500 rounded-full"
                                        />
                                        <SectionIcon className="w-5 h-5 text-blue-400" />
                                        <h2 className="text-lg font-semibold text-gray-100">{section.title}</h2>
                                    </div>
                                    <div className="flex-1 h-px bg-gray-700"></div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded-full">
                                            {section.files.length} files
                                        </span>
                                        {/* <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => viewAllFiles(section.title)}
                                            className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 text-xs px-3 py-1 h-auto"
                                        >
                                            View All
                                            <ArrowRight className="w-3 h-3 ml-1" />
                                        </Button> */}
                                    </div>
                                </div>

                                <p className="text-sm text-gray-400 ml-7">{section.description}</p>

                                {/* Files Grid */}
                                {section.files.length > 0 ? (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ml-7">
                                        {section.files.map((file, fileIndex) => (
                                            <Tooltip key={file.id || file.name}>
                                                <TooltipTrigger asChild>
                                                    <motion.div
                                                        initial={{ opacity: 0, scale: 0.95 }}
                                                        animate={{ opacity: 1, scale: 1 }}
                                                        transition={{ duration: 0.2, delay: fileIndex * 0.05 }}
                                                        className="bg-gray-800 border border-gray-600 rounded-lg p-4 hover:bg-gray-700 transition-all duration-200 group overflow-hidden"
                                                    >
                                                        {/* File Header */}
                                                        <div className="flex items-start justify-between mb-3">
                                                            <div className="flex items-center gap-3">
                                                                {getFileIcon(file.name)}
                                                                <div className="flex-1 min-w-0 overflow-hidden">
                                                                    <h3 className="text-sm font-medium text-gray-200 truncate" title={file.name}>
                                                                        {file.name.length > 40 ? file.name.substring(0, 40) + '...' : file.name}
                                                                    </h3>
                                                                    <p className="text-xs text-gray-500">{file.type}</p>
                                                                    <p className="text-xs text-gray-400 mt-1">
                                                                        <span className="font-medium">ID:</span> {file.id}
                                                                    </p>
                                                                </div>
                                                            </div>

                                                            {/* Action Buttons */}
                                                            <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                                                                {/* <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    onClick={() => handleViewFile(file)}
                                                                    className="h-6 w-6 p-0 text-gray-400 hover:text-blue-400"
                                                                    title="Preview file"
                                                                >
                                                                    <Eye className="w-3 h-3" />
                                                                </Button> */}
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
                                                </TooltipTrigger>
                                                <TooltipContent sideOffset={8}>
                                                    {file.name}
                                                </TooltipContent>
                                            </Tooltip>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="ml-7 flex items-center justify-center py-8 text-gray-500">
                                        <div className="text-center">
                                            <SectionIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                            <p>No files found</p>
                                            {searchQuery && <p className="text-xs">Try adjusting your search</p>}
                                        </div>
                                    </div>
                                )}
                            </motion.div>
                        )
                    })}
                </div>
            )}

            {/* Summary Section */}
            {!loading && (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.6 }}
                    className="bg-gray-800/50 border border-gray-600 rounded-lg p-6"
                >
                    <div className="flex items-center gap-3 mb-4">
                        <motion.div
                            whileHover={{ scale: 1.1 }}
                            className="w-2 h-2 bg-blue-500 rounded-full"
                        />
                        <h3 className="text-lg font-medium text-gray-200">File Summary</h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {fileSections.map((section, index) => (
                            <div key={section.title} className="bg-gray-700/50 rounded-lg p-4">
                                <div className="flex items-center gap-2 mb-2">
                                    <section.icon className="w-4 h-4 text-blue-400" />
                                    <span className="text-sm font-medium text-gray-200">{section.title}</span>
                                </div>
                                <div className="text-2xl font-bold text-blue-400 mb-1">
                                    {section.files.length}
                                </div>
                                <div className="text-xs text-gray-400">files tracked</div>
                            </div>
                        ))}
                    </div>

                    <div className="mt-4 pt-4 border-t border-gray-600">
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-400">Total files tracked:</span>
                            <span className="font-semibold text-gray-200">
                                {totalFiles} files
                            </span>
                        </div>
                        <div className="flex items-center justify-between text-sm mt-1">
                            <span className="text-gray-400">Files from AI:</span>
                            <span className="font-semibold text-blue-400">
                                {aiFiles} files
                            </span>
                        </div>
                        <div className="flex items-center justify-between text-sm mt-1">
                            <span className="text-gray-400">Files from users:</span>
                            <span className="font-semibold text-green-400">
                                {userFiles} files
                            </span>
                        </div>
                    </div>
                </motion.div>
            )}
        </div>
    )
}

export default Files