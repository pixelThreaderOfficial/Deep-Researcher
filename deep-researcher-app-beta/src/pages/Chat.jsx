import React, { useMemo, useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import ChatSidebar from '../components/widgets/ChatSidebar'
import ChatHeader from '../components/widgets/ChatHeader'
import ChatArea from '../components/widgets/ChatArea'
import ResearchArea from '../components/widgets/ResearchArea'

const Chat = () => {
    const { id } = useParams()
    const location = useLocation()
    const navigate = useNavigate()
    const initialId = id || 'ch_1'
    const [activeChatId, setActiveChatId] = useState(initialId)
    const [isProcessing, setIsProcessing] = useState(false)
    const [messagesByChat, setMessagesByChat] = useState({})
    const [model, setModel] = useState('gemini-2.5-flash')
    const [currentTaskId, setCurrentTaskId] = useState(null)
    const [currentSession, setCurrentSession] = useState(null)
    const [isLoadingChat, setIsLoadingChat] = useState(false)
    const [isResearchMode, setIsResearchMode] = useState(false)
    const [researchProgress, setResearchProgress] = useState('')
    const [researchSources, setResearchSources] = useState([])
    const [researchImages, setResearchImages] = useState([])
    const [researchNews, setResearchNews] = useState(null)
    const [researchMetadata, setResearchMetadata] = useState(null)
    const [initialResearchInput, setInitialResearchInput] = useState('')
    const unlistenRefs = useRef({ stream: null, done: null })
    const wsRef = useRef(null)
    const currentStreamingMessageIdRef = useRef(null)

    // Load session and messages from API
    const loadChatFromDatabase = async (sessionId) => {
        try {
            setIsLoadingChat(true)

            // Load session details and messages in parallel
            const [sessionResponse, messagesResponse] = await Promise.all([
                fetch(`http://localhost:8000/api/sessions/${sessionId}`).catch(err => {
                    console.warn('Session fetch failed:', err)
                    return { ok: false, status: 404 }
                }),
                fetch(`http://localhost:8000/api/sessions/${sessionId}/messages?limit=100`).catch(err => {
                    console.warn('Messages fetch failed:', err)
                    return { ok: false, status: 404 }
                })
            ])

            const sessionData = sessionResponse.ok ? await sessionResponse.json() : { success: false, error: 'Session not found' }
            const messagesData = messagesResponse.ok ? await messagesResponse.json() : { success: false, error: 'Messages not found' }

            if (sessionData.success && sessionData.session) {
                // Set the model from session data
                setModel(sessionData.session.stats?.unique_models === 1 ? 'gemini-2.0-flash' : 'gemini-2.5-flash')
                // Store the current session data including title
                setCurrentSession(sessionData.session)
            }

            if (messagesData.success && messagesData.messages && messagesData.messages.length > 0) {
                console.log('Loading messages for session:', sessionId, messagesData.messages)

                // Convert API messages to frontend format
                // Each API message contains both prompt and response, so create two frontend messages
                const frontendMessages = []

                messagesData.messages.forEach(msg => {
                    // Add user message
                    if (msg.prompt && msg.prompt.trim()) {
                        frontendMessages.push({
                            id: `${msg.chatid || msg.sno}_user`,
                            role: 'user',
                            content: msg.prompt.trim(),
                            createdAt: new Date(msg.created_at * 1000).toISOString(),
                            responseTime: msg.generation_time,
                            files: msg.files ? JSON.parse(msg.files) : undefined
                        })
                    }

                    // Add assistant message
                    if (msg.response && msg.response.trim()) {
                        frontendMessages.push({
                            id: `${msg.chatid || msg.sno}_assistant`,
                            role: 'assistant',
                            content: msg.response.trim(),
                            createdAt: new Date(msg.created_at * 1000).toISOString(),
                            responseTime: msg.generation_time,
                            files: undefined
                        })
                    }
                })

                // Sort by creation time
                frontendMessages.sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt))

                console.log('Converted messages:', frontendMessages)

                setMessagesByChat(prev => ({
                    ...prev,
                    [sessionId]: frontendMessages
                }))

                return frontendMessages
            } else {
                console.log('No messages found for session:', sessionId)
                // Empty session
                setMessagesByChat(prev => ({
                    ...prev,
                    [sessionId]: []
                }))
                return []
            }
        } catch (error) {
            console.error('Failed to load chat:', error, 'Session ID:', sessionId)

            // Check if it's a 404 (session doesn't exist yet)
            if (error.message && error.message.includes('404')) {
                console.log('Session does not exist yet, creating empty session')
                setMessagesByChat(prev => ({
                    ...prev,
                    [sessionId]: []
                }))
                return []
            }

            // For other errors, still create empty session
            setMessagesByChat(prev => ({
                ...prev,
                [sessionId]: []
            }))
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

    // Load chat statistics from API
    const chatStats = useMemo(() => {
        const messages = currentMessages || []

        // If we have messages loaded, use local calculations
        // Otherwise, stats will be loaded from API when available
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

            // Use response time from message if available
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

    // Research WebSocket connection
    const connectResearchWebSocket = (sessionId, query, model = 'gemini-2.0-flash') => {
        if (wsRef.current) {
            wsRef.current.close()
        }

        // Reset research state
        setResearchProgress('')
        setResearchSources([])
        setResearchImages([])
        setResearchNews(null)
        setResearchMetadata(null)

        const ws = new WebSocket('ws://localhost:8000/ws/research')
        wsRef.current = ws

        ws.onopen = () => {
            console.log('Research WebSocket connected')
            ws.send(JSON.stringify({
                query: query,
                model: model,
                session_id: sessionId,
            }))
        }

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)

            switch (data.type) {
                case 'progress':
                    console.log(`[${data.stage}] ${data.message}`)
                    setResearchProgress(`${data.stage}: ${data.message}`)
                    break

                case 'answer_chunk':
                    // Append streaming text
                    setMessagesByChat(prev => {
                        const newMessages = [...(prev[sessionId] || [])]
                        const lastMessage = newMessages[newMessages.length - 1]

                        if (lastMessage && lastMessage.role === 'assistant' && lastMessage.streaming) {
                            // Update existing streaming message
                            lastMessage.content += data.chunk
                        } else {
                            // Create new streaming message
                            const streamingMessage = {
                                id: Date.now(),
                                role: 'assistant',
                                content: data.chunk,
                                streaming: true,
                                createdAt: new Date().toISOString()
                            }
                            newMessages.push(streamingMessage)
                            currentStreamingMessageIdRef.current = streamingMessage.id
                        }

                        return {
                            ...prev,
                            [sessionId]: newMessages
                        }
                    })
                    break

                case 'result':
                    // Final result received
                    console.log('Research complete!', data.data)

                    // Mark streaming as completed
                    setMessagesByChat(prev => {
                        const newMessages = [...(prev[sessionId] || [])]
                        const lastMessage = newMessages[newMessages.length - 1]

                        if (lastMessage && lastMessage.role === 'assistant' && lastMessage.streaming) {
                            lastMessage.streaming = false
                        }

                        return {
                            ...prev,
                            [sessionId]: [...newMessages]
                        }
                    })

                    // Store research data
                    setResearchSources(data.data.sources || [])
                    setResearchImages(data.data.images || [])
                    setResearchNews(data.data.news || null)
                    setResearchMetadata(data.data.metadata || null)

                    setIsProcessing(false)
                    setResearchProgress('Research completed!')
                    ws.close()
                    wsRef.current = null
                    break

                case 'error':
                    console.error('Research error:', data.message)
                    setMessagesByChat(prev => ({
                        ...prev,
                        [sessionId]: [...(prev[sessionId] || []), {
                            id: Date.now(),
                            role: 'assistant',
                            content: `Research failed: ${data.message}`,
                            createdAt: new Date().toISOString()
                        }]
                    }))
                    setIsProcessing(false)
                    setResearchProgress(`Error: ${data.message}`)
                    ws.close()
                    wsRef.current = null
                    break

                default:
                    console.warn('Unknown research message type:', data.type)
            }
        }

        ws.onerror = (error) => {
            console.error('Research WebSocket error:', error)
            setMessagesByChat(prev => ({
                ...prev,
                [sessionId]: [...(prev[sessionId] || []), {
                    id: Date.now(),
                    role: 'assistant',
                    content: 'Connection error occurred during research.',
                    createdAt: new Date().toISOString()
                }]
            }))
            setIsProcessing(false)
            setResearchProgress('Connection error')
        }

        ws.onclose = () => {
            console.log('Research WebSocket closed')
            wsRef.current = null
        }

        return ws
    }

    // Regular chat WebSocket connection
    const connectWebSocket = (sessionId, prompt, model = 'gemini-2.5-flash', thinking = false) => {
        if (wsRef.current) {
            wsRef.current.close()
        }

        const ws = new WebSocket('ws://localhost:8000/ws/generate')
        wsRef.current = ws

        ws.onopen = () => {
            console.log('WebSocket connected for streaming')
            ws.send(JSON.stringify({
                prompt: prompt,
                thinking: thinking,
                model: model,
                session_id: sessionId, // Include session_id for continuation
            }))
        }

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)

            if (data.chunk) {
                // Append streaming text
                setMessagesByChat(prev => {
                    const newMessages = [...(prev[sessionId] || [])]
                    const lastMessage = newMessages[newMessages.length - 1]

                    if (lastMessage && lastMessage.role === 'assistant' && lastMessage.streaming) {
                        // Update existing streaming message
                        lastMessage.content += data.chunk
                    } else {
                        // Create new streaming message
                        const streamingMessage = {
                            id: Date.now(),
                            role: 'assistant',
                            content: data.chunk,
                            streaming: true,
                            createdAt: new Date().toISOString()
                        }
                        newMessages.push(streamingMessage)
                        currentStreamingMessageIdRef.current = streamingMessage.id
                    }

                    return {
                        ...prev,
                        [sessionId]: newMessages
                    }
                })
            } else if (data.done) {
                // Streaming completed
                setMessagesByChat(prev => {
                    const newMessages = [...(prev[sessionId] || [])]
                    const lastMessage = newMessages[newMessages.length - 1]

                    if (lastMessage && lastMessage.role === 'assistant' && lastMessage.streaming) {
                        lastMessage.streaming = false // Mark as completed
                    }

                    return {
                        ...prev,
                        [sessionId]: [...newMessages]
                    }
                })

                setIsProcessing(false)
                ws.close()
                wsRef.current = null
            } else if (data.error) {
                // Handle error
                console.error('WebSocket error:', data.error)
                setMessagesByChat(prev => ({
                    ...prev,
                    [sessionId]: [...(prev[sessionId] || []), {
                        id: Date.now(),
                        role: 'assistant',
                        content: `Error: ${data.error}`,
                        createdAt: new Date().toISOString()
                    }]
                }))
                setIsProcessing(false)
                ws.close()
                wsRef.current = null
            }
        }

        ws.onerror = (error) => {
            console.error('WebSocket error:', error)
            setMessagesByChat(prev => ({
                ...prev,
                [sessionId]: [...(prev[sessionId] || []), {
                    id: Date.now(),
                    role: 'assistant',
                    content: 'Connection error. Please try again.',
                    createdAt: new Date().toISOString()
                }]
            }))
            setIsProcessing(false)
        }

        ws.onclose = () => {
            console.log('WebSocket closed')
            wsRef.current = null
        }

        return ws
    }

    // Load chat when component mounts or chat ID changes
    useEffect(() => {
        console.log('Chat useEffect triggered:', { id, activeChatId, isLoadingChat })
        if (id && id !== activeChatId) {
            console.log('Loading chat for new session ID:', id)
            setActiveChatId(id)
            // Load chat from database
            loadChatFromDatabase(id)
        } else if (id && id === activeChatId) {
            console.log('Session ID matches active chat ID, checking if messages are loaded')
            const currentMessages = messagesByChat[id]
            if (!currentMessages) {
                console.log('No messages found for active chat, loading...')
                loadChatFromDatabase(id)
            }
        }
    }, [id, activeChatId])

    useEffect(() => {
        const state = location.state || {}
        const initialMsg = state && state.initialMsg
        const selectedModel = state.selectedModel
        const researchMode = state.isResearchMode

        // Set the model if provided in state
        if (selectedModel && selectedModel !== model) {
            setModel(selectedModel)
        }

        // Set research mode if provided in state
        if (researchMode !== undefined) {
            setIsResearchMode(researchMode)
        }

        if (initialMsg && id) {
            // Prevent duplicate seeding if user reloads or navigates back
            const seededKey = `seeded:${id}`
            if (!sessionStorage.getItem(seededKey)) {
                sessionStorage.setItem(seededKey, '1')

                // If research mode is enabled, populate the input field instead of starting research automatically
                if (researchMode) {
                    setInitialResearchInput(initialMsg.content)
                } else {
                    // Start WebSocket streaming with the initial message for regular chat
                    setMessagesByChat(prev => {
                        const currentMessages = prev[id] || []
                        const updatedMessages = [...currentMessages, initialMsg]
                        return {
                            ...prev,
                            [id]: updatedMessages
                        }
                    })
                    setIsProcessing(true)
                    connectWebSocket(id, initialMsg.content, selectedModel || 'gemini-2.5-flash', false)
                }
            }
            navigate(location.pathname, { replace: true, state: {} })
        }
    }, [id, model])

    const handleNewChat = async () => {
        // Generate a new UUID for the session (frontend generates, backend will use it)
        const newSessionId = `550e8400-e29b-41d4-a716-${Date.now().toString(16).padStart(12, '0')}`

        try {
            // Create empty session in state
            setMessagesByChat((prev) => ({
                ...prev,
                [newSessionId]: [],
            }))
            setActiveChatId(newSessionId)
            navigate(`/chat/${newSessionId}`)
        } catch (error) {
            console.error('Failed to create new chat:', error)
            // Fallback
            setMessagesByChat((prev) => ({
                ...prev,
                [newSessionId]: [],
            }))
            setActiveChatId(newSessionId)
            navigate(`/chat/${newSessionId}`)
        }
    }

    const handleSelectChat = (id) => {
        console.log('handleSelectChat called with ID:', id)
        setActiveChatId(id)
        navigate(`/chat/${id}`)
    }

    const handleUpdateTitle = (newTitle) => {
        // Update the title in the current session state
        setCurrentSession(prev => prev ? { ...prev, title: newTitle } : null)
        console.log('Title updated to:', newTitle)
        // The sidebar will refresh automatically via the API call in ChatHeader
    }

    const handleRenameChat = async (chatId, newTitle) => {
        try {
            const response = await fetch(`http://localhost:8000/api/sessions/${chatId}/title`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: newTitle }),
            })
            const data = await response.json()

            if (data.success) {
                // Refresh the chats list
                loadChatsFromDatabase()
                // Update current session if it's the active one
                if (chatId === activeChatId) {
                    setCurrentSession(prev => prev ? { ...prev, title: newTitle } : null)
                }
            } else {
                console.error('Failed to rename chat:', data.error)
                alert('Failed to rename chat')
            }
        } catch (error) {
            console.error('Error renaming chat:', error)
            alert('Error renaming chat')
        }
    }

    const handleDeleteChat = async (chatId) => {
        try {
            const response = await fetch(`http://localhost:8000/api/sessions/${chatId}`, {
                method: 'DELETE',
            })
            const data = await response.json()

            if (data.success) {
                // Refresh the chats list
                loadChatsFromDatabase()
                // If the deleted chat was active, navigate away
                if (chatId === activeChatId) {
                    navigate('/')
                }
            } else {
                console.error('Failed to delete chat:', data.error)
                alert('Failed to delete chat')
            }
        } catch (error) {
            console.error('Error deleting chat:', error)
            alert('Error deleting chat')
        }
    }

    const handleSend = async (text, files) => {
        const userMsg = { id: Date.now(), role: 'user', content: text, files, createdAt: new Date().toISOString() }

        try {
            // Messages are saved automatically via WebSocket API
            // No need to manually save here as WebSocket handles persistence
            console.log('Message will be saved via WebSocket:', {
                sessionId: activeChatId,
                role: userMsg.role,
                content: userMsg.content,
                files: files ? JSON.stringify(files) : null
            })
        } catch (error) {
            console.error('Failed to prepare message:', error)
        }

        setMessagesByChat((prev) => ({
            ...prev,
            [activeChatId]: [...(prev[activeChatId] || []), userMsg],
        }))
        setIsProcessing(true)

        // Use the selected model from AIInput or current model
        const modelToUse = location.state?.selectedModel || model || 'gemini-2.5-flash'

        // Use research WebSocket if in research mode
        if (isResearchMode) {
            connectResearchWebSocket(activeChatId, text, modelToUse)
        } else {
            // Connect WebSocket with session_id for continuation
            connectWebSocket(activeChatId, text, modelToUse, false)
        }
    }

    // Cleanup WebSocket and listeners on unmount
    useEffect(() => {
        return () => {
            if (wsRef.current) {
                wsRef.current.close()
            }
            if (unlistenRefs.current.stream) { unlistenRefs.current.stream(); unlistenRefs.current.stream = null }
            if (unlistenRefs.current.done) { unlistenRefs.current.done(); unlistenRefs.current.done = null }
            // No task to stop since we're using WebSocket
        }
    }, [])

    return (
        <div className="h-screen">
            <div className="flex h-full">
                <ChatSidebar
                    recentChats={recentChats}
                    onNewChat={handleNewChat}
                    onSelectChat={handleSelectChat}
                    onRenameChat={handleRenameChat}
                    onDeleteChat={handleDeleteChat}
                    activeChatId={activeChatId}
                />

                <main className="flex-1 flex flex-col min-h-0">
                    <ChatHeader
                        onOpenSettings={() => { }}
                        model={model}
                        chatTitle={currentSession?.title}
                        sessionId={activeChatId}
                        onUpdateTitle={handleUpdateTitle}
                        isResearchMode={isResearchMode}
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
                    {isResearchMode ? (
                        <ResearchArea
                            messages={currentMessages}
                            onSend={handleSend}
                            isProcessing={isProcessing}
                            researchProgress={researchProgress}
                            researchSources={researchSources}
                            researchImages={researchImages}
                            researchNews={researchNews}
                            researchMetadata={researchMetadata}
                            initialInput={initialResearchInput}
                        />
                    ) : (
                        <ChatArea
                            messages={currentMessages}
                            onSend={handleSend}
                            isProcessing={isProcessing}
                        />
                    )}
                </main>
            </div>
        </div>
    )
}

export default Chat