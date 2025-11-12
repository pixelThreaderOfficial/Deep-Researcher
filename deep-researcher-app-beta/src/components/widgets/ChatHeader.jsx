import React, { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Bot, Settings, Info, MessageSquare, Clock, Cpu, FileText, Hash, Database, Zap, TrendingUp, Edit3, Check, X, Search } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ThisChatSettings from './ThisChatSettings'

const ChatHeader = ({ onOpenSettings, model, chatInfo, chatTitle, onUpdateTitle, sessionId, isResearchMode = false, pageTitle }) => {
    const location = useLocation()
    const isChatPage = location.pathname.startsWith('/chat')
    const isFilesPage = location.pathname.includes('/files') || pageTitle?.toLowerCase().includes('file')
    const derivedTitle = pageTitle || (isResearchMode ? 'Research' : (isChatPage ? (chatTitle || 'New Chat') : ''))
    const [isInfoOpen, setIsInfoOpen] = useState(false)
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
    const [isEditingTitle, setIsEditingTitle] = useState(false)
    const [editingTitle, setEditingTitle] = useState('')
    const [chatSettings, setChatSettings] = useState({
        systemPrompt: '',
        promptTemplate: 'default',
        topP: 0.9,
        topK: 50,
        documentAnalysisMode: 'auto',
        thinkingEnabled: true,
        maxChatMemories: 5
    })

    const messageCount = chatInfo?.messageCount || 0
    const createdAt = chatInfo?.createdAt ? new Date(chatInfo.createdAt).toLocaleDateString() : 'Just now'
    const totalTokens = chatInfo?.totalTokens || 0
    const totalFiles = chatInfo?.totalFiles || 0
    const contextTokens = chatInfo?.contextTokens || 0
    const nextPromptFiles = chatInfo?.nextPromptFiles || 0
    const lastResponseStats = chatInfo?.lastResponseStats || null

    const handleSaveChatSettings = (newSettings) => {
        setChatSettings(newSettings)
        // Here you could also save to localStorage or send to a backend
        console.log('Chat settings saved:', newSettings)
    }

    const handleStartEditingTitle = () => {
        if (!isChatPage) return
        setEditingTitle(chatTitle || 'New Chat')
        setIsEditingTitle(true)
    }

    const handleSaveTitle = async () => {
        const newTitle = editingTitle.trim()
        if (newTitle && newTitle !== chatTitle && sessionId) {
            try {
                const response = await fetch(`http://localhost:8000/api/sessions/${sessionId}/title`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ title: newTitle }),
                })
                const data = await response.json()

                if (data.success) {
                    onUpdateTitle?.(newTitle)
                } else {
                    console.error('Failed to update title:', data.error)
                }
            } catch (error) {
                console.error('Error updating title:', error)
            }
        }
        setIsEditingTitle(false)
    }

    const handleCancelTitleEdit = () => {
        setEditingTitle('')
        setIsEditingTitle(false)
    }

    return (
        <div className="w-full px-4 py-3 border-b border-gray-800 bg-gray-900/60">
            {/* Header Content */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-gray-100">
                    <div className="p-2 rounded-lg bg-gray-800 border border-gray-700 relative" title={isFilesPage ? 'Files' : undefined}>
                        {isFilesPage ? (
                            <FileText className="w-5 h-5 text-cyan-400" />
                        ) : (!isChatPage && (pageTitle?.toLowerCase().includes('research'))) || isResearchMode ? (
                            <Search className="w-5 h-5 text-purple-400" />
                        ) : (
                            <Bot className="w-5 h-5 text-blue-400" />
                        )}
                        {isChatPage && (chatInfo?.totalFiles || 0) > 0 && (
                            <div className="absolute -top-1 -right-1 bg-cyan-600 text-[10px] leading-none px-1 py-0.5 rounded shadow-sm" title={`${chatInfo.totalFiles} file${chatInfo.totalFiles === 1 ? '' : 's'}`}>
                                {chatInfo.totalFiles}
                            </div>
                        )}
                    </div>
                    <div className="flex-1 min-w-0">
                        {isChatPage && isEditingTitle ? (
                            <div className="flex items-center gap-2">
                                <input
                                    type="text"
                                    value={editingTitle}
                                    onChange={(e) => setEditingTitle(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') handleSaveTitle()
                                        if (e.key === 'Escape') handleCancelTitleEdit()
                                    }}
                                    className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
                                    autoFocus
                                    onBlur={handleCancelTitleEdit}
                                />
                                <button
                                    onClick={handleSaveTitle}
                                    className="p-1 text-green-400 hover:text-green-300"
                                >
                                    <Check className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={handleCancelTitleEdit}
                                    className="p-1 text-red-400 hover:text-red-300"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            </div>
                        ) : (
                            <div className={`flex items-center gap-2 ${isChatPage ? 'cursor-pointer group' : ''}`} onClick={handleStartEditingTitle}>
                                <div className="font-semibold truncate">{isChatPage ? (chatTitle || 'New Chat') : (derivedTitle || 'Dashboard')}</div>
                                {isChatPage && <Edit3 className="w-4 h-4 text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity" />}
                            </div>
                        )}
                        {isChatPage && (
                            <div className="text-xs text-gray-400 flex items-center gap-2">
                                <span>Session: {sessionId || 'New'}</span>
                                {model && (
                                    <>
                                        <span>•</span>
                                        <span className="flex items-center gap-1">
                                            <Cpu className="w-3 h-3" />
                                            {model}
                                        </span>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Info Button with Dropdown */}
                    {isChatPage && (
                        <div className="relative">
                            <motion.button
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                                className="p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 hover:text-gray-100"
                                onClick={() => setIsInfoOpen(!isInfoOpen)}
                            >
                                <Info className="w-5 h-5" />
                            </motion.button>

                            {/* Info Dropdown */}
                            <AnimatePresence>
                                {isInfoOpen && (
                                    <motion.div
                                        initial={{ opacity: 0, y: -10, scale: 0.95 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        exit={{ opacity: 0, y: -10, scale: 0.95 }}
                                        transition={{ duration: 0.15 }}
                                        className="absolute right-0 top-full mt-2 w-64 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-50"
                                    >
                                        <div className="p-4">
                                            <h3 className="font-semibold text-gray-100 mb-3 flex items-center gap-2">
                                                <Info className="w-4 h-4" />
                                                Chat Information
                                            </h3>
                                            <div className="space-y-3 text-sm">
                                                {/* Basic Info */}
                                                <div className="space-y-2">
                                                    <div className="flex items-center gap-2 text-gray-300">
                                                        <MessageSquare className="w-4 h-4 text-blue-400" />
                                                        <span>{messageCount} messages</span>
                                                    </div>
                                                    <div className="flex items-center gap-2 text-gray-300">
                                                        <Clock className="w-4 h-4 text-green-400" />
                                                        <span>Created {createdAt}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2 text-gray-300">
                                                        <Cpu className="w-4 h-4 text-purple-400" />
                                                        <span>Model: {model || 'Unknown'}</span>
                                                    </div>
                                                </div>

                                                {/* Token & File Stats */}
                                                <div className="border-t border-gray-700 pt-3">
                                                    <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Chat Statistics</h4>
                                                    <div className="space-y-2">
                                                        <div className="flex items-center gap-2 text-gray-300">
                                                            <Hash className="w-4 h-4 text-orange-400" />
                                                            <span>{totalTokens.toLocaleString()} total tokens</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 text-gray-300">
                                                            <FileText className="w-4 h-4 text-cyan-400" />
                                                            <span>{totalFiles} total files</span>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Context Info */}
                                                <div className="border-t border-gray-700 pt-3">
                                                    <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Next Prompt Context</h4>
                                                    <div className="space-y-2">
                                                        <div className="flex items-center gap-2 text-gray-300">
                                                            <Database className="w-4 h-4 text-yellow-400" />
                                                            <span>{contextTokens.toLocaleString()} context tokens</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 text-gray-300">
                                                            <FileText className="w-4 h-4 text-pink-400" />
                                                            <span>{nextPromptFiles} attached files</span>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Previous Response Stats */}
                                                {lastResponseStats && (
                                                    <div className="border-t border-gray-700 pt-3">
                                                        <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Previous Response Stats</h4>
                                                        <div className="space-y-2">
                                                            <div className="flex items-center gap-2 text-gray-300">
                                                                <Hash className="w-4 h-4 text-emerald-400" />
                                                                <span>{lastResponseStats.tokenCount?.toLocaleString() || 0} response tokens</span>
                                                            </div>
                                                            <div className="flex items-center gap-2 text-gray-300">
                                                                <Zap className="w-4 h-4 text-blue-400" />
                                                                <span>{lastResponseStats.responseTime ? `${lastResponseStats.responseTime}s` : 'N/A'} response time</span>
                                                            </div>
                                                            <div className="flex items-center gap-2 text-gray-300">
                                                                <TrendingUp className="w-4 h-4 text-purple-400" />
                                                                <span>{lastResponseStats.wordCount || 0} words</span>
                                                            </div>
                                                            <div className="flex items-center gap-2 text-gray-300">
                                                                <Clock className="w-4 h-4 text-orange-400" />
                                                                <span>{lastResponseStats.timestamp ? new Date(lastResponseStats.timestamp).toLocaleTimeString() : 'N/A'}</span>
                                                            </div>
                                                            <div className="flex items-center gap-2 text-gray-300">
                                                                <Database className="w-4 h-4 text-indigo-400" />
                                                                <span>{lastResponseStats.contextTokensUsed?.toLocaleString() || 0} context tokens used</span>
                                                            </div>
                                                            <div className="flex items-center gap-2 text-gray-300">
                                                                <FileText className="w-4 h-4 text-teal-400" />
                                                                <span>{lastResponseStats.referenceFilesUsed || 0} reference files used</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        <div className="absolute -top-2 right-3 w-4 h-4 bg-gray-800 border-l border-t border-gray-700 transform rotate-45"></div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    )}

                    {/* Settings Button */}
                    {/* Settings button hidden until implemented */}
                    {/* {isChatPage && (
                        <motion.button
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            className="p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 hover:text-gray-100"
                            onClick={() => setIsSettingsModalOpen(true)}
                        >
                            <Settings className="w-5 h-5" />
                        </motion.button>
                    )} */}
                </div>
            </div>

            {/* Click outside to close dropdown */}
            {isChatPage && isInfoOpen && (
                <div
                    className="fixed inset-0 z-40"
                    onClick={() => setIsInfoOpen(false)}
                />
            )}

            {/* Chat Settings Modal */}
            {/* Settings modal hidden until implemented */}
            {/* {isChatPage && (
                <ThisChatSettings
                    isOpen={isSettingsModalOpen}
                    onOpenChange={setIsSettingsModalOpen}
                    currentSettings={chatSettings}
                    onSaveSettings={handleSaveChatSettings}
                />
            )} */}
        </div>
    )
}

export default ChatHeader


