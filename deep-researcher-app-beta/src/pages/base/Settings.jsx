import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import StyledDropdown from '@/components/ui/styled-dropdown'
import { motion } from 'framer-motion'
import { Settings as sett, Hash, Clock, Bot, MessageSquare, Cpu, Save, Brain, FileText, Database, ChevronUp, ChevronDown, Edit3, Trash2, Check, X } from 'lucide-react'

const SettingsPage = () => {
    const [settings, setSettings] = useState({
        systemPrompt: '',
        promptTemplate: 'default',
        topP: 0.9,
        topK: 50,
        documentAnalysisMode: 'auto',
        thinkingEnabled: true,
        maxChatMemories: 5
    })

    const [editingMemoryId, setEditingMemoryId] = useState(null)
    const [editingContent, setEditingContent] = useState('')
    const [chatMemories, setChatMemories] = useState(
        // Mock memory data - replace with actual vector DB data
        Array.from({ length: 10 }, (_, index) => ({
            id: index + 1,
            timestamp: new Date(Date.now() - index * 24 * 60 * 60 * 1000).toISOString(),
            content: `Memory ${index + 1}: ${index % 2 === 0 ? 'User asked about React hooks implementation' : 'AI explained async/await patterns in JavaScript'}`,
            type: index % 3 === 0 ? 'question' : index % 3 === 1 ? 'answer' : 'summary'
        }))
    )

    const promptTemplates = [
        { value: 'default', name: 'Default', description: 'Standard prompt template' },
        { value: 'creative', name: 'Creative', description: 'Encourages creative responses' },
        { value: 'analytical', name: 'Analytical', description: 'Focuses on logical analysis' },
        { value: 'concise', name: 'Concise', description: 'Provides brief, direct answers' },
        { value: 'educational', name: 'Educational', description: 'Explains concepts thoroughly' }
    ]

    const documentAnalysisModes = [
        { value: 'off', name: 'Off', description: 'Disable document analysis' },
        { value: 'auto', name: 'Auto', description: 'Automatically detect content type' },
        { value: 'text', name: 'Text Only', description: 'Process as plain text' },
        { value: 'structured', name: 'Structured', description: 'Extract structured data' },
        { value: 'visual', name: 'Visual', description: 'Analyze images and diagrams' }
    ]

    const updateSetting = (key, value) => {
        setSettings(prev => ({ ...prev, [key]: value }))
    }

    const handleSave = () => {
        console.log('Settings saved:', settings)
    }

    const handleEditMemory = (memory) => {
        setEditingMemoryId(memory.id)
        setEditingContent(memory.content)
    }

    const handleSaveMemoryEdit = () => {
        setChatMemories(prev => prev.map(memory =>
            memory.id === editingMemoryId
                ? { ...memory, content: editingContent }
                : memory
        ))
        setEditingMemoryId(null)
        setEditingContent('')
    }

    const handleCancelMemoryEdit = () => {
        setEditingMemoryId(null)
        setEditingContent('')
    }

    const handleDeleteMemory = (memoryId) => {
        if (window.confirm('Are you sure you want to delete this memory?')) {
            setChatMemories(prev => prev.filter(memory => memory.id !== memoryId))
        }
    }

    return (
        <motion.div
            className="p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
        >
            <div className="max-w-6xl mx-auto space-y-8">
                {/* Page Header */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="mb-8"
                >
                    <div className="flex items-center gap-3">
                        <motion.div
                            whileHover={{ rotate: 180 }}
                            transition={{ duration: 0.3 }}
                        >
                            <sett className="w-6 h-6 text-blue-400" />
                        </motion.div>
                        <div>
                            <h1 className="text-xl font-semibold text-gray-100">Chat Settings</h1>
                            <p className="text-sm text-gray-400">Customize your chat behavior, prompts, and memory settings</p>
                        </div>
                    </div>
                </motion.div>
                {/* System Prompt Section */}
                <motion.div
                    className="space-y-4"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: 0.2 }}
                >
                    <div className="flex items-center gap-2">
                        <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-blue-500 rounded-full" />
                        <Label className="text-lg font-semibold text-white flex items-center gap-2">
                            <Bot className="w-4 h-4" />
                            System Prompt
                        </Label>
                    </div>
                    <div className="space-y-2">
                        <textarea
                            value={settings.systemPrompt}
                            onChange={(e) => updateSetting('systemPrompt', e.target.value)}
                            placeholder="Enter your system prompt here..."
                            className="w-full min-h-[120px] bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 text-gray-100 placeholder:text-gray-400 resize-y focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-all duration-200"
                            rows={6}
                        />
                        <p className="text-xs text-gray-400">
                            This prompt will guide the AI's behavior throughout the conversation
                        </p>
                    </div>
                </motion.div>

                {/* AI Parameters */}
                <motion.div
                    className="grid grid-cols-1 md:grid-cols-3 gap-6"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.3 }}
                >
                    {/* Prompt Template */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-purple-500 rounded-full" />
                            <Label className="text-base font-semibold text-white flex items-center gap-2">
                                <FileText className="w-4 h-4" />
                                Prompt Template
                            </Label>
                        </div>
                        <StyledDropdown
                            value={settings.promptTemplate}
                            onValueChange={(value) => updateSetting('promptTemplate', value)}
                            options={promptTemplates}
                            placeholder="Select Template"
                            width="w-full"
                        />
                    </div>

                    {/* Top-P */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-green-500 rounded-full" />
                            <Label className="text-base font-semibold text-white flex items-center gap-2">
                                <Cpu className="w-4 h-4" />
                                Top-P
                            </Label>
                        </div>
                        <div className="space-y-2">
                            <Input
                                type="number"
                                min="0"
                                max="1"
                                step="0.1"
                                value={settings.topP}
                                onChange={(e) => updateSetting('topP', parseFloat(e.target.value))}
                                className="bg-gray-800 border-gray-600 text-gray-100 focus:border-blue-500"
                            />
                            <div className="flex justify-between text-xs text-gray-400">
                                <span>0.0 (Deterministic)</span>
                                <span>1.0 (Creative)</span>
                            </div>
                        </div>
                    </div>

                    {/* Top-K */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-blue-500 rounded-full" />
                            <Label className="text-base font-semibold text-white flex items-center gap-2">
                                <Hash className="w-4 h-4" />
                                Top-K
                            </Label>
                        </div>
                        <div className="space-y-2">
                            <Input
                                type="number"
                                min="1"
                                max="100"
                                step="1"
                                value={settings.topK}
                                onChange={(e) => updateSetting('topK', parseInt(e.target.value))}
                                className="bg-gray-800 border-gray-600 text-gray-100 focus:border-blue-500"
                            />
                            <div className="flex justify-between text-xs text-gray-400">
                                <span>1 (Focused)</span>
                                <span>100 (Diverse)</span>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Document Analysis & Thinking Toggle */}
                <motion.div
                    className="grid grid-cols-1 md:grid-cols-2 gap-6"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.4 }}
                >
                    {/* Document Analysis Mode */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-orange-500 rounded-full" />
                            <Label className="text-base font-semibold text-white flex items-center gap-2">
                                <Database className="w-4 h-4" />
                                Document Analysis Mode
                            </Label>
                        </div>
                        <StyledDropdown
                            value={settings.documentAnalysisMode}
                            onValueChange={(value) => updateSetting('documentAnalysisMode', value)}
                            options={documentAnalysisModes}
                            placeholder="Select Mode"
                            width="w-full"
                        />
                    </div>

                    {/* Thinking Toggle */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-indigo-500 rounded-full" />
                            <Label className="text-base font-semibold text-white flex items-center gap-2">
                                <Brain className="w-4 h-4" />
                                Thinking Mode
                            </Label>
                        </div>
                        <div className="flex items-center justify-between p-4 bg-gray-800/30 rounded-lg border border-gray-600/50">
                            <div className="flex-1">
                                <div className="text-gray-200 font-medium">Enable Thinking</div>
                                <div className="text-xs text-gray-400 mt-1">
                                    Show AI reasoning process before responses
                                </div>
                            </div>
                            <Switch
                                checked={settings.thinkingEnabled}
                                onCheckedChange={(checked) => updateSetting('thinkingEnabled', checked)}
                            />
                        </div>
                    </div>
                </motion.div>

                {/* Chat Memories */}
                <motion.div
                    className="space-y-4"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: 0.5 }}
                >
                    <div className="flex items-center gap-2">
                        <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-pink-500 rounded-full" />
                        <Label className="text-lg font-semibold text-white flex items-center gap-2">
                            <MessageSquare className="w-4 h-4" />
                            Chat Memories
                        </Label>
                    </div>

                    {/* Memory Cards Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {chatMemories.map((memory) => (
                            <motion.div
                                key={memory.id}
                                className="bg-gray-800 border border-gray-600 rounded-lg p-4 hover:bg-gray-700 transition-all duration-200"
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.2, delay: memory.id * 0.05 }}
                                whileHover={{ scale: 1.02 }}
                            >
                                <div className="flex items-start justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                        <div className={`w-2 h-2 rounded-full ${memory.type === 'question' ? 'bg-blue-500' :
                                            memory.type === 'answer' ? 'bg-green-500' : 'bg-purple-500'
                                            }`} />
                                        <span className="text-xs text-gray-400 capitalize">
                                            {memory.type}
                                        </span>
                                    </div>
                                    <span className="text-xs text-gray-500">
                                        #{memory.id}
                                    </span>
                                </div>

                                {/* Content or Edit Input */}
                                {editingMemoryId === memory.id ? (
                                    <textarea
                                        value={editingContent}
                                        onChange={(e) => setEditingContent(e.target.value)}
                                        className="w-full min-h-[60px] bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 resize-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none mb-3"
                                        placeholder="Edit memory content..."
                                    />
                                ) : (
                                    <p className="text-sm text-gray-200 mb-3 line-clamp-2">
                                        {memory.content}
                                    </p>
                                )}

                                {/* Timestamp and Actions */}
                                <div className="flex items-center justify-between text-xs text-gray-500">
                                    <div className="flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        <span>
                                            {new Date(memory.timestamp).toLocaleDateString()} {new Date(memory.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </span>
                                    </div>

                                    {/* Action Buttons */}
                                    <div className="flex items-center gap-1">
                                        {editingMemoryId === memory.id ? (
                                            <>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={handleSaveMemoryEdit}
                                                    className="h-6 px-2 text-xs text-green-500 hover:text-green-400 dark:text-green-400 dark:hover:text-green-300"
                                                >
                                                    <Check className="w-3 h-3" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={handleCancelMemoryEdit}
                                                    className="h-6 px-2 text-xs text-gray-400 hover:text-gray-300 dark:text-gray-500 dark:hover:text-gray-400"
                                                >
                                                    <X className="w-3 h-3" />
                                                </Button>
                                            </>
                                        ) : (
                                            <>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => handleEditMemory(memory)}
                                                    className="h-6 px-2 text-xs text-blue-500 hover:text-blue-400 dark:text-blue-400 dark:hover:text-blue-300"
                                                >
                                                    <Edit3 className="w-3 h-3" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => handleDeleteMemory(memory.id)}
                                                    className="h-6 px-2 text-xs text-red-500 hover:text-red-400 dark:text-red-400 dark:hover:text-red-300"
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                </Button>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>

                    {/* Memory Settings */}
                    <div className="border-t border-gray-600/50 pt-4">
                        <div className="flex items-center justify-between">
                            <div className="space-y-1">
                                <Label className="text-sm font-medium text-gray-300">Memory Retention</Label>
                                <p className="text-xs text-gray-400">
                                    Maximum memories stored per chat session
                                </p>
                            </div>
                            <div className="flex items-center gap-4">
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => updateSetting('maxChatMemories', Math.max(1, settings.maxChatMemories - 1))}
                                    disabled={settings.maxChatMemories <= 1}
                                    className="h-8 w-8 p-0"
                                >
                                    <ChevronDown className="w-4 h-4" />
                                </Button>
                                <span className="text-lg font-semibold text-gray-100 min-w-[2rem] text-center">
                                    {settings.maxChatMemories}
                                </span>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => updateSetting('maxChatMemories', Math.min(10, settings.maxChatMemories + 1))}
                                    disabled={settings.maxChatMemories >= 10}
                                    className="h-8 w-8 p-0"
                                >
                                    <ChevronUp className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Save Button */}
                <div className="flex justify-end pt-6">
                    <motion.div
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                    >
                        <Button
                            onClick={handleSave}
                            className="bg-blue-500 hover:bg-blue-600 text-white shadow-lg hover:shadow-xl transition-all duration-200 px-6 py-2"
                        >
                            <motion.div
                                whileHover={{ rotate: 360 }}
                                transition={{ duration: 0.3 }}
                                className="mr-2"
                            >
                                <Save className="w-4 h-4" />
                            </motion.div>
                            Save Settings
                        </Button>
                    </motion.div>
                </div>
            </div>
        </motion.div>
    )
}

export default SettingsPage