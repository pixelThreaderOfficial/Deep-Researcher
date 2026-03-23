import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useFilePicker } from 'use-file-picker'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { PromptEditor } from '@/components/ui/prompt-editor'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { ResearchTemplateSelector } from '@/ui/components/ResearchTemplateSelector'
import { cn } from '@/lib/utils'
import {
  Sparkles,
  Briefcase,
  TrendingUp,
  Users,
  Globe,
  Youtube,
  Link as LinkIcon,
  Plus,
  X,
  MessageSquare,
  Settings2,
  Library,
  ArrowRight,
  Upload,
  FileText,
  Zap
} from 'lucide-react'
import { createResearchRecord, createResearchSourceRecord, getAllWorkspaces, runResearch } from '@/lib/apis'

const WORKSPACE_STYLES = [
  {
    icon: TrendingUp,
    color: 'text-blue-400',
    bgColor: 'bg-blue-400/10',
    borderColor: 'border-blue-400/20',
  },
  {
    icon: Users,
    color: 'text-purple-400',
    bgColor: 'bg-purple-400/10',
    borderColor: 'border-purple-400/20',
  },
  {
    icon: Briefcase,
    color: 'text-green-400',
    bgColor: 'bg-green-400/10',
    borderColor: 'border-green-400/20',
  },
]

interface WorkspaceOption {
  id: string
  title: string
  description: string
  icon: typeof Briefcase
  color: string
  bgColor: string
  borderColor: string
}

