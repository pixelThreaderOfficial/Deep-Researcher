import React, { useState } from 'react'
import { Bot, Settings, Info, MessageSquare, Clock, Cpu, FileText, Hash, Database, Zap, TrendingUp } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ThisChatSettings from './ThisChatSettings'

const ChatHeader = ({ onOpenSettings, model, chatInfo }) => {
    const [isInfoOpen, setIsInfoOpen] = useState(false)
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
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

    return (
        <div className="w-full px-4 py-3 border-b border-gray-800 bg-gray-900/60">
            {/* Header Content */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-gray-100">
                    <div className="p-2 rounded-lg bg-gray-800 border border-gray-700">
                        <Bot className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                        <div className="font-semibold">Chatting Assistant Area</div>
                        <div className="text-xs text-gray-400 flex items-center gap-2">
                            <span>Always-on, privacy-first</span>
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
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Info Button with Dropdown */}
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

                    {/* Settings Button */}
                    <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 hover:text-gray-100"
                        onClick={() => setIsSettingsModalOpen(true)}
                    >
                        <Settings className="w-5 h-5" />
                    </motion.button>
                </div>
            </div>

            {/* Click outside to close dropdown */}
            {isInfoOpen && (
                <div
                    className="fixed inset-0 z-40"
                    onClick={() => setIsInfoOpen(false)}
                />
            )}

            {/* Chat Settings Modal */}
            <ThisChatSettings
                isOpen={isSettingsModalOpen}
                onOpenChange={setIsSettingsModalOpen}
                currentSettings={chatSettings}
                onSaveSettings={handleSaveChatSettings}
            />
        </div>
    )
}

export default ChatHeader


