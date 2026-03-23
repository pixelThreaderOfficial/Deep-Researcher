import { useEffect, memo, useCallback, useState, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Message, MessageContent, MessageResponse } from '@/components/ai-elements/message'
import {
    Conversation,
    ConversationContent,
    ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import { Reasoning, ReasoningTrigger, ReasoningContent } from '@/components/ai-elements/reasoning'
import {
    Plan, PlanHeader, PlanTitle, PlanDescription, PlanAction, PlanContent, PlanTrigger,
} from '@/components/ai-elements/plan'
import {
    Tool, ToolHeader, ToolContent, ToolInput, ToolOutput,
} from '@/components/ai-elements/tool'
import { Sources, SourcesTrigger, SourcesContent, Source } from '@/components/ai-elements/sources'
import { Task, TaskTrigger, TaskContent, TaskItem, TaskItemFile } from '@/components/ai-elements/task'
import {
    ChainOfThought, ChainOfThoughtHeader, ChainOfThoughtContent, ChainOfThoughtStep,
    ChainOfThoughtSearchResults, ChainOfThoughtSearchResult, ChainOfThoughtImage,
} from '@/components/ai-elements/chain-of-thought'
import {
    Confirmation, ConfirmationTitle, ConfirmationRequest,
    ConfirmationAccepted, ConfirmationRejected,
    ConfirmationActions, ConfirmationAction,
} from '@/components/ai-elements/confirmation'
import {
    Artifact, ArtifactHeader, ArtifactTitle, ArtifactDescription,
    ArtifactActions, ArtifactContent,
} from '@/components/ai-elements/artifact'
import {
    InlineCitation, InlineCitationCard, InlineCitationCardTrigger, InlineCitationCardBody,
} from '@/components/ai-elements/inline-citation'
import { Shimmer } from '@/components/ai-elements/shimmer'
import { Persona } from '@/components/ai-elements/persona'
import {
    Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import {
    SearchIcon, Square, Globe, FileText, BookOpen,
    Clock, Zap, Hash, Database, CopyIcon, CheckIcon,
    ChevronLeft, Sparkles, Youtube, Link as LinkIcon,
    CheckCircle2, Circle, Loader2, Download, ExternalLink,
    ChevronDown, MessageSquare, FileJson, FileType, FileOutput, Share2,
} from 'lucide-react'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import { toast } from "sonner"
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useResearchRealtime } from './useResearchRealtime'
import { DEFAULT_SYSTEM_PROMPT } from './research_response'
import type {
    ResearchStep,
    ReasoningStep as TReasoningStep,
    PlanStep as TPlanStep,
    ToolCallStep as TToolCallStep,
    ContentStep as TContentStep,
    SourcesStep as TSourcesStep,
    TaskStep as TTaskStep,
    ChainOfThoughtStep as TCOTStep,
    ConfirmationStep as TConfirmationStep,
    ArtifactStep as TArtifactStep,
} from './research_response'
import "katex/dist/katex.min.css"

// ─── Step Renderers ───────────────────────────────────────────────────────────

const ReasoningStepRenderer = memo(({ step, isLast, isRunning }: { step: TReasoningStep; isLast: boolean; isRunning: boolean }) => (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <Reasoning isStreaming={isLast && isRunning} duration={step.durationSeconds} defaultOpen={isLast && isRunning}>
            <ReasoningTrigger />
            <ReasoningContent>{step.content}</ReasoningContent>
        </Reasoning>
    </div>
))
ReasoningStepRenderer.displayName = 'ReasoningStepRenderer'

const PlanStepRenderer = memo(({ step, isRunning }: { step: TPlanStep; isRunning: boolean }) => {
    const hasActiveTask = step.tasks.some(t => t.status === 'active')
    return (
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <Plan isStreaming={hasActiveTask && isRunning} defaultOpen>
                <PlanHeader>
                    <div>
                        <PlanTitle>{step.title}</PlanTitle>
                        <PlanDescription>{step.description}</PlanDescription>
                    </div>
                    <PlanAction>
                        <PlanTrigger />
                    </PlanAction>
                </PlanHeader>
                <PlanContent>
                    <div className="space-y-2 pb-4">
                        {step.tasks.map((task, i) => (
                            <div key={i} className="flex items-center gap-3 px-1">
                                {task.status === 'complete' ? (
                                    <CheckCircle2 className="size-4 text-green-500 shrink-0" />
                                ) : task.status === 'active' ? (
                                    <Loader2 className="size-4 text-primary animate-spin shrink-0" />
                                ) : (
                                    <Circle className="size-4 text-muted-foreground/40 shrink-0" />
                                )}
                                <span className={cn(
                                    "text-sm transition-all duration-300",
                                    task.status === 'complete' && "text-muted-foreground line-through",
                                    task.status === 'active' && "text-foreground font-medium",
                                    task.status === 'pending' && "text-muted-foreground"
                                )}>
                                    {task.label}
                                </span>
                            </div>
                        ))}
                    </div>
                </PlanContent>
            </Plan>
        </div>
    )
})
PlanStepRenderer.displayName = 'PlanStepRenderer'

const ToolCallStepRenderer = memo(({ step }: { step: TToolCallStep }) => (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <Tool>
            <ToolHeader
                title={step.title}
                type="dynamic-tool"
                state={step.state}
                toolName={step.toolName}
            />
            <ToolContent>
                <ToolInput input={step.input} />
                <ToolOutput output={step.output} errorText={step.state === 'output-error' ? 'Tool execution failed' : undefined} />
            </ToolContent>
        </Tool>
    </div>
))
ToolCallStepRenderer.displayName = 'ToolCallStepRenderer'

const ContentStepRenderer = memo(({ step, isLast, isRunning }: { step: TContentStep; isLast: boolean; isRunning: boolean }) => {
    const streaming = (isLast && isRunning) || step.isStreaming
    return (
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <Message from="assistant" className="max-w-full">
                <MessageContent className="bg-transparent px-0 py-0 w-full text-justify">
                    <MessageResponse
                        isAnimating={streaming}
                        className={cn(streaming && "streaming-text-fade")}
                    >
                        {step.content}
                    </MessageResponse>

                    {step.citations && step.citations.length > 0 && !streaming && (
                        <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-border/30">
                            {step.citations.map((cit, i) => (
                                <InlineCitation key={i}>
                                    <InlineCitationCard>
                                        <InlineCitationCardTrigger sources={cit.sources.map(s => s.url)} />
                                        <InlineCitationCardBody>
                                            <div className="space-y-2 p-3">
                                                {cit.sources.map((src, si) => (
                                                    <div key={si} className="space-y-1">
                                                        <a
                                                            href={src.url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="text-sm font-medium text-primary hover:underline"
                                                        >
                                                            {src.title}
                                                        </a>
                                                        <p className="text-xs text-muted-foreground">{src.description}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        </InlineCitationCardBody>
                                    </InlineCitationCard>
                                </InlineCitation>
                            ))}
                        </div>
                    )}
                </MessageContent>
            </Message>
        </div>
    )
})
ContentStepRenderer.displayName = 'ContentStepRenderer'

const SourcesStepRenderer = memo(({ step }: { step: TSourcesStep }) => (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <Sources>
            <SourcesTrigger count={step.items.length} />
            <SourcesContent>
                {step.items.map((s, i) => (
                    <Source key={i} href={s.href} title={s.title} />
                ))}
            </SourcesContent>
        </Sources>
    </div>
))
SourcesStepRenderer.displayName = 'SourcesStepRenderer'

const TaskStepRenderer = memo(({ step }: { step: TTaskStep }) => (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <Task defaultOpen>
            <TaskTrigger title={step.title} />
            <TaskContent>
                {step.items.map((item, i) => (
                    <TaskItem key={i}>
                        <span>{item.label}</span>
                        {item.file && (
                            <TaskItemFile className="ml-2">
                                <FileText className="size-3" />
                                {item.file}
                            </TaskItemFile>
                        )}
                    </TaskItem>
                ))}
            </TaskContent>
        </Task>
    </div>
))
TaskStepRenderer.displayName = 'TaskStepRenderer'

const COTStepRenderer = memo(({ step }: { step: TCOTStep }) => (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="bg-accent/50 rounded-2xl border border-border/50 overflow-hidden">
            <ChainOfThought className="p-4 pb-0 w-full" defaultOpen>
                <ChainOfThoughtHeader className="w-full" />
                <ChainOfThoughtContent className="w-full pr-4">
                    {step.steps.map((s, i) => (
                        <ChainOfThoughtStep
                            key={i}
                            icon={SearchIcon}
                            label={s.label}
                            status={s.status}
                        >
                            {s.content && (
                                <p className="text-sm text-muted-foreground mt-1 mb-1 w-full leading-relaxed">
                                    {s.content}
                                </p>
                            )}

                            {/* Search results as badges */}
                            {s.searchResults && s.searchResults.length > 0 && (
                                <ChainOfThoughtSearchResults className="mt-1 mb-1">
                                    {s.searchResults.map((sr, sri) => (
                                        <ChainOfThoughtSearchResult key={sri}>
                                            {sr.url ? (
                                                <a href={sr.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                                                    {sr.label}
                                                </a>
                                            ) : sr.label}
                                        </ChainOfThoughtSearchResult>
                                    ))}
                                </ChainOfThoughtSearchResults>
                            )}

                            {/* Image within thought step */}
                            {s.image && (
                                <ChainOfThoughtImage
                                    caption={s.image.caption}
                                    className="mt-1 mb-2"
                                >
                                    <img
                                        src={s.image.src}
                                        alt={s.image.caption}
                                        className="object-cover w-full h-full rounded-md"
                                    />
                                </ChainOfThoughtImage>
                            )}
                        </ChainOfThoughtStep>
                    ))}
                </ChainOfThoughtContent>
            </ChainOfThought>
        </div>
    </div>
))
COTStepRenderer.displayName = 'COTStepRenderer'

const ConfirmationStepRenderer = memo(({
    step,
    isPending,
    wasApproved,
    onApprove,
    onReject,
}: {
    step: TConfirmationStep
    isPending: boolean
    wasApproved: boolean | null
    onApprove: (value: string) => void
    onReject: (reason?: string) => void
}) => {
    // Build the approval object the Confirmation component expects
    const approvalObj = isPending
        ? { id: step.question }
        : wasApproved === true
            ? { id: step.question, approved: true as const }
            : wasApproved === false
                ? { id: step.question, approved: false as const, reason: 'User declined' }
                : { id: step.question }

    return (
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <Confirmation
                approval={approvalObj}
                state={isPending ? 'approval-requested' : 'approval-responded'}
            >
                <ConfirmationTitle>
                    <div className="flex items-center gap-2 mb-2">
                        <div className="size-6 rounded-full bg-primary/20 flex items-center justify-center">
                            <Sparkles className="size-3.5 text-primary" />
                        </div>
                        <span className="font-medium">Approval Required</span>
                    </div>
                    <ConfirmationRequest>
                        <p className="text-sm text-muted-foreground mt-1">{step.question}</p>
                    </ConfirmationRequest>
                    <ConfirmationAccepted>
                        <div className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400 mt-2">
                            <CheckCircle2 className="size-3" />
                            Approved — proceeding with detailed analysis
                        </div>
                    </ConfirmationAccepted>
                    <ConfirmationRejected>
                        <div className="flex items-center gap-1.5 text-xs text-destructive mt-2">
                            Research stopped by user
                        </div>
                    </ConfirmationRejected>
                </ConfirmationTitle>
                <ConfirmationActions>
                    {step.actions.map((action, i) => (
                        <ConfirmationAction
                            key={i}
                            onClick={() => onApprove(action.value)}
                        >
                            {action.label}
                        </ConfirmationAction>
                    ))}
                    <ConfirmationAction
                        variant="outline"
                        onClick={() => onReject('User declined')}
                    >
                        Decline
                    </ConfirmationAction>
                </ConfirmationActions>
            </Confirmation>
        </div>
    )
})
ConfirmationStepRenderer.displayName = 'ConfirmationStepRenderer'

const ArtifactStepRenderer = memo(({
    step,
    onOpenArtifact,
}: {
    step: TArtifactStep
    onOpenArtifact: () => void
}) => {
    const handleDownload = (format: 'md' | 'pdf' | 'docx') => {
        if (format === 'md') {
            const blob = new Blob([step.content], { type: 'text/markdown' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `${step.title.replace(/[^a-zA-Z0-9]/g, '_')}.md`
            a.click()
            URL.revokeObjectURL(url)
            toast.success("Markdown report downloaded")
        } else {
            // Simulated formats
            toast.info(`Generating ${format.toUpperCase()} report...`)
            setTimeout(() => {
                const blob = new Blob([step.content], { type: 'text/plain' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${step.title.replace(/[^a-zA-Z0-9]/g, '_')}.${format}`
                a.click()
                URL.revokeObjectURL(url)
                toast.success(`${format.toUpperCase()} report downloaded`)
            }, 1000)
        }
    }

    return (
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <Artifact className="border-primary/20 bg-linear-to-b from-card to-card/50 shadow-xl overflow-hidden">
                <ArtifactHeader className="border-b border-border/10 bg-muted/5 p-6">
                    <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="h-5 px-1.5 text-[10px] uppercase tracking-wider font-bold bg-primary/5 border-primary/20 text-primary">
                                Research Artifact
                            </Badge>
                            <span className="text-[10px] text-muted-foreground">•</span>
                            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">Ready</span>
                        </div>
                        <ArtifactTitle className="text-xl font-bold tracking-tight">{step.title}</ArtifactTitle>
                        <ArtifactDescription className="text-sm text-muted-foreground/80">{step.description}</ArtifactDescription>
                    </div>
                    <ArtifactActions>
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="outline" size="sm" className="h-9 gap-1.5 border-primary/20 bg-background/50 backdrop-blur-sm">
                                    <Download className="size-4" />
                                    Download
                                    <ChevronDown className="size-3.5 opacity-50" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-48">
                                <DropdownMenuItem onClick={() => handleDownload('pdf')} className="gap-2">
                                    <FileType className="size-4 text-red-500" />
                                    <span>Download PDF</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleDownload('docx')} className="gap-2">
                                    <FileType className="size-4 text-blue-500" />
                                    <span>Download Word</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleDownload('md')} className="gap-2">
                                    <FileText className="size-4 text-primary" />
                                    <span>Download Markdown</span>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem className="gap-2">
                                    <FileJson className="size-4 text-amber-500" />
                                    <span>Download RAW Data</span>
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>

                        <Button
                            variant="default"
                            size="sm"
                            className="h-9 gap-1.5 shadow-lg shadow-primary/20"
                            onClick={onOpenArtifact}
                        >
                            <ExternalLink className="size-4" />
                            Open Report
                        </Button>
                    </ArtifactActions>
                </ArtifactHeader>
                <ArtifactContent className="p-0">
                    <div
                        className="group relative cursor-pointer hover:bg-muted/50 transition-all p-8 flex gap-6 items-start"
                        onClick={onOpenArtifact}
                    >
                        {/* Report Cover Preview Style */}
                        <div className="w-24 h-32 shrink-0 rounded border border-border/50 bg-background shadow-inner flex flex-col p-2 gap-1 overflow-hidden transition-transform group-hover:scale-105 group-hover:rotate-1">
                            <div className="h-1.5 w-full bg-primary/20 rounded-full" />
                            <div className="h-1 w-2/3 bg-muted rounded-full mt-1" />
                            <div className="mt-2 space-y-1">
                                <div className="h-0.5 w-full bg-border rounded-full" />
                                <div className="h-0.5 w-full bg-border rounded-full" />
                                <div className="h-0.5 w-3/4 bg-border rounded-full" />
                                <div className="h-0.5 w-full bg-border rounded-full" />
                                <div className="h-0.5 w-1/2 bg-border rounded-full" />
                            </div>
                            <div className="mt-auto h-8 w-full bg-muted/20 rounded flex items-center justify-center">
                                <FileText className="size-3 text-muted-foreground" />
                            </div>
                        </div>

                        <div className="flex-1 min-w-0">
                            <h4 className="font-semibold text-foreground mb-2 group-hover:text-primary transition-colors">Executive Summary</h4>
                            <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3 italic font-serif">
                                "{step.content.slice(0, 300).replace(/[#*_[\]]/g, '')}..."
                            </p>
                            <div className="flex items-center gap-3 mt-4">
                                <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">PDF v1.0</span>
                                <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">Markdown</span>
                                <span className="text-[10px] font-bold text-primary ml-auto group-hover:translate-x-1 transition-transform">
                                    Click to read full template report →
                                </span>
                            </div>
                        </div>
                    </div>
                </ArtifactContent>
            </Artifact>
        </div>
    )
})
ArtifactStepRenderer.displayName = 'ArtifactStepRenderer'

// ─── Step Dispatcher ──────────────────────────────────────────────────────────

const ResearchStepItem = memo(({
    step, isLast, isRunning,
    isPendingConfirmation, confirmationApproved, onApprove, onReject,
    onOpenArtifact,
}: {
    step: ResearchStep
    isLast: boolean
    isRunning: boolean
    isPendingConfirmation: boolean
    confirmationApproved: boolean | null
    onApprove: (value: string) => void
    onReject: (reason?: string) => void
    onOpenArtifact: () => void
}) => {
    switch (step.type) {
        case 'reasoning': return <ReasoningStepRenderer step={step} isLast={isLast} isRunning={isRunning} />
        case 'plan': return <PlanStepRenderer step={step} isRunning={isRunning} />
        case 'tool-call': return <ToolCallStepRenderer step={step} />
        case 'content': return <ContentStepRenderer step={step} isLast={isLast} isRunning={isRunning} />
        case 'sources': return <SourcesStepRenderer step={step} />
        case 'task': return <TaskStepRenderer step={step} />
        case 'chain-of-thought': return <COTStepRenderer step={step} />
        case 'confirmation': return (
            <ConfirmationStepRenderer
                step={step}
                isPending={isPendingConfirmation && isLast}
                wasApproved={confirmationApproved}
                onApprove={onApprove}
                onReject={onReject}
            />
        )
        case 'artifact': return <ArtifactStepRenderer step={step} onOpenArtifact={onOpenArtifact} />
        default: return null
    }
})
ResearchStepItem.displayName = 'ResearchStepItem'

// ─── Stats Bar ────────────────────────────────────────────────────────────────

const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return m > 0 ? `${m}m ${s}s` : `${s}s`
}

const StatsBar = memo(({ stats, elapsedSeconds, isRunning }: {
    stats: { tokensUsed: number; filesReferenced: number; websitesVisited: number; docsRead: number; contextTokens: number }
    elapsedSeconds: number
    isRunning: boolean
}) => (
    <div className={cn(
        "flex items-center gap-4 flex-wrap text-xs text-muted-foreground font-mono transition-opacity",
        isRunning ? "opacity-100" : "opacity-70"
    )}>
        <div className="flex items-center gap-1.5">
            <Clock className="size-3.5" />
            <span>{formatTime(elapsedSeconds)}</span>
        </div>
        <div className="flex items-center gap-1.5">
            <Zap className="size-3.5 text-amber-500" />
            <span>{stats.tokensUsed.toLocaleString()} tokens</span>
        </div>
        <div className="flex items-center gap-1.5">
            <Globe className="size-3.5 text-blue-500" />
            <span>{stats.websitesVisited} sites</span>
        </div>
        <div className="flex items-center gap-1.5">
            <FileText className="size-3.5 text-orange-500" />
            <span>{stats.filesReferenced} files</span>
        </div>
        <div className="flex items-center gap-1.5">
            <BookOpen className="size-3.5 text-green-500" />
            <span>{stats.docsRead} docs</span>
        </div>
        <div className="flex items-center gap-1.5">
            <Database className="size-3.5 text-purple-500" />
            <span>~{stats.contextTokens.toLocaleString()} ctx</span>
        </div>
    </div>
))
StatsBar.displayName = 'StatsBar'

// ─── Main Component ───────────────────────────────────────────────────────────

interface ResearchNavigationState {
    id?: string
    title: string
    description: string
    prompt: string
    workspaceId: string
    workspaceName: string
    preferences: {
        enableChat: boolean
        allowBackendResearch: boolean
        template: string
        customInstructions: string
    }
    sources: { type: string; value: string; name?: string }[]
}

const ResearchThread = () => {
    const location = useLocation()
    const navigate = useNavigate()
    const state = location.state as ResearchNavigationState | null

    const researchId = state?.id || location.pathname.split('/').pop() || ""

    const {
        steps, stats, isRunning, elapsedSeconds,
        isPendingConfirmation, approveConfirmation, rejectConfirmation,
        stopResearch, startResearch,
    } = useResearchRealtime(researchId)
    
    const [copyStatus, setCopyStatus] = useState<'idle' | 'loading' | 'success'>('idle')
    const [artifactOpen, setArtifactOpen] = useState(false)
    // Track whether the confirmation was approved or rejected
    const [confirmationApproved, setConfirmationApproved] = useState<boolean | null>(null)
    const confirmationApprovedRef = useRef<boolean | null>(null)

    // Wrapped approve/reject handlers that track the outcome
    const handleConfirmApprove = useCallback((value: string) => {
        setConfirmationApproved(true)
        confirmationApprovedRef.current = true
        approveConfirmation(value)
    }, [approveConfirmation])

    const handleConfirmReject = useCallback((reason?: string) => {
        setConfirmationApproved(false)
        confirmationApprovedRef.current = false
        rejectConfirmation(reason)
    }, [rejectConfirmation])

    // Find the artifact step for the sheet content
    const artifactStep = steps.find((s): s is ResearchStep & { type: 'artifact' } => s.type === 'artifact') as
        | (ResearchStep & { type: 'artifact'; title: string; description: string; content: string })
        | undefined

    // Auto-start on mount
    useEffect(() => {
        const timer = setTimeout(() => {
            startResearch()
        }, 800)
        return () => clearTimeout(timer)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const handleCopyAll = useCallback(async () => {
        setCopyStatus('loading')
        const allContent = steps
            .filter((s): s is TContentStep => s.type === 'content')
            .map(s => s.content)
            .join('\n\n')
        try {
            await navigator.clipboard.writeText(allContent)
            setCopyStatus('success')
            setTimeout(() => setCopyStatus('idle'), 2000)
        } catch {
            setCopyStatus('idle')
        }
    }, [steps])

    const researchTitle = state?.title || 'AI Impact on Healthcare'
    const workspaceName = state?.workspaceName || 'Research Workspace'
    const userPrompt = state?.prompt || 'Analyze the impact of AI on the healthcare industry, focusing on diagnostics, drug discovery, and patient outcomes. Include recent data from 2023-2025.'
    const userSources = state?.sources || []

    return (
        <div className="flex flex-col h-full w-full text-foreground animate-in fade-in duration-500 overflow-hidden relative">
            {/* Floating Header */}
            <header className="absolute top-4 left-6 right-6 z-30 pointer-events-none">
                <div className="pointer-events-auto backdrop-blur-xl bg-background/80 border border-border/50 rounded-2xl px-6 py-3 shadow-lg shadow-black/5 animate-in fade-in slide-in-from-top-2 duration-500 flex items-center gap-3 w-fit">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 shrink-0"
                        onClick={() => navigate(-1)}
                    >
                        <ChevronLeft className="size-4" />
                    </Button>
                    {isRunning && (
                        <Persona
                            state={steps.length > 0 && steps[steps.length - 1]?.type === 'content' ? 'speaking' : 'thinking'}
                            className="size-5"
                            variant="glint"
                        />
                    )}
                    <div className="flex flex-col">
                        <h2 className="text-sm font-semibold bg-linear-to-r from-foreground to-foreground/70 bg-clip-text text-transparent leading-none">
                            {researchTitle}
                        </h2>
                        <p className="text-[10px] text-muted-foreground/60 mt-1 font-medium">
                            {workspaceName} • {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </p>
                    </div>
                </div>
            </header>

            {/* Conversation Area */}
            <Conversation className="flex-1 w-full">
                <ConversationContent className="max-w-4xl mx-auto pt-20 pb-48 space-y-6">

                    {/* ── System Prompt (collapsed) ────────────────────────────────── */}
                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
                        <Message from="assistant" className="max-w-full">
                            <MessageContent className="bg-transparent px-0 py-0 w-full">
                                <Task defaultOpen={false}>
                                    <TaskTrigger title="System Prompt Loaded" />
                                    <TaskContent>
                                        <TaskItem>
                                            <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
                                                {DEFAULT_SYSTEM_PROMPT}
                                            </pre>
                                        </TaskItem>
                                    </TaskContent>
                                </Task>
                            </MessageContent>
                        </Message>
                    </div>

                    {/* ── User Prompt Bubble ───────────────────────────────────────── */}
                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-500 delay-200">
                        <Message from="user" className="pl-12 ml-auto max-w-full">
                            <MessageContent className="shadow-sm text-foreground">
                                <MessageResponse>{userPrompt}</MessageResponse>

                                {/* Attached sources */}
                                {userSources.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-border/30 space-y-2">
                                        <span className="text-xs font-medium text-muted-foreground">Attached Sources</span>
                                        <div className="flex flex-wrap gap-2">
                                            {userSources.map((source, i) => (
                                                <Badge key={i} variant="secondary" className="gap-1.5 text-xs">
                                                    {source.type === 'youtube' ? (
                                                        <Youtube className="size-3 text-red-500" />
                                                    ) : source.type === 'file' ? (
                                                        <FileText className="size-3 text-orange-500" />
                                                    ) : (
                                                        <LinkIcon className="size-3 text-blue-500" />
                                                    )}
                                                    {source.name || source.value}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Preferences summary */}
                                {state?.preferences && (
                                    <div className="mt-2 flex flex-wrap gap-1.5">
                                        <Badge variant="outline" className="text-[10px] gap-1">
                                            <Hash className="size-2.5" />
                                            {state.preferences.template}
                                        </Badge>
                                        {state.preferences.allowBackendResearch && (
                                            <Badge variant="outline" className="text-[10px] gap-1">
                                                <Zap className="size-2.5" />
                                                Backend Research
                                            </Badge>
                                        )}
                                    </div>
                                )}
                            </MessageContent>
                        </Message>
                    </div>

                    {/* ── Research Steps ───────────────────────────────────────────── */}
                    {steps.map((step, idx) => (
                        <ResearchStepItem
                            key={idx}
                            step={step}
                            isLast={idx === steps.length - 1}
                            isRunning={isRunning}
                            isPendingConfirmation={isPendingConfirmation}
                            confirmationApproved={confirmationApproved}
                            onApprove={handleConfirmApprove}
                            onReject={handleConfirmReject}
                            onOpenArtifact={() => setArtifactOpen(true)}
                        />
                    ))}

                    {/* ── Thinking shimmer when running with no new step ───────────── */}
                    {isRunning && steps.length > 0 && !isPendingConfirmation && (
                        <div className="flex items-center gap-2 animate-in fade-in duration-300">
                            <Persona state="thinking" className="size-5" variant="glint" />
                            <Shimmer className="text-sm font-medium">Researching...</Shimmer>
                        </div>
                    )}

                    {/* ── Finish State: Chat link ──────────────────────────────────── */}
                    {!isRunning && steps.length > 0 && (
                        <div className="flex justify-center pt-8 pb-12 animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-500">
                            <div className="p-8 rounded-3xl border border-primary/20 bg-linear-to-b from-primary/5 to-transparent flex flex-col items-center text-center max-w-lg w-full">
                                <div className="size-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                                    <MessageSquare className="size-6 text-primary" />
                                </div>
                                <h3 className="text-xl font-bold mb-2">Research Completed Successfully</h3>
                                <p className="text-sm text-muted-foreground mb-6">
                                    The deep research has been synthesized into the final artifact.
                                    You can now dive deeper into the findings or ask follow-up questions.
                                </p>
                                <div className="flex items-center gap-3 w-full">
                                    <Button className="flex-1 gap-2 h-11 text-base shadow-lg shadow-primary/20">
                                        <MessageSquare className="size-4" />
                                        Chat on this research
                                    </Button>
                                    <Button variant="outline" className="flex-1 gap-2 h-11 text-base">
                                        <Share2 className="size-4" />
                                        Share Report
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}
                </ConversationContent>
                <ConversationScrollButton />
            </Conversation>

            {/* ── Footer: Stats + Stop ────────────────────────────────────────── */}
            <footer className="shrink-0 border-t border-border/50 bg-background/80 backdrop-blur-sm z-20">
                <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
                    <StatsBar stats={stats} elapsedSeconds={elapsedSeconds} isRunning={isRunning} />

                    <div className="flex items-center gap-2">
                        {/* Copy all content */}
                        {!isRunning && steps.length > 0 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 gap-1.5 text-xs"
                                onClick={handleCopyAll}
                                disabled={copyStatus !== 'idle'}
                            >
                                {copyStatus === 'success' ? (
                                    <><CheckIcon className="size-3.5 text-green-500" /> Copied</>
                                ) : copyStatus === 'loading' ? (
                                    <><Loader2 className="size-3.5 animate-spin" /> Copying...</>
                                ) : (
                                    <><CopyIcon className="size-3.5" /> Copy Report</>
                                )}
                            </Button>
                        )}

                        {/* Stop button */}
                        {isRunning && (
                            <Button
                                onClick={stopResearch}
                                variant="destructive"
                                size="sm"
                                className="h-9 px-5 gap-2 shadow-lg shadow-destructive/20 animate-in fade-in zoom-in-95 duration-200"
                            >
                                <Square className="size-3.5 fill-current" />
                                Stop Research
                            </Button>
                        )}
                    </div>
                </div>

                {/* Research complete message */}
                {!isRunning && steps.length > 0 && (
                    <div className="text-center pb-3">
                        <p className="text-[10px] text-muted-foreground/50 font-medium">
                            Research completed in {formatTime(elapsedSeconds)} • {stats.tokensUsed.toLocaleString()} tokens used
                        </p>
                    </div>
                )}
            </footer>

            {/* ── Artifact Sheet ───────────────────────────────────────────────── */}
            <Sheet open={artifactOpen} onOpenChange={setArtifactOpen}>
                <SheetContent side="right" className="w-full sm:w-1/2 sm:max-w-none border-l border-border/50 bg-card/95 backdrop-blur-xl p-0 flex flex-col overflow-hidden">
                    <div className="flex-1 overflow-y-auto px-8 pt-8 pb-32">
                        <SheetHeader className="space-y-4 p-0">
                            <div className="flex items-center gap-4">
                                <div className="size-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
                                    <FileText className="size-7 text-primary" />
                                </div>
                                <div>
                                    <SheetTitle className="text-2xl font-bold tracking-tight">{artifactStep?.title || 'Research Report'}</SheetTitle>
                                    <SheetDescription className="text-base">
                                        {artifactStep?.description || 'Generated by Deep Researcher Engine'}
                                    </SheetDescription>
                                </div>
                            </div>
                        </SheetHeader>

                        <div className="mt-12 bg-background rounded-3xl border border-border/50 shadow-sm p-8 max-w-none">
                            <Message from="assistant" className="max-w-none w-full">
                                <MessageContent className="bg-transparent px-0 py-0 w-full text-base leading-relaxed">
                                    <MessageResponse>
                                        {artifactStep?.content || ''}
                                    </MessageResponse>
                                </MessageContent>
                            </Message>
                        </div>
                    </div>

                    <div className="shrink-0 p-8 border-t bg-background/50 backdrop-blur-xl flex items-center justify-between gap-4 absolute bottom-0 left-0 right-0">
                        <Button
                            variant="ghost"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => setArtifactOpen(false)}
                        >
                            Close Report
                        </Button>

                        <div className="flex items-center gap-3">
                            <Button variant="outline" className="gap-2 border-primary/20">
                                <FileOutput className="size-4" />
                                Export JSON
                            </Button>
                            <Button className="gap-2 shadow-lg shadow-primary/20" onClick={() => {
                                if (artifactStep) {
                                    const blob = new Blob([artifactStep.content], { type: 'text/markdown' })
                                    const url = URL.createObjectURL(blob)
                                    const a = document.createElement('a')
                                    a.href = url
                                    a.download = `${artifactStep.title}.md`
                                    a.click()
                                }
                            }}>
                                <Download className="size-4" />
                                Download Markdown
                            </Button>
                        </div>
                    </div>
                </SheetContent>
            </Sheet>
        </div>
    )
}

export default ResearchThread