export default function NewResearch() {
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState<WorkspaceOption[]>([])
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(false)
  const [isStartingResearch, setIsStartingResearch] = useState(false)

  // State
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')
  const [selectedWorkspace, setSelectedWorkspace] = useState<string | null>(null)

  // Preferences
  const [enableChat, setEnableChat] = useState(true)
  const [allowBackendResearch, setAllowBackendResearch] = useState(true)
  const [template, setTemplate] = useState('comprehensive')
  const [customInstructions, setCustomInstructions] = useState('')

  // Sources
  const [sources, setSources] = useState<{ type: 'url' | 'youtube' | 'file', value: string, name?: string, file?: File }[]>([])
  const [newUrl, setNewUrl] = useState('')

  useEffect(() => {
    let isCancelled = false

    const loadWorkspaces = async () => {
      setIsLoadingWorkspaces(true)
      try {
        const { workspaces: workspaceRecords } = await getAllWorkspaces()
        if (isCancelled) return

        const mapped = workspaceRecords.map((workspace, index) => {
          const style = WORKSPACE_STYLES[index % WORKSPACE_STYLES.length]
          return {
            id: workspace.id,
            title: workspace.name,
            description: workspace.description || 'No description available',
            icon: style.icon,
            color: style.color,
            bgColor: style.bgColor,
            borderColor: style.borderColor,
          }
        })

        setWorkspaces(mapped)
      } catch (error) {
        console.error('Failed to load workspaces', error)
      } finally {
        if (!isCancelled) {
          setIsLoadingWorkspaces(false)
        }
      }
    }

    void loadWorkspaces()

    return () => {
      isCancelled = true
    }
  }, [])

  const { openFilePicker, clear } = useFilePicker({
    accept: ['.pdf', '.docx', '.txt'],
    multiple: true,
    onFilesSelected: ({ plainFiles }) => {
      if (plainFiles && plainFiles.length > 0) {
        const newFiles = plainFiles.map((file: File) => ({
          type: 'file' as const,
          value: file.name,
          name: file.name,
          file: file
        }))

        setSources(prev => {
          // Filter out duplicates based on name
          const existingNames = new Set(prev.map(s => s.name))
          const uniqueNewFiles = newFiles.filter((f: { name: string }) => !existingNames.has(f.name))
          return [...prev, ...uniqueNewFiles]
        })

        // Clear internal state to allow re-selecting same files if needed
        clear()
      }
    }
  })

  const handleAddSource = () => {
    if (!newUrl) return

    let type: 'url' | 'youtube' = 'url'
    if (newUrl.includes('youtube.com') || newUrl.includes('youtu.be')) {
      type = 'youtube'
    }

    setSources([...sources, { type, value: newUrl, name: newUrl }])
    setNewUrl('')
  }

  const removeSource = (index: number) => {
    setSources(sources.filter((_, i) => i !== index))
  }

  const handleStartResearch = async () => {
    if (!selectedWorkspace || isStartingResearch) return

    setIsStartingResearch(true)

    const researchData = {
      title: title || 'Deep Research Task (Auto-generated)',
      description: description || 'Auto-generated description based on context.',
      prompt,
      workspaceId: selectedWorkspace,
      workspaceName: workspaces.find(ws => ws.id === selectedWorkspace)?.title || 'Unknown Workspace',
      preferences: {
        enableChat,
        allowBackendResearch,
        template,
        customInstructions,
      },
      sources: sources.map(s => ({ type: s.type, value: s.value, name: s.name })),
    }

    try {
      const createdResearch = await createResearchRecord({
        title: researchData.title,
        desc: researchData.description,
        prompt: researchData.prompt,
        workspace_id: researchData.workspaceId,
        chat_access: enableChat,
        background_processing: allowBackendResearch,
        research_template_id: template,
        custom_instructions: customInstructions || null,
      })

      const sourcePayloads = sources.map((source) => ({
        research_id: createdResearch.id,
        source_type: source.type,
        source_url: source.value,
      }))

      await Promise.all(sourcePayloads.map((payload) => createResearchSourceRecord(payload)))

      // ADD THIS NEW BLOCK: Trigger the asynchronous AI research pipeline
      await runResearch({
        prompt: researchData.prompt,
        research_id: createdResearch.id,
        workspace_id: researchData.workspaceId,
      })

      navigate(`/researches/${createdResearch.id}`, {
        state: {
          ...researchData,
          id: createdResearch.id,
        },
      })
    } catch (error) {
      console.error('Failed to start research', error)
      toast.error(error instanceof Error ? error.message : 'Failed to start research')
    } finally {
      setIsStartingResearch(false)
    }
  }

  return (
    <div className="flex flex-col h-full w-full bg-background overflow-hidden animate-in fade-in duration-500">

      {/* Header */}
      <div className="shrink-0 border-b border-border/50 bg-background/50 backdrop-blur-sm sticky top-0 z-30">
        <div className="w-full max-w-5xl mx-auto px-6 py-6">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-2xl bg-linear-to-br from-primary/20 via-primary/10 to-transparent border border-primary/20 flex items-center justify-center">
              <Sparkles className="size-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Start New Research</h1>
              <p className="text-muted-foreground">Configure your deep dive analysis parameters</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Form Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="w-full max-w-5xl mx-auto px-6 py-8 space-y-8 pb-32">

          {/* Step 1: Research Details */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-primary font-semibold">
              <span className="flex items-center justify-center size-6 rounded-full bg-primary/20 text-xs">1</span>
              <h3>Research Details</h3>
            </div>
            <Card className="border-border/50 shadow-sm">
              <CardContent className="pt-6 space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Research Title</label>
                  <Input
                    placeholder="e.g., impact of AI on specialized software markets"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="bg-muted/30"
                  />
                  <p className="text-xs text-muted-foreground">Leave blank to auto-generate based on your first query.</p>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Description (Optional)</label>
                  <Textarea
                    placeholder="Describe the goal of this research..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="bg-muted/30 min-h-25 resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-sm font-medium">Research Prompt</label>
                    <span className={cn("text-xs font-mono", prompt.length > 5000 ? "text-red-500" : "text-muted-foreground")}>
                      {prompt.length}/5000
                    </span>
                  </div>
                  <div className="relative rounded-xl border border-border/50 bg-muted/30 focus-within:ring-2 focus-within:ring-primary/20 transition-all overflow-hidden">
                    <PromptEditor
                      value={prompt}
                      onChange={(val) => {
                        if (val.length <= 5000) setPrompt(val)
                      }}
                      placeholder="Enter detailed instruction for the AI researcher..."
                      className="min-h-50 border-none bg-transparent focus:ring-0"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">Provide specific questions, context, or formatting requirements.</p>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* Step 2: Add Sources (Moved here) */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-primary font-semibold">
              <span className="flex items-center justify-center size-6 rounded-full bg-primary/20 text-xs">2</span>
              <h3>Add Sources (Optional)</h3>
            </div>
            <Card className="border-border/50 shadow-sm">
              <CardContent className="pt-6 space-y-6">

                {/* Add URL Input */}
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                    <Input
                      placeholder="Paste website URL or YouTube link..."
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="pl-9 bg-muted/30"
                      onKeyDown={(e) => e.key === 'Enter' && handleAddSource()}
                    />
                  </div>
                  <Button onClick={handleAddSource} variant="secondary" disabled={!newUrl}>
                    <Plus className="size-4 mr-2" />
                    Add
                  </Button>
                </div>

                {/* File Upload Placeholder */}
                <div
                  onClick={() => openFilePicker()}
                  className="border-2 border-dashed border-border/60 rounded-xl p-6 flex flex-col items-center justify-center text-center gap-2 hover:bg-muted/20 transition-colors cursor-pointer group"
                >
                  <div className="size-10 rounded-full bg-muted flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Upload className="size-5 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">Upload Documents</p>
                    <p className="text-xs text-muted-foreground mt-1">Support for PDF, DOCX (Max 10MB)</p>
                  </div>
                </div>

                {/* Sources List */}
                {sources.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {sources.map((source, idx) => (
                      <div key={idx} className="flex items-center gap-3 p-3 rounded-lg bg-muted/40 border border-border/50 group">
                        <div className="shrink-0 p-2 rounded-md bg-background border">
                          {source.type === 'youtube' ? (
                            <Youtube className="size-4 text-red-500" />
                          ) : source.type === 'file' ? (
                            <FileText className="size-4 text-orange-500" />
                          ) : (
                            <LinkIcon className="size-4 text-blue-500" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{source.value}</p>
                          <p className="text-xs text-muted-foreground capitalize">{source.type}</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => removeSource(idx)}
                        >
                          <X className="size-4 text-muted-foreground hover:text-destructive" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </section>

          {/* Step 3: Workspace Selection (Moved here) */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-primary font-semibold">
              <span className="flex items-center justify-center size-6 rounded-full bg-primary/20 text-xs">3</span>
              <h3>Select Workspace <span className="text-red-500">*</span></h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {workspaces.map((ws) => {
                const isSelected = selectedWorkspace === ws.id
                return (
                  <div
                    key={ws.id}
                    onClick={() => setSelectedWorkspace(ws.id)}
                    className={cn(
                      "cursor-pointer rounded-xl border p-4 transition-all duration-200 relative overflow-hidden group hover:border-primary/50",
                      isSelected
                        ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                        : "border-border/50 bg-card hover:bg-muted/20"
                    )}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className={cn("p-2 rounded-lg", ws.bgColor)}>
                        <ws.icon className={cn("size-5", ws.color)} />
                      </div>
                      {isSelected && (
                        <div className="size-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                          <Sparkles className="size-3" />
                        </div>
                      )}
                    </div>
                    <h4 className="font-semibold text-foreground/90">{ws.title}</h4>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{ws.description}</p>
                  </div>
                )
              })}

              {!isLoadingWorkspaces && workspaces.length === 0 && (
                <div className="rounded-xl border border-dashed border-border/60 p-4 col-span-full text-center">
                  <p className="text-sm text-muted-foreground">No workspaces available. Create one first.</p>
                </div>
              )}

              {isLoadingWorkspaces && (
                <div className="rounded-xl border border-dashed border-border/60 p-4 col-span-full text-center">
                  <p className="text-sm text-muted-foreground">Loading workspaces...</p>
                </div>
              )}

              {/* Create New Workspace Placeholder */}
              <div className="rounded-xl border border-dashed border-border/60 p-4 transition-all hover:border-primary/50 hover:bg-muted/50 cursor-pointer flex flex-col items-center justify-center text-center gap-2 min-h-35">
                <div className="size-10 rounded-full bg-muted flex items-center justify-center">
                  <Plus className="size-5 text-muted-foreground" />
                </div>
                <p className="text-sm font-medium text-muted-foreground">Create New Workspace</p>
              </div>
            </div>
            {!selectedWorkspace && (
              <p className="text-xs text-red-400 font-medium px-1">Please select a workspace to continue.</p>
            )}
          </section>

          {/* Step 4: Preferences (Moved here) */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-primary font-semibold">
              <span className="flex items-center justify-center size-6 rounded-full bg-primary/20 text-xs">4</span>
              <h3>Preferences</h3>
            </div>
            <Card className="border-border/50 shadow-sm">
              <CardContent className="pt-6 grid gap-6">

                {/* Enable Chat */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <label className="text-sm font-medium flex items-center gap-2">
                      <MessageSquare className="size-4 text-primary" />
                      Enable Chat
                    </label>
                    <p className="text-xs text-muted-foreground">Allow casual conversation alongside research.</p>
                  </div>
                  <Switch checked={enableChat} onCheckedChange={setEnableChat} />
                </div>

                <Separator />

                {/* Background Research */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <label className="text-sm font-medium flex items-center gap-2">
                      <Zap className="size-4 text-primary" />
                      Allow Backend Research
                    </label>
                    <p className="text-xs text-muted-foreground">Continue research even if app is closed or page is switched.</p>
                  </div>
                  <Switch checked={allowBackendResearch} onCheckedChange={setAllowBackendResearch} />
                </div>

                <Separator />

                {/* Research Template */}
                <div className="flex items-center justify-between gap-4">
                  <div className="space-y-0.5">
                    <label className="text-sm font-medium flex items-center gap-2">
                      <Library className="size-4 text-primary" />
                      Research Template
                    </label>
                    <p className="text-xs text-muted-foreground">Select a preset to guide the AI's research methodology.</p>
                  </div>
                  <ResearchTemplateSelector
                    value={template}
                    onChange={setTemplate}
                    className="w-fit"
                  />
                </div>

                <Separator />

                {/* Custom Instructions */}
                <div className="space-y-3">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <Settings2 className="size-4 text-primary" />
                    Custom Instructions
                  </label>
                  <Textarea
                    placeholder="e.g., Focus specifically on data from last 2 years, minimize technical jargon..."
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    className="bg-muted/30 min-h-20 resize-none"
                  />
                </div>

              </CardContent>
            </Card>
          </section>

        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-border/50 bg-background/80 backdrop-blur-sm p-4 z-30">
        <div className="max-w-5xl mx-auto flex items-center justify-end gap-3">
          <Button variant="ghost" onClick={() => navigate(-1)}>
            Cancel
          </Button>
          <Button
            onClick={handleStartResearch}
            disabled={!selectedWorkspace || isStartingResearch}
            className="px-8 shadow-lg shadow-primary/20"
          >
            {isStartingResearch ? 'Starting...' : 'Start Research'}
            <ArrowRight className="size-4 ml-2" />
          </Button>
        </div>
      </div>
    </div>
  )
}