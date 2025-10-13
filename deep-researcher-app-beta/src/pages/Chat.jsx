import React, { useMemo, useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import ChatSidebar from '../components/widgets/ChatSidebar'
import ChatHeader from '../components/widgets/ChatHeader'
import ChatArea from '../components/widgets/ChatArea'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'

const Chat = () => {
    const { id } = useParams()
    const location = useLocation()
    const navigate = useNavigate()
    const initialId = id || 'ch_1'
    const [activeChatId, setActiveChatId] = useState(initialId)
    const [isProcessing, setIsProcessing] = useState(false)
    const [messagesByChat, setMessagesByChat] = useState({})
    const [model, setModel] = useState('granite3-moe')
    const [currentTaskId, setCurrentTaskId] = useState(null)
    const [isLoadingChat, setIsLoadingChat] = useState(false)
    const unlistenRefs = useRef({ stream: null, done: null })

    // Load chat and messages from database
    const loadChatFromDatabase = async (chatId) => {
        try {
            setIsLoadingChat(true)
            const [chatData, messagesData] = await Promise.all([
                invoke('cmd_get_chat', { chatId }),
                invoke('cmd_get_messages', { chatId })
            ])

            if (chatData) {
                setModel(chatData.model)
            }

            // Convert database messages to frontend format
            const frontendMessages = messagesData.map(msg => ({
                id: msg.id,
                role: msg.role,
                content: msg.content,
                createdAt: msg.created_at,
                responseTime: msg.response_time,
                files: msg.files ? JSON.parse(msg.files) : undefined
            }))

            setMessagesByChat(prev => ({
                ...prev,
                [chatId]: frontendMessages
            }))

            return frontendMessages
        } catch (error) {
            console.error('Failed to load chat from database:', error)
            return []
        } finally {
            setIsLoadingChat(false)
        }
    }

    const recentChats = useMemo(() => (
        Object.keys(messagesByChat).map((id, idx) => ({
            id,
            title: messagesByChat[id][0]?.content?.slice(0, 24) || `Chat ${idx + 1}`,
            updatedAt: 'just now',
        }))
    ), [messagesByChat])

    const currentMessages = messagesByChat[activeChatId] || []

    function buildOllamaMessagesFrom(list) {
        return (list || []).map(m => ({ role: m.role, content: m.content }))
    }

    // Calculate tokens (rough estimate: 1 token ≈ 4 characters)
    function estimateTokens(text) {
        return Math.ceil(text.length / 4)
    }

    // Calculate chat statistics
    const chatStats = useMemo(() => {
        const messages = currentMessages || []
        let totalTokens = 0
        let totalFiles = 0
        let contextTokens = 0
        let nextPromptFiles = 0

        messages.forEach(message => {
            // Count tokens in message content
            if (message.content) {
                totalTokens += estimateTokens(message.content)
            }

            // Count files in message
            if (message.files && Array.isArray(message.files)) {
                totalFiles += message.files.length
            }
        })

        // Calculate context tokens (last few messages that would be sent)
        const contextMessages = messages.slice(-10) // Last 10 messages for context
        contextMessages.forEach(message => {
            if (message.content) {
                contextTokens += estimateTokens(message.content)
            }
        })

        // Calculate files that would be attached to next prompt (from recent messages)
        const recentMessages = messages.slice(-5) // Last 5 messages
        recentMessages.forEach(message => {
            if (message.files && Array.isArray(message.files)) {
                nextPromptFiles += message.files.length
            }
        })

        // Calculate previous response stats
        let lastResponseStats = null
        const assistantMessages = messages.filter(m => m.role === 'assistant' && !m.streaming)
        if (assistantMessages.length > 0) {
            const lastAssistantMessage = assistantMessages[assistantMessages.length - 1]
            const wordCount = lastAssistantMessage.content ? lastAssistantMessage.content.split(/\s+/).filter(word => word.length > 0).length : 0
            const tokenCount = lastAssistantMessage.content ? estimateTokens(lastAssistantMessage.content) : 0

            // Calculate approximate response time (this would need to be tracked during streaming)
            // For now, we'll use a placeholder or estimate
            const responseTime = lastAssistantMessage.responseTime || null

            // Find the index of this assistant message to calculate context
            const messageIndex = messages.findIndex(m => m.id === lastAssistantMessage.id)
            const contextMessages = messages.slice(0, messageIndex) // All messages before this response

            // Calculate context tokens used
            let contextTokensUsed = 0
            contextMessages.forEach(message => {
                if (message.content) {
                    contextTokensUsed += estimateTokens(message.content)
                }
            })

            // Calculate reference files used (files from all messages before this response)
            let referenceFilesUsed = 0
            contextMessages.forEach(message => {
                if (message.files && Array.isArray(message.files)) {
                    referenceFilesUsed += message.files.length
                }
            })

            lastResponseStats = {
                tokenCount,
                wordCount,
                responseTime,
                timestamp: lastAssistantMessage.createdAt,
                contextTokensUsed,
                referenceFilesUsed
            }
        }

        return {
            totalTokens,
            totalFiles,
            contextTokens,
            nextPromptFiles,
            lastResponseStats
        }
    }, [currentMessages])

    async function startAssistantStream(chatId, historyOverride = null, modelOverride = null) {
        // Stop any previous running stream to avoid mixing outputs
        if (currentTaskId) {
            try { await invoke('cmd_force_stop', { taskId: currentTaskId }) } catch { }
            if (unlistenRefs.current.stream) { unlistenRefs.current.stream(); unlistenRefs.current.stream = null }
            if (unlistenRefs.current.done) { unlistenRefs.current.done(); unlistenRefs.current.done = null }
        }

        const history = historyOverride || buildOllamaMessagesFrom(messagesByChat[chatId])
        const currentModel = modelOverride || model || 'granite3-moe'
        try {
            const taskId = await invoke('cmd_stream_chat_start', {
                model: currentModel,
                messages: history,
            })
            setCurrentTaskId(taskId)
            const replyId = Date.now() + 1
            const streamStartTime = Date.now()
            const assistantMessage = {
                id: replyId,
                role: 'assistant',
                content: '',
                streaming: true,
                createdAt: new Date().toISOString(),
                streamStartTime
            }

            // Save initial assistant message to database
            try {
                await invoke('cmd_add_message', {
                    chatId,
                    role: assistantMessage.role,
                    content: assistantMessage.content,
                    files: null
                })
            } catch (error) {
                console.error('Failed to save assistant message:', error)
            }

            setMessagesByChat(prev => ({
                ...prev,
                [chatId]: [...(prev[chatId] || []), assistantMessage]
            }))

            // Cleanup any previous listeners
            if (unlistenRefs.current.stream) { unlistenRefs.current.stream(); unlistenRefs.current.stream = null }
            if (unlistenRefs.current.done) { unlistenRefs.current.done(); unlistenRefs.current.done = null }

            unlistenRefs.current.stream = await listen('ollama:stream', (event) => {
                const payload = event?.payload || {}
                if (payload.taskId !== taskId) return
                const token = payload.token || ''
                setMessagesByChat(prev => ({
                    ...prev,
                    [chatId]: (prev[chatId] || []).map(m => m.id === replyId ? { ...m, content: (m.content || '') + token } : m)
                }))
            })

            unlistenRefs.current.done = await listen('ollama:stream_done', async (event) => {
                const payload = event?.payload || {}
                if (payload.taskId !== taskId) return
                const streamEndTime = Date.now()
                const responseTime = (streamEndTime - streamStartTime) / 1000 // Convert to seconds

                // Update the message in state first
                const updatedMessage = await new Promise(resolve => {
                    setMessagesByChat(prev => {
                        const updated = (prev[chatId] || []).map(m => m.id === replyId ? {
                            ...m,
                            streaming: false,
                            responseTime: responseTime.toFixed(2)
                        } : m)
                        const finalMessage = updated.find(m => m.id === replyId)
                        resolve(finalMessage)
                        return {
                            ...prev,
                            [chatId]: updated
                        }
                    })
                })

                // Save assistant message to database with statistics
                try {
                    const tokenCount = estimateTokens(updatedMessage.content)
                    await invoke('cmd_update_message_stats', {
                        messageId: replyId,
                        responseTime,
                        tokenCount
                    })
                } catch (error) {
                    console.error('Failed to save message statistics:', error)
                }

                setIsProcessing(false)
                setCurrentTaskId(null)
                if (unlistenRefs.current.stream) { unlistenRefs.current.stream(); unlistenRefs.current.stream = null }
                if (unlistenRefs.current.done) { unlistenRefs.current.done(); unlistenRefs.current.done = null }
            })
        } catch (e) {
            console.error('Failed to start stream:', e)
            setIsProcessing(false)
            setCurrentTaskId(null)
        }
    }

    // Load chat when component mounts or chat ID changes
    useEffect(() => {
        if (id && id !== activeChatId) {
            setActiveChatId(id)
            // Load chat from database
            loadChatFromDatabase(id)
        }
    }, [id])

    useEffect(() => {
        const state = location.state || {}
        const initialMsg = state && state.initialMsg
        const selectedModel = state.selectedModel

        // Set the model if provided in state
        if (selectedModel && selectedModel !== model) {
            setModel(selectedModel)
        }

        if (initialMsg && id) {
            // Prevent duplicate seeding if user reloads or navigates back
            const seededKey = `seeded:${id}`
            if (!sessionStorage.getItem(seededKey)) {
                sessionStorage.setItem(seededKey, '1')

                // First create the chat in database if it doesn't exist
                const createChatIfNeeded = async () => {
                    try {
                        const existingChat = await invoke('cmd_get_chat', { chatId: id })
                        if (!existingChat) {
                            await invoke('cmd_create_chat', {
                                id,
                                title: initialMsg.content.slice(0, 50) + (initialMsg.content.length > 50 ? '...' : ''),
                                model: selectedModel || model
                            })
                        }
                    } catch (error) {
                        console.error('Failed to create chat:', error)
                    }
                }

                createChatIfNeeded().then(() => {
                    setMessagesByChat(prev => {
                        const currentMessages = prev[id] || []
                        const updatedMessages = [...currentMessages, initialMsg]
                        // Start streaming with the updated messages
                        const history = buildOllamaMessagesFrom(updatedMessages)
                        startAssistantStream(id, history, selectedModel)
                        return {
                            ...prev,
                            [id]: updatedMessages
                        }
                    })
                    setIsProcessing(true)
                })
            }
            navigate(location.pathname, { replace: true, state: {} })
        }
    }, [id, model])

    const handleNewChat = async () => {
        const newId = `ch_${Date.now()}`
        try {
            // Create chat in database
            await invoke('cmd_create_chat', {
                id: newId,
                title: 'New Chat',
                model: model
            })

            // Add welcome message to database
            const welcomeMessage = { id: Date.now(), role: 'assistant', content: 'New chat started. What would you like to do?', createdAt: new Date().toISOString() }
            await invoke('cmd_add_message', {
                chatId: newId,
                role: welcomeMessage.role,
                content: welcomeMessage.content,
                files: null
            })

            setMessagesByChat((prev) => ({
                ...prev,
                [newId]: [welcomeMessage],
            }))
            setActiveChatId(newId)
            navigate(`/chat/${newId}`)
        } catch (error) {
            console.error('Failed to create new chat:', error)
            // Fallback to in-memory only
            setMessagesByChat((prev) => ({
                ...prev,
                [newId]: [
                    { id: Date.now(), role: 'assistant', content: 'New chat started. What would you like to do?' },
                ],
            }))
            setActiveChatId(newId)
            navigate(`/chat/${newId}`)
        }
    }

    const handleSelectChat = (id) => {
        setActiveChatId(id)
        navigate(`/chat/${id}`)
    }

    const handleSend = async (text, files) => {
        const userMsg = { id: Date.now(), role: 'user', content: text, files, createdAt: new Date().toISOString() }

        try {
            // Save user message to database
            await invoke('cmd_add_message', {
                chatId: activeChatId,
                role: userMsg.role,
                content: userMsg.content,
                files: files ? JSON.stringify(files) : null
            })
        } catch (error) {
            console.error('Failed to save user message:', error)
        }

        setMessagesByChat((prev) => ({
            ...prev,
            [activeChatId]: [...(prev[activeChatId] || []), userMsg],
        }))
        setIsProcessing(true)
        const history = buildOllamaMessagesFrom([...(messagesByChat[activeChatId] || []), userMsg])
        startAssistantStream(activeChatId, history, model)
    }

    // Cleanup listeners on unmount
    useEffect(() => {
        return () => {
            if (unlistenRefs.current.stream) { unlistenRefs.current.stream(); unlistenRefs.current.stream = null }
            if (unlistenRefs.current.done) { unlistenRefs.current.done(); unlistenRefs.current.done = null }
            if (currentTaskId) {
                invoke('cmd_force_stop', { taskId: currentTaskId }).catch(() => { })
            }
        }
    }, [])

    return (
        <div className="h-screen">
            <div className="flex h-full">
                <ChatSidebar
                    recentChats={recentChats}
                    onNewChat={handleNewChat}
                    onSelectChat={handleSelectChat}
                    activeChatId={activeChatId}
                />

                <main className="flex-1 h-full flex flex-col min-h-0">
                    <ChatHeader
                        onOpenSettings={() => { }}
                        model={model}
                        chatInfo={{
                            messageCount: currentMessages.length,
                            createdAt: currentMessages.length > 0 ? currentMessages[0]?.createdAt : new Date().toISOString(),
                            totalTokens: chatStats.totalTokens,
                            totalFiles: chatStats.totalFiles,
                            contextTokens: chatStats.contextTokens,
                            nextPromptFiles: chatStats.nextPromptFiles,
                            lastResponseStats: chatStats.lastResponseStats
                        }}
                    />
                    <ChatArea
                        messages={currentMessages}
                        onSend={handleSend}
                        isProcessing={isProcessing}
                    />
                </main>
            </div>
        </div>
    )
}

export default Chat


