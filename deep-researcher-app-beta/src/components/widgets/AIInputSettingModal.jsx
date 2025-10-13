import { useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import StyledDropdown from '@/components/ui/styled-dropdown'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Sliders, File, FileText, Image, FileSpreadsheet, Save, Settings, SquareArrowOutUpRight } from 'lucide-react'

const AIInputSettingModal = ({
    selectedModel,
    setSelectedModel,
    selectedAgentType,
    setSelectedAgentType,
    children
}) => {
    const [selectedTone, setSelectedTone] = useState('Professional')
    const [selectedAgent, setSelectedAgent] = useState('WebResearcher')
    const [fileLimit, setFileLimit] = useState('10')
    const [allowedFileTypes, setAllowedFileTypes] = useState(['images', 'documents'])
    const [priorityOrder, setPriorityOrder] = useState(['images', 'documents'])
    const navigate = useNavigate()

    const models = [
        { value: 'gpt-5-preview', name: 'GPT-5 (Preview)', description: 'Early access, subject to change' },
        { value: 'Claude Sonnet 4', name: 'Claude Sonnet 4', description: 'Most advanced model' },
        { value: 'gpt-4', name: 'GPT-4', description: 'OpenAI GPT-4' },
        { value: 'gpt-3.5', name: 'GPT-3.5 Turbo', description: 'Fast and efficient' },
        { value: 'claude-3', name: 'Claude 3', description: 'Anthropic Claude' },
        { value: 'gemini-pro', name: 'Gemini Pro', description: 'Google Gemini' }
    ]

    const tones = [
        { value: 'Professional', name: 'Professional', description: 'Formal and structured' },
        { value: 'Casual', name: 'Casual', description: 'Relaxed and friendly' },
        { value: 'Friendly', name: 'Friendly', description: 'Warm and approachable' }
    ]

    const agents = [
        { value: 'WebResearcher', name: 'WebResearcher', description: 'Web research specialist' },
        { value: 'KnowledgeBase', name: 'KnowledgeBase', description: 'Internal knowledge expert' },
        { value: 'RAG', name: 'RAG', description: 'Retrieval augmented generation' }
    ]

    const fileTypeOptions = [
        {
            id: 'images',
            name: 'Images',
            icon: Image,
            description: 'JPG, PNG, GIF, WebP'
        },
        {
            id: 'documents',
            name: 'Documents',
            icon: FileText,
            description: 'Text, MS Doc, PPT, Xlsx'
        },
        {
            id: 'pdfs',
            name: 'PDFs',
            icon: File,
            description: 'PDF documents'
        }
    ]

    const handleFileTypeChange = (fileType, checked) => {
        if (checked) {
            setAllowedFileTypes(prev => [...prev, fileType])
            if (!priorityOrder.includes(fileType)) {
                setPriorityOrder(prev => [...prev, fileType])
            }
        } else {
            setAllowedFileTypes(prev => prev.filter(type => type !== fileType))
            setPriorityOrder(prev => prev.filter(type => type !== fileType))
        }
    }

    const moveItemUp = (index) => {
        if (index === 0) return
        const items = [...priorityOrder]
        const [item] = items.splice(index, 1)
        items.splice(index - 1, 0, item)
        setPriorityOrder(items)
    }

    const moveItemDown = (index) => {
        if (index === priorityOrder.length - 1) return
        const items = [...priorityOrder]
        const [item] = items.splice(index, 1)
        items.splice(index + 1, 0, item)
        setPriorityOrder(items)
    }

    const PriorityFileType = ({ fileType, index }) => {
        const fileTypeInfo = fileTypeOptions.find(ft => ft.id === fileType)
        const Icon = fileTypeInfo?.icon || File

        return (
            <motion.div
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="flex items-center gap-3 bg-gray-700/50 rounded-lg p-3 transition-all duration-200 hover:bg-gray-600/50"
            >
                <div className="flex flex-col gap-1">
                    <button
                        onClick={() => moveItemUp(index)}
                        disabled={index === 0}
                        className="text-gray-400 hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
                        </svg>
                    </button>
                    <button
                        onClick={() => moveItemDown(index)}
                        disabled={index === priorityOrder.length - 1}
                        className="text-gray-400 hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                    </button>
                </div>
                <Icon className="w-4 h-4 text-orange-400" />
                <span className="text-gray-200 text-sm flex-1">{fileTypeInfo?.name}</span>
                <span className="text-xs text-gray-400 bg-orange-500/20 px-2 py-1 rounded-full">
                    #{index + 1}
                </span>
            </motion.div>
        )
    }

    const handleSave = () => {
        console.log('Settings saved:', {
            selectedModel,
            selectedTone,
            selectedAgent,
            fileLimit,
            allowedFileTypes,
            priorityOrder
        })
    }

    return (
        <Dialog defaultOpen={false}>
            <DialogTrigger asChild>
                {children}
            </DialogTrigger>
            <DialogContent variant="fade" className="max-w-6xl max-h-[85vh] overflow-hidden flex flex-col">
                {/* Static Header */}
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                >
                    <DialogHeader className="pb-4 border-b border-gray-700/50">
                        <DialogTitle className="flex items-center gap-2">
                            <motion.div
                                whileHover={{ rotate: 180 }}
                                transition={{ duration: 0.3 }}
                            >
                                <Sliders className="w-5 h-5" />
                            </motion.div>
                            AI Input Settings
                        </DialogTitle>
                        <DialogDescription>
                            Configure your AI assistant preferences and file handling
                        </DialogDescription>
                    </DialogHeader>
                </motion.div>

                {/* Scrollable Content */}
                <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                    <motion.div
                        className="py-6"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: 0.1 }}
                    >
                        {/* Main Settings Grid */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                            {/* Left Column - AI Settings */}
                            <motion.div
                                className="space-y-6"
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ duration: 0.3, delay: 0.2 }}
                            >
                                {/* Group 1: AI Model + Model Tone */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* AI Model Selection */}
                                    <motion.div className="space-y-3">
                                        <div className="flex items-center justify-between gap-2 w-full">
                                            <div className="flex items-center gap-2">
                                                <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-blue-500 rounded-full" />
                                                <Label className="text-lg font-semibold text-white">AI Model</Label>
                                            </div>
                                            <Button
                                                type="button"
                                                variant="link"
                                                onClick={() => navigate('/settings/models/manage')}
                                                className="h-auto cursor-pointer px-0 text-xs sm:text-sm text-gray-400 hover:text-gray-200 hover:underline underline-offset-4"
                                                aria-label="Manage models"
                                            >
                                                <SquareArrowOutUpRight className="w-4 h-4 mr-1 opacity-70" />
                                                Manage models
                                            </Button>
                                        </div>
                                        <StyledDropdown
                                            value={selectedModel}
                                            onValueChange={setSelectedModel}
                                            options={models}
                                            placeholder="Select AI Model"
                                            width="w-full"
                                        />
                                    </motion.div>

                                    {/* Model Tone */}
                                    <motion.div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-purple-500 rounded-full" />
                                            <Label className="text-lg font-semibold text-white">Model Tone</Label>
                                        </div>
                                        <StyledDropdown
                                            value={selectedTone}
                                            onValueChange={setSelectedTone}
                                            options={tones}
                                            placeholder="Select Tone"
                                            width="w-full"
                                        />
                                    </motion.div>
                                </div>

                                {/* Group 2: Agent Mode + File Limit */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* Agent Mode */}
                                    <motion.div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-green-500 rounded-full" />
                                            <Label className="text-lg font-semibold text-white">Agent Mode</Label>
                                        </div>
                                        <StyledDropdown
                                            value={selectedAgent}
                                            onValueChange={setSelectedAgent}
                                            options={agents}
                                            placeholder="Select Agent"
                                            width="w-full"
                                        />
                                    </motion.div>

                                    {/* File Limit */}
                                    <motion.div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <motion.div whileHover={{ scale: 1.1 }} className="w-2 h-2 bg-yellow-500 rounded-full" />
                                            <Label className="text-lg font-semibold text-white">File Limit</Label>
                                        </div>
                                        <StyledDropdown
                                            value={fileLimit}
                                            onValueChange={setFileLimit}
                                            options={[
                                                { value: '5', name: '5 files', description: 'Small batch processing' },
                                                { value: '10', name: '10 files', description: 'Standard processing' },
                                                { value: '20', name: '20 files', description: 'Large batch processing' },
                                                { value: '50', name: '50 files', description: 'Maximum capacity' }
                                            ]}
                                            placeholder="Select File Limit"
                                            width="w-full"
                                        />
                                    </motion.div>
                                </div>
                            </motion.div>

                            {/* Right Column - File Settings */}
                            <motion.div
                                className="space-y-6"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ duration: 0.3, delay: 0.3 }}
                            >
                                {/* Files Allowed */}
                                <motion.div className="space-y-4">
                                    <div className="flex items-center gap-2">
                                        <motion.div
                                            whileHover={{ scale: 1.1 }}
                                            className="w-2 h-2 bg-red-500 rounded-full"
                                        />
                                        <Label className="text-lg font-semibold text-white">Files Allowed</Label>
                                    </div>
                                    <div className="grid gap-3">
                                        {fileTypeOptions.map((fileType) => {
                                            const Icon = fileType.icon
                                            return (
                                                <motion.div
                                                    key={fileType.id}
                                                    className="flex items-center space-x-3 p-3 rounded-lg bg-gray-700/30 hover:bg-gray-600/40 transition-all duration-200"
                                                    whileHover={{ scale: 1.02 }}
                                                    whileTap={{ scale: 0.98 }}
                                                >
                                                    <Checkbox
                                                        id={fileType.id}
                                                        checked={allowedFileTypes.includes(fileType.id)}
                                                        onCheckedChange={(checked) => handleFileTypeChange(fileType.id, checked)}
                                                        className="data-[state=checked]:bg-orange-500 data-[state=checked]:border-orange-500"
                                                    />
                                                    <Icon className="w-4 h-4 text-orange-400" />
                                                    <div className="flex-1">
                                                        <Label htmlFor={fileType.id} className="text-gray-200 font-medium cursor-pointer">
                                                            {fileType.name}
                                                        </Label>
                                                        <p className="text-xs text-gray-400 mt-1">{fileType.description}</p>
                                                    </div>
                                                </motion.div>
                                            )
                                        })}
                                    </div>
                                </motion.div>
                            </motion.div>
                        </div>

                        {/* Priority File Order Section */}
                        <AnimatePresence>
                            {priorityOrder.length > 0 && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    transition={{ duration: 0.3 }}
                                    className="space-y-4"
                                >
                                    <div className="flex items-center gap-2">
                                        <motion.div
                                            whileHover={{ scale: 1.1 }}
                                            className="w-2 h-2 bg-green-500 rounded-full"
                                        />
                                        <Label className="text-lg font-semibold text-white">Priority File Order</Label>
                                    </div>
                                    <div className="text-sm text-gray-400 mb-4 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                            <path d="M7 3a1 1 0 000 2h6a1 1 0 100-2H7zM4 7a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM2 11a1 1 0 011-1h14a1 1 0 110 2H3a1 1 0 01-1-1z" />
                                        </svg>
                                        Use up/down arrows to reorder file types by processing priority
                                    </div>
                                    <div className="grid gap-3">
                                        <AnimatePresence>
                                            {priorityOrder.map((fileType, index) => (
                                                <PriorityFileType key={fileType} fileType={fileType} index={index} />
                                            ))}
                                        </AnimatePresence>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </motion.div>
                </div>

                {/* Static Footer */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.2 }}
                >
                    <DialogFooter className="pt-4 border-t border-gray-700/50">
                        <motion.div
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                        >
                            <Button
                                onClick={handleSave}
                                className="bg-orange-500 hover:bg-orange-600 text-white shadow-lg hover:shadow-xl transition-all duration-200"
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
                    </DialogFooter>
                </motion.div>
            </DialogContent>
        </Dialog>
    )
}

export default AIInputSettingModal