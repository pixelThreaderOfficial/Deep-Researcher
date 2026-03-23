import { useState, useRef, useCallback, useEffect } from 'react'
import type { ResearchStep, ResearchStats } from './research_response'
import { resolveApiUrl } from '@/lib/apis'

export interface UseResearchRealtimeReturn {
    steps: ResearchStep[]
    stats: ResearchStats
    isRunning: boolean
    elapsedSeconds: number
    isPendingConfirmation: boolean
    pendingConfirmationStep: ResearchStep | null
    approveConfirmation: (value: string) => void
    rejectConfirmation: (reason?: string) => void
    stopResearch: () => void
    startResearch: () => void
}

export function useResearchRealtime(
    researchId: string
): UseResearchRealtimeReturn {
    const [steps, setSteps] = useState<ResearchStep[]>([])
    const [isRunning, setIsRunning] = useState(false)
    const [elapsedSeconds, setElapsedSeconds] = useState(0)
    const [stats, setStats] = useState<ResearchStats>({
        tokensUsed: 0,
        filesReferenced: 0,
        websitesVisited: 0,
        docsRead: 0,
        contextTokens: 0,
    })
    
    // Timer
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const eventSourceRef = useRef<EventSource | null>(null)

    useEffect(() => {
        if (isRunning) {
            timerRef.current = setInterval(() => {
                setElapsedSeconds((prev) => prev + 1)
            }, 1000)
        } else if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
        }
        return () => {
            if (timerRef.current) clearInterval(timerRef.current)
        }
    }, [isRunning])

    const startResearch = useCallback(async () => {
        if (!researchId) return;
        
        setIsRunning(true)
        setSteps([])
        setElapsedSeconds(0)
        
        // Connect to SSE first to catch early updates
        const sseUrl = resolveApiUrl(`/events/${researchId}`)
        if (sseUrl) {
            const sse = new EventSource(sseUrl)
            eventSourceRef.current = sse

            sse.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data)
                    const stage = data.stage
                    const message = data.message || ''
                    const toolData = data.data || {}

                    // Update stats if we got any
                    setStats(prev => ({
                        tokensUsed: toolData.tokens_used || prev.tokensUsed,
                        filesReferenced: toolData.files_count || prev.filesReferenced,
                        websitesVisited: toolData.total_sources || toolData.websites_count || prev.websitesVisited,
                        docsRead: toolData.total_steps || prev.docsRead,
                        contextTokens: toolData.context_tokens || prev.contextTokens
                    }))

                    if (data.status === 'completed' || data.status === 'failed') {
                        setIsRunning(false)
                        sse.close()
                        eventSourceRef.current = null
                        
                        if (data.status === 'completed' && stage === 'finalizing_output') {
                            const artifact = toolData.artifact
                            if (artifact) {
                                setSteps(prev => [...prev, {
                                    type: 'artifact',
                                    title: artifact.title || 'Research Report',
                                    description: artifact.summary || 'Completed research artifact.',
                                    content: artifact.markdown_content || '',
                                    delay: 0
                                }])
                            }
                        } else if (data.status === 'failed') {
                            setSteps(prev => [...prev, {
                                type: 'content',
                                content: `Research failed: ${message}`,
                                isStreaming: false,
                                delay: 0
                            }])
                        }
                        return
                    }

                    // Map various stages
                    if (stage === 'thinking') {
                        setSteps(prev => [...prev, {
                            type: 'reasoning',
                            content: toolData.thought || message || 'Thinking...',
                            durationSeconds: 1,
                            delay: 0
                        }])
                    } else if (stage === 'acting') {
                        setSteps(prev => [...prev, {
                            type: 'tool-call',
                            title: `Using ${toolData.tool || 'Action'}`,
                            toolName: toolData.tool || 'Action',
                            input: toolData.parameters || {},
                            output: toolData.result || message,
                            state: 'output-available',
                            delay: 0
                        }])
                    } else if (stage === 'semantic_search' || stage === 'searching_sources' || stage === 'youtube_search') {
                        setSteps(prev => [...prev, {
                            type: 'chain-of-thought',
                            label: 'Information Search',
                            steps: [{
                                icon: 'search',
                                status: 'complete',
                                label: message || 'Searching',
                                content: toolData.query || ''
                            }],
                            delay: 0
                        }])
                    } else if (stage === 'validating_query' || stage === 'generating_research_plan' || stage === 'ingesting_vectors') {
                        setSteps(prev => {
                            const hasPlan = prev.find(p => p.type === 'plan');
                            if (!hasPlan) {
                                return [...prev, {
                                    type: 'plan',
                                    title: 'Research Processing',
                                    description: 'Executing background research steps',
                                    tasks: [{ status: 'active', label: message }],
                                    delay: 0
                                }]
                            }
                            const filtered = prev.filter(p => p.type !== 'plan');
                            return [...filtered, {
                                type: 'plan',
                                title: 'Research Processing',
                                description: 'Executing background research steps',
                                tasks: [{ status: 'active', label: message }],
                                delay: 0
                            }]
                        })
                    } else if (stage === 'summarizing_findings' || stage === 'analyzing_data' || stage === 'generating_artifact') {
                        setSteps(prev => [...prev, {
                            type: 'task',
                            title: 'Status Update',
                            items: [{ label: message }],
                            delay: 0
                        }])
                    }
                    
                } catch (err) {
                    console.error("Parse SSE error", err)
                }
            }

            sse.onerror = (err) => {
                console.error("SSE Error:", err)
                sse.close()
                setIsRunning(false)
            }
        }


    }, [researchId])

    const stopResearch = useCallback(() => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }
        setIsRunning(false)
    }, [])

    return {
        steps,
        stats,
        isRunning,
        elapsedSeconds,
        isPendingConfirmation: false,
        pendingConfirmationStep: null,
        approveConfirmation: () => {},
        rejectConfirmation: () => {},
        stopResearch,
        startResearch,
    }
}
