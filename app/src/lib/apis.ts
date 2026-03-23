import axios, { AxiosError, type AxiosResponse } from "axios";

const backendUrl =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ??
  "http://localhost:8000";

export const resolveApiUrl = (path?: string | null): string | null => {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  const normalizedBase = backendUrl.endsWith("/")
    ? backendUrl.slice(0, -1)
    : backendUrl;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
};

const api = axios.create({
  baseURL: backendUrl,
});

type QueryPrimitive =
  | string
  | number
  | boolean
  | null
  | undefined
  | Date;
type QueryValue = QueryPrimitive | QueryPrimitive[];
type QueryParams = Record<string, QueryValue>;

const withQuery = (path: string, params?: QueryParams): string => {
  if (!params) return path;

  const searchParams = new URLSearchParams();

  for (const [key, rawValue] of Object.entries(params)) {
    if (rawValue === undefined || rawValue === null) {
      continue;
    }

    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    for (const value of values) {
      if (value === undefined || value === null) continue;
      const normalized =
        value instanceof Date ? value.toISOString() : String(value);
      searchParams.append(key, normalized);
    }
  }

  const query = searchParams.toString();
  return query ? `${path}?${query}` : path;
};

const extractErrorMessage = (error: AxiosError<unknown>): string => {
  const data = error.response?.data;

  if (typeof data === "string" && data.trim().length > 0) {
    return data;
  }

  if (data && typeof data === "object") {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }

    const message = (data as { message?: unknown }).message;
    if (typeof message === "string" && message.trim().length > 0) {
      return message;
    }
  }

  return error.message;
};

async function requestData<T>(promise: Promise<AxiosResponse<T>>): Promise<T> {
  try {
    const response = await promise;
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(extractErrorMessage(error));
    }
    throw error;
  }
}

async function requestVoid(
  promise: Promise<AxiosResponse<unknown>>,
): Promise<void> {
  await requestData(promise);
}

export type SortOrder = "asc" | "desc";

export interface PaginationResponse<T> {
  items: T[];
  page: number;
  size: number;
  total_items: number;
  total_pages: number;
  offset: number;
}

export interface HealthResponse {
  status: "ok";
}

export const getHealth = async (): Promise<HealthResponse> => {
  return requestData(api.get<HealthResponse>("/health"));
};

// Workspace API
export type WorkspaceAiConfig = "auto" | "local" | "online";
export type WorkspaceSortBy = "updated_at" | "created_at" | "name";

export interface WorkspaceRecord {
  id: string;
  name: string;
  desc: string;
  icon: string | null;
  accent_clr: string | null;
  banner_img: string | null;
  connected_bucket_id: string | null;
  ai_config: WorkspaceAiConfig;
  workspace_resources_id: string | null;
  workspace_research_agents: boolean;
  workspace_chat_agents: boolean;
  created_at: string;
  updated_at: string;
  resource_count: number;
}

export interface WorkspaceCreateRequest {
  name: string;
  desc: string;
  icon?: string | null;
  accent_clr?: string | null;
  banner_img?: string | null;
  connected_bucket_id?: string | null;
  ai_config?: WorkspaceAiConfig;
  workspace_research_agents?: boolean;
  workspace_chat_agents?: boolean;
}

export interface WorkspaceCreateWithAssetsRequest {
  name: string;
  desc: string;
  icon?: string | null;
  accent_clr?: string | null;
  banner_img?: string | null;
  connected_bucket_id?: string | null;
  ai_config?: WorkspaceAiConfig;
  workspace_resources_id?: string | null;
  workspace_research_agents?: boolean;
  workspace_chat_agents?: boolean;
  banner_file?: File | null;
  icon_file?: File | null;
  resource_files?: File[];
  resource_created_by?: string;
  resource_source?: string;
  resource_summary?: string;
}

export type WorkspacePatchRequest = Partial<WorkspaceCreateRequest>;

export interface WorkspaceListQuery {
  page?: number;
  size?: number;
  nameContains?: string;
  descContains?: string;
  aiConfig?: WorkspaceAiConfig;
  connectedBucketId?: string;
  sortBy?: WorkspaceSortBy;
  sortOrder?: SortOrder;
}

export type WorkspaceListResponse = PaginationResponse<WorkspaceRecord>;

export const listWorkspaceRecords = async (
  query?: WorkspaceListQuery,
): Promise<WorkspaceListResponse> => {
  return requestData(
    api.get<WorkspaceListResponse>(
      withQuery("/workspace/", {
        page: query?.page,
        size: query?.size,
        nameContains: query?.nameContains,
        descContains: query?.descContains,
        aiConfig: query?.aiConfig,
        connectedBucketId: query?.connectedBucketId,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getWorkspaceRecord = async (
  workspaceId: string,
): Promise<WorkspaceRecord> => {
  return requestData(
    api.get<WorkspaceRecord>(`/workspace/${encodeURIComponent(workspaceId)}`),
  );
};

export const createWorkspaceRecord = async (
  payload: WorkspaceCreateRequest,
): Promise<WorkspaceRecord> => {
  return requestData(api.post<WorkspaceRecord>("/workspace/", payload));
};

export const createWorkspaceRecordWithAssets = async (
  payload: WorkspaceCreateWithAssetsRequest,
): Promise<WorkspaceRecord> => {
  const formData = new FormData();

  formData.append("name", payload.name);
  formData.append("desc", payload.desc);

  if (payload.icon !== undefined && payload.icon !== null) {
    formData.append("icon", payload.icon);
  }
  if (payload.accent_clr !== undefined && payload.accent_clr !== null) {
    formData.append("accent_clr", payload.accent_clr);
  }
  if (payload.banner_img !== undefined && payload.banner_img !== null) {
    formData.append("banner_img", payload.banner_img);
  }
  if (
    payload.connected_bucket_id !== undefined &&
    payload.connected_bucket_id !== null
  ) {
    formData.append("connected_bucket_id", payload.connected_bucket_id);
  }
  if (
    payload.workspace_resources_id !== undefined &&
    payload.workspace_resources_id !== null
  ) {
    formData.append("workspace_resources_id", payload.workspace_resources_id);
  }
  if (payload.ai_config !== undefined) {
    formData.append("ai_config", payload.ai_config);
  }
  if (payload.workspace_research_agents !== undefined) {
    formData.append(
      "workspace_research_agents",
      String(payload.workspace_research_agents),
    );
  }
  if (payload.workspace_chat_agents !== undefined) {
    formData.append(
      "workspace_chat_agents",
      String(payload.workspace_chat_agents),
    );
  }
  if (payload.banner_file) {
    formData.append("banner_file", payload.banner_file, payload.banner_file.name);
  }
  if (payload.icon_file) {
    formData.append("icon_file", payload.icon_file, payload.icon_file.name);
  }
  if (payload.resource_files && payload.resource_files.length > 0) {
    for (const file of payload.resource_files) {
      formData.append("resource_files", file, file.name);
    }
  }
  if (payload.resource_created_by) {
    formData.append("resource_created_by", payload.resource_created_by);
  }
  if (payload.resource_source) {
    formData.append("resource_source", payload.resource_source);
  }
  if (payload.resource_summary) {
    formData.append("resource_summary", payload.resource_summary);
  }

  return requestData(api.post<WorkspaceRecord>("/workspace/create-with-assets", formData));
};

export const replaceWorkspaceRecord = async (
  workspaceId: string,
  payload: WorkspaceCreateRequest,
): Promise<WorkspaceRecord> => {
  return requestData(
    api.put<WorkspaceRecord>(`/workspace/${encodeURIComponent(workspaceId)}`, payload),
  );
};

export const patchWorkspaceRecord = async (
  workspaceId: string,
  payload: WorkspacePatchRequest,
): Promise<WorkspaceRecord> => {
  return requestData(
    api.patch<WorkspaceRecord>(
      `/workspace/${encodeURIComponent(workspaceId)}`,
      payload,
    ),
  );
};

export const uploadWorkspaceBannerRecord = async (
  workspaceId: string,
  file: File,
): Promise<WorkspaceRecord> => {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return requestData(
    api.post<WorkspaceRecord>(
      `/workspace/${encodeURIComponent(workspaceId)}/upload/banner`,
      formData,
    ),
  );
};

export const uploadWorkspaceIconRecord = async (
  workspaceId: string,
  file: File,
): Promise<WorkspaceRecord> => {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return requestData(
    api.post<WorkspaceRecord>(
      `/workspace/${encodeURIComponent(workspaceId)}/upload/icon`,
      formData,
    ),
  );
};

// Workspace Resource Upload APIs
export interface WorkspaceResourceUploadQuery {
  createdBy: string;
  source?: string;
  summary?: string;
}

export const uploadWorkspaceResource = async (
  workspaceId: string,
  file: File,
  query: WorkspaceResourceUploadQuery,
): Promise<BucketItemRecord> => {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return requestData(
    api.post<BucketItemRecord>(
      withQuery(`/workspace/${encodeURIComponent(workspaceId)}/resources/upload`, {
        created_by: query.createdBy,
        source: query.source,
        summary: query.summary,
      }),
      formData,
    ),
  );
};

export const uploadWorkspaceResourcesBulk = async (
  workspaceId: string,
  files: File[],
  query: WorkspaceResourceUploadQuery,
): Promise<BucketItemRecord[]> => {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
  }
  return requestData(
    api.post<BucketItemRecord[]>(
      withQuery(`/workspace/${encodeURIComponent(workspaceId)}/resources/upload/bulk`, {
        created_by: query.createdBy,
        source: query.source,
        summary: query.summary,
      }),
      formData,
    ),
  );
};

export const deleteWorkspaceRecord = async (workspaceId: string): Promise<void> => {
  await requestVoid(api.delete(`/workspace/${encodeURIComponent(workspaceId)}`));
};

// Research API
export type ResearchSortBy = "id" | "title" | "workspace_id";

export interface ResearchRecord {
  id: string;
  title: string | null;
  desc: string | null;
  prompt: string | null;
  sources: string | null;
  workspace_id: string | null;
  artifacts: string | null;
  chat_access: boolean;
  background_processing: boolean;
  research_template_id: string | null;
  custom_instructions: string | null;
  prompt_order: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ResearchCreateRequest {
  title?: string | null;
  desc?: string | null;
  prompt?: string | null;
  sources?: string | null;
  workspace_id?: string | null;
  artifacts?: string | null;
  chat_access?: boolean;
  background_processing?: boolean;
  research_template_id?: string | null;
  custom_instructions?: string | null;
  prompt_order?: string | null;
}

export type ResearchPatchRequest = Partial<ResearchCreateRequest>;

export interface ResearchListQuery {
  page?: number;
  size?: number;
  workspaceId?: string;
  titleContains?: string;
  descContains?: string;
  promptContains?: string;
  chatAccess?: boolean;
  backgroundProcessing?: boolean;
  sortBy?: ResearchSortBy;
  sortOrder?: SortOrder;
}

export type ResearchListResponse = PaginationResponse<ResearchRecord>;

export const listResearchRecords = async (
  query?: ResearchListQuery,
): Promise<ResearchListResponse> => {
  return requestData(
    api.get<ResearchListResponse>(
      withQuery("/research/", {
        page: query?.page,
        size: query?.size,
        workspaceId: query?.workspaceId,
        titleContains: query?.titleContains,
        descContains: query?.descContains,
        promptContains: query?.promptContains,
        chatAccess: query?.chatAccess,
        backgroundProcessing: query?.backgroundProcessing,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getResearchRecord = async (
  researchId: string,
): Promise<ResearchRecord> => {
  return requestData(
    api.get<ResearchRecord>(`/research/${encodeURIComponent(researchId)}`),
  );
};

export const createResearchRecord = async (
  payload: ResearchCreateRequest,
): Promise<ResearchRecord> => {
  return requestData(api.post<ResearchRecord>("/research/", payload));
};

export const replaceResearchRecord = async (
  researchId: string,
  payload: ResearchCreateRequest,
): Promise<ResearchRecord> => {
  return requestData(
    api.put<ResearchRecord>(`/research/${encodeURIComponent(researchId)}`, payload),
  );
};

export const patchResearchRecord = async (
  researchId: string,
  payload: ResearchPatchRequest,
): Promise<ResearchRecord> => {
  return requestData(
    api.patch<ResearchRecord>(`/research/${encodeURIComponent(researchId)}`, payload),
  );
};

export const deleteResearchRecord = async (researchId: string): Promise<void> => {
  await requestVoid(api.delete(`/research/${encodeURIComponent(researchId)}`));
};

export interface ResearchRunRequest {
  prompt: string;
  context?: string | null;
  research_id?: string | null;
  workspace_id?: string | null;
  api_key?: string | null;
}

export const runResearch = async (
  payload: ResearchRunRequest,
): Promise<{ job_id: string; status: string }> => {
  return requestData(api.post<{ job_id: string; status: string }>("/research/run", payload));
};

// Research Sources API
export interface ResearchSourceRecord {
  id: string;
  research_id: string;
  source_url: string;
  source_type: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchSourceCreateRequest {
  research_id: string;
  source_url: string;
  source_type: string;
}

export type ResearchSourcePatchRequest = Partial<ResearchSourceCreateRequest>;

export interface ResearchSourceListQuery {
  page?: number;
  size?: number;
  researchId?: string;
  createdFrom?: string | Date;
  createdTo?: string | Date;
  updatedFrom?: string | Date;
  updatedTo?: string | Date;
  sourceType?: string;
  urlContains?: string;
  sortBy?: "created_at" | "updated_at" | "research_id" | "source_type" | "source_url";
  sortOrder?: SortOrder;
}

export type ResearchSourceListResponse = PaginationResponse<ResearchSourceRecord>;

export const listResearchSourceRecords = async (
  query?: ResearchSourceListQuery,
): Promise<ResearchSourceListResponse> => {
  return requestData(
    api.get<ResearchSourceListResponse>(
      withQuery("/research/urls", {
        page: query?.page,
        size: query?.size,
        researchId: query?.researchId,
        createdFrom: query?.createdFrom,
        createdTo: query?.createdTo,
        updatedFrom: query?.updatedFrom,
        updatedTo: query?.updatedTo,
        sourceType: query?.sourceType,
        urlContains: query?.urlContains,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getResearchSourceRecord = async (
  sourceId: string,
): Promise<ResearchSourceRecord> => {
  return requestData(
    api.get<ResearchSourceRecord>(`/research/sources/${encodeURIComponent(sourceId)}`),
  );
};

export const createResearchSourceRecord = async (
  payload: ResearchSourceCreateRequest,
): Promise<ResearchSourceRecord> => {
  return requestData(api.post<ResearchSourceRecord>("/research/sources", payload));
};

export const patchResearchSourceRecord = async (
  sourceId: string,
  payload: ResearchSourcePatchRequest,
): Promise<ResearchSourceRecord> => {
  return requestData(
    api.patch<ResearchSourceRecord>(
      `/research/sources/${encodeURIComponent(sourceId)}`,
      payload,
    ),
  );
};

export const deleteResearchSourceRecord = async (sourceId: string): Promise<void> => {
  await requestVoid(api.delete(`/research/sources/${encodeURIComponent(sourceId)}`));
};

// History API
export type HistoryType =
  | "usage"
  | "research"
  | "chat"
  | "version"
  | "token"
  | "ai_summary"
  | "bucket"
  | "search"
  | "export"
  | "download"
  | "upload"
  | "generation";

export interface HistoryItemRecord {
  id: string;
  user_id: string | null;
  workspace_id: string | null;
  activity: string | null;
  type: HistoryType | null;
  created_at: string;
  last_seen: string | null;
  actions: string | null;
  url: string | null;
}

export interface HistoryCreateRequest {
  user_id?: string | null;
  workspace_id?: string | null;
  activity?: string | null;
  type?: HistoryType | null;
  last_seen?: string | null;
  actions?: string | null;
  url?: string | null;
}

export type HistoryPatchRequest = Partial<HistoryCreateRequest>;

export interface HistoryListQuery {
  page?: number;
  size?: number;
  itemType?: HistoryType;
  workspaceId?: string;
  userId?: string;
  include_deleted?: boolean;
  activityContains?: string;
  urlContains?: string;
  createdFrom?: string | Date;
  createdTo?: string | Date;
  lastSeenFrom?: string | Date;
  lastSeenTo?: string | Date;
  sortBy?: "last_seen" | "created_at" | "activity" | "type";
  sortOrder?: SortOrder;
}

export interface HistoryListResponse {
  history_items: HistoryItemRecord[];
  page: number;
  total_pages: number;
  offset: number;
}

export const listHistoryItems = async (
  query?: HistoryListQuery,
): Promise<HistoryListResponse> => {
  return requestData(
    api.get<HistoryListResponse>(
      withQuery("/history/", {
        page: query?.page,
        size: query?.size,
        itemType: query?.itemType,
        workspaceId: query?.workspaceId,
        userId: query?.userId,
        include_deleted: query?.include_deleted,
        activityContains: query?.activityContains,
        urlContains: query?.urlContains,
        createdFrom: query?.createdFrom,
        createdTo: query?.createdTo,
        lastSeenFrom: query?.lastSeenFrom,
        lastSeenTo: query?.lastSeenTo,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getHistoryItem = async (historyId: string): Promise<HistoryItemRecord> => {
  return requestData(
    api.get<HistoryItemRecord>(`/history/${encodeURIComponent(historyId)}`),
  );
};

export const createHistoryItem = async (
  payload: HistoryCreateRequest,
): Promise<HistoryItemRecord> => {
  return requestData(api.post<HistoryItemRecord>("/history/", payload));
};

export const replaceHistoryItem = async (
  historyId: string,
  payload: HistoryCreateRequest,
): Promise<HistoryItemRecord> => {
  return requestData(
    api.put<HistoryItemRecord>(`/history/${encodeURIComponent(historyId)}`, payload),
  );
};

export const patchHistoryItem = async (
  historyId: string,
  payload: HistoryPatchRequest,
): Promise<HistoryItemRecord> => {
  return requestData(
    api.patch<HistoryItemRecord>(`/history/${encodeURIComponent(historyId)}`, payload),
  );
};

export const deleteHistoryItem = async (historyId: string): Promise<void> => {
  await requestVoid(api.delete(`/history/${encodeURIComponent(historyId)}`));
};

export const executeHistoryAction = async (
  historyId: string,
  action: "delete" = "delete",
): Promise<HistoryItemRecord> => {
  return requestData(
    api.post<HistoryItemRecord>(
      withQuery(`/history/${encodeURIComponent(historyId)}/action`, { action }),
    ),
  );
};

// Chats API: Threads
export interface ChatThreadRecord {
  thread_id: string;
  thread_title: string | null;
  workspace_id: string | null;
  user_id: string | null;
  metadata: string | null;
  token_count: number | null;
  is_pinned: boolean | null;
  pinned_at: string | null;
  pinned_order: number | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatThreadCreateRequest {
  thread_title?: string | null;
  workspace_id?: string | null;
  user_id?: string | null;
  metadata?: string | null;
  token_count?: number | null;
  is_pinned?: boolean | null;
  pinned_at?: string | null;
  pinned_order?: number | null;
  created_by?: string | null;
}

export type ChatThreadPatchRequest = Partial<ChatThreadCreateRequest>;

export interface ChatThreadListQuery {
  page?: number;
  size?: number;
  workspaceId?: string;
  userId?: string;
  createdBy?: string;
  isPinned?: boolean;
  threadTitleContains?: string;
  sortBy?: "updated_at" | "created_at" | "thread_title" | "pinned_order";
  sortOrder?: SortOrder;
}

export type ChatThreadListResponse = PaginationResponse<ChatThreadRecord>;

export const listChatThreads = async (
  query?: ChatThreadListQuery,
): Promise<ChatThreadListResponse> => {
  return requestData(
    api.get<ChatThreadListResponse>(
      withQuery("/chats/threads", {
        page: query?.page,
        size: query?.size,
        workspaceId: query?.workspaceId,
        userId: query?.userId,
        createdBy: query?.createdBy,
        isPinned: query?.isPinned,
        threadTitleContains: query?.threadTitleContains,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getChatThread = async (threadId: string): Promise<ChatThreadRecord> => {
  return requestData(
    api.get<ChatThreadRecord>(`/chats/threads/${encodeURIComponent(threadId)}`),
  );
};

export const createChatThread = async (
  payload: ChatThreadCreateRequest,
): Promise<ChatThreadRecord> => {
  return requestData(api.post<ChatThreadRecord>("/chats/threads", payload));
};

export const replaceChatThread = async (
  threadId: string,
  payload: ChatThreadCreateRequest,
): Promise<ChatThreadRecord> => {
  return requestData(
    api.put<ChatThreadRecord>(`/chats/threads/${encodeURIComponent(threadId)}`, payload),
  );
};

export const patchChatThread = async (
  threadId: string,
  payload: ChatThreadPatchRequest,
): Promise<ChatThreadRecord> => {
  return requestData(
    api.patch<ChatThreadRecord>(`/chats/threads/${encodeURIComponent(threadId)}`, payload),
  );
};

export const deleteChatThread = async (threadId: string): Promise<void> => {
  await requestVoid(api.delete(`/chats/threads/${encodeURIComponent(threadId)}`));
};

// Chats API: Messages
export interface ChatMessageRecord {
  message_id: string;
  thread_id: string | null;
  message_seq: number | null;
  parent_id: string | null;
  role: string | null;
  content: string | null;
  citations: string | null;
  token_count: number | null;
  attachments: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageCreateRequest {
  thread_id?: string | null;
  message_seq?: number | null;
  parent_id?: string | null;
  role?: string | null;
  content?: string | null;
  citations?: string | null;
  token_count?: number | null;
  attachments?: string | null;
}

export type ChatMessagePatchRequest = Partial<ChatMessageCreateRequest>;

export interface ChatMessageListQuery {
  page?: number;
  size?: number;
  threadId?: string;
  role?: string;
  parentId?: string;
  contentContains?: string;
  createdFrom?: string | Date;
  createdTo?: string | Date;
  sortBy?: "message_seq" | "created_at" | "updated_at";
  sortOrder?: SortOrder;
}

export type ChatMessageListResponse = PaginationResponse<ChatMessageRecord>;

export const listChatMessages = async (
  query?: ChatMessageListQuery,
): Promise<ChatMessageListResponse> => {
  return requestData(
    api.get<ChatMessageListResponse>(
      withQuery("/chats/messages", {
        page: query?.page,
        size: query?.size,
        threadId: query?.threadId,
        role: query?.role,
        parentId: query?.parentId,
        contentContains: query?.contentContains,
        createdFrom: query?.createdFrom,
        createdTo: query?.createdTo,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getChatMessage = async (
  messageId: string,
): Promise<ChatMessageRecord> => {
  return requestData(
    api.get<ChatMessageRecord>(`/chats/messages/${encodeURIComponent(messageId)}`),
  );
};

export const createChatMessage = async (
  payload: ChatMessageCreateRequest,
): Promise<ChatMessageRecord> => {
  return requestData(api.post<ChatMessageRecord>("/chats/messages", payload));
};

export const patchChatMessage = async (
  messageId: string,
  payload: ChatMessagePatchRequest,
): Promise<ChatMessageRecord> => {
  return requestData(
    api.patch<ChatMessageRecord>(`/chats/messages/${encodeURIComponent(messageId)}`, payload),
  );
};

export const deleteChatMessage = async (messageId: string): Promise<void> => {
  await requestVoid(api.delete(`/chats/messages/${encodeURIComponent(messageId)}`));
};

// Chats API: Attachments
export interface ChatAttachmentRecord {
  attachment_id: string;
  message_id: string | null;
  attachment_type: string | null;
  attachment_path: string | null;
  attachment_size: number | null;
  created_at: string;
  updated_at: string;
}

export interface ChatAttachmentCreateRequest {
  message_id?: string | null;
  attachment_type?: string | null;
  attachment_path?: string | null;
  attachment_size?: number | null;
}

export type ChatAttachmentPatchRequest = Partial<ChatAttachmentCreateRequest>;

export interface ChatAttachmentListQuery {
  page?: number;
  size?: number;
  messageId?: string;
  attachmentType?: string;
  minAttachmentSize?: number;
  maxAttachmentSize?: number;
  pathContains?: string;
  sortBy?: "created_at" | "updated_at" | "attachment_size";
  sortOrder?: SortOrder;
}

export type ChatAttachmentListResponse = PaginationResponse<ChatAttachmentRecord>;

export const listChatAttachments = async (
  query?: ChatAttachmentListQuery,
): Promise<ChatAttachmentListResponse> => {
  return requestData(
    api.get<ChatAttachmentListResponse>(
      withQuery("/chats/attachments", {
        page: query?.page,
        size: query?.size,
        messageId: query?.messageId,
        attachmentType: query?.attachmentType,
        minAttachmentSize: query?.minAttachmentSize,
        maxAttachmentSize: query?.maxAttachmentSize,
        pathContains: query?.pathContains,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getChatAttachment = async (
  attachmentId: string,
): Promise<ChatAttachmentRecord> => {
  return requestData(
    api.get<ChatAttachmentRecord>(
      `/chats/attachments/${encodeURIComponent(attachmentId)}`,
    ),
  );
};

export const createChatAttachment = async (
  payload: ChatAttachmentCreateRequest,
): Promise<ChatAttachmentRecord> => {
  return requestData(
    api.post<ChatAttachmentRecord>("/chats/attachments", payload),
  );
};

export const patchChatAttachment = async (
  attachmentId: string,
  payload: ChatAttachmentPatchRequest,
): Promise<ChatAttachmentRecord> => {
  return requestData(
    api.patch<ChatAttachmentRecord>(
      `/chats/attachments/${encodeURIComponent(attachmentId)}`,
      payload,
    ),
  );
};

export const deleteChatAttachment = async (attachmentId: string): Promise<void> => {
  await requestVoid(api.delete(`/chats/attachments/${encodeURIComponent(attachmentId)}`));
};

// Bucket API
export type BucketSortBy =
  | "updated_at"
  | "created_at"
  | "name"
  | "total_files"
  | "total_size";

export interface BucketRecord {
  id: string;
  name: string;
  allowed_file_types: string;
  description: string | null;
  deletable: boolean;
  status: boolean;
  total_files: number;
  total_size: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface BucketCreateRequest {
  name: string;
  allowed_file_types: string;
  description?: string | null;
  deletable?: boolean;
  status?: boolean;
  created_by: string;
}

export type BucketPatchRequest = Partial<BucketCreateRequest>;

export interface BucketListQuery {
  page?: number;
  size?: number;
  createdBy?: string;
  nameContains?: string;
  status?: boolean;
  deletable?: boolean;
  minTotalFiles?: number;
  maxTotalFiles?: number;
  minTotalSize?: number;
  maxTotalSize?: number;
  sortBy?: BucketSortBy;
  sortOrder?: SortOrder;
}

export type BucketListResponse = PaginationResponse<BucketRecord>;

export const listBuckets = async (
  query?: BucketListQuery,
): Promise<BucketListResponse> => {
  return requestData(
    api.get<BucketListResponse>(
      withQuery("/bucket/", {
        page: query?.page,
        size: query?.size,
        createdBy: query?.createdBy,
        nameContains: query?.nameContains,
        status: query?.status,
        deletable: query?.deletable,
        minTotalFiles: query?.minTotalFiles,
        maxTotalFiles: query?.maxTotalFiles,
        minTotalSize: query?.minTotalSize,
        maxTotalSize: query?.maxTotalSize,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getBucket = async (bucketId: string): Promise<BucketRecord> => {
  return requestData(
    api.get<BucketRecord>(`/bucket/${encodeURIComponent(bucketId)}`),
  );
};

export const createBucket = async (
  payload: BucketCreateRequest,
): Promise<BucketRecord> => {
  return requestData(api.post<BucketRecord>("/bucket/", payload));
};

export const replaceBucket = async (
  bucketId: string,
  payload: BucketCreateRequest,
): Promise<BucketRecord> => {
  return requestData(
    api.put<BucketRecord>(`/bucket/${encodeURIComponent(bucketId)}`, payload),
  );
};

export const patchBucket = async (
  bucketId: string,
  payload: BucketPatchRequest,
): Promise<BucketRecord> => {
  return requestData(
    api.patch<BucketRecord>(`/bucket/${encodeURIComponent(bucketId)}`, payload),
  );
};

export const deleteBucket = async (bucketId: string): Promise<void> => {
  await requestVoid(api.delete(`/bucket/${encodeURIComponent(bucketId)}`));
};

export interface BucketUploadQuery {
  created_by?: string;
  createdBy?: string;
  source?: string;
  summary?: string;
  connectedWorkspaceIds?: string;
}

export interface BucketItemRecord {
  id: string;
  bucket_id: string;
  connected_workspace_ids: string | null;
  source: string | null;
  file_name: string;
  file_path: string;
  file_format: string;
  file_size: number;
  summary: string | null;
  is_deleted: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export const uploadBucketFile = async (
  bucketId: string,
  file: File,
  query: BucketUploadQuery,
): Promise<BucketItemRecord> => {
  const formData = new FormData();
  formData.append("file", file, file.name);

  return requestData(
    api.post<BucketItemRecord>(
      withQuery(`/bucket/${encodeURIComponent(bucketId)}/upload`, {
        created_by: query.createdBy || query.created_by,
        source: query.source,
        summary: query.summary,
        connectedWorkspaceIds: query.connectedWorkspaceIds,
      }),
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    ),
  );
};

export const uploadBucketFiles = async (
  bucketId: string,
  files: File[],
  query: BucketUploadQuery,
): Promise<BucketItemRecord[]> => {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
  }

  return requestData(
    api.post<BucketItemRecord[]>(
      withQuery(`/bucket/${encodeURIComponent(bucketId)}/upload/bulk`, {
        created_by: query.createdBy || query.created_by,
        source: query.source,
        summary: query.summary,
        connectedWorkspaceIds: query.connectedWorkspaceIds,
      }),
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    ),
  );
};

// Bucket Items API
export type BucketItemSortBy =
  | "updated_at"
  | "created_at"
  | "file_name"
  | "file_size";

export interface BucketItemCreateRequest {
  bucket_id: string;
  file_name: string;
  file_path: string;
  file_format: string;
  file_size: number;
  created_by: string;
  source?: string | null;
  summary?: string | null;
  connected_workspace_ids?: string | null;
  is_deleted?: boolean;
}

export type BucketItemPatchRequest = Partial<BucketItemCreateRequest>;

export interface BucketItemListQuery {
  page?: number;
  size?: number;
  bucketId?: string;
  fileFormat?: string;
  source?: string;
  createdBy?: string;
  isDeleted?: boolean;
  minFileSize?: number;
  maxFileSize?: number;
  fileNameContains?: string;
  filePathContains?: string;
  workspaceId?: string;
  sortBy?: BucketItemSortBy;
  sortOrder?: SortOrder;
}

export type BucketItemListResponse = PaginationResponse<BucketItemRecord>;

export const listBucketItems = async (
  query?: BucketItemListQuery,
): Promise<BucketItemListResponse> => {
  return requestData(
    api.get<BucketItemListResponse>(
      withQuery("/bucket/items", {
        page: query?.page,
        size: query?.size,
        bucketId: query?.bucketId,
        fileFormat: query?.fileFormat,
        source: query?.source,
        createdBy: query?.createdBy,
        isDeleted: query?.isDeleted,
        minFileSize: query?.minFileSize,
        maxFileSize: query?.maxFileSize,
        fileNameContains: query?.fileNameContains,
        filePathContains: query?.filePathContains,
        workspaceId: query?.workspaceId,
        sortBy: query?.sortBy,
        sortOrder: query?.sortOrder,
      }),
    ),
  );
};

export const getBucketItem = async (itemId: string): Promise<BucketItemRecord> => {
  return requestData(
    api.get<BucketItemRecord>(`/bucket/items/${encodeURIComponent(itemId)}`),
  );
};

export const createBucketItem = async (
  payload: BucketItemCreateRequest,
): Promise<BucketItemRecord> => {
  return requestData(api.post<BucketItemRecord>("/bucket/items", payload));
};

export const replaceBucketItem = async (
  itemId: string,
  payload: BucketItemCreateRequest,
): Promise<BucketItemRecord> => {
  return requestData(
    api.put<BucketItemRecord>(`/bucket/items/${encodeURIComponent(itemId)}`, payload),
  );
};

export const patchBucketItem = async (
  itemId: string,
  payload: BucketItemPatchRequest,
): Promise<BucketItemRecord> => {
  return requestData(
    api.patch<BucketItemRecord>(`/bucket/items/${encodeURIComponent(itemId)}`, payload),
  );
};

export const deleteBucketItem = async (itemId: string): Promise<void> => {
  await requestVoid(api.delete(`/bucket/items/${encodeURIComponent(itemId)}`));
};

// Settings API
export type ThemeMode = "system" | "light" | "dark";
export type ColorMode = "default" | "coffee" | "fresh" | "nerd" | "smooth";
export type DefaultReportFormat = "md" | "html" | "pdf" | "docx";
export type DefaultResearchTemplate =
  | "comprehensive"
  | "quick_summary"
  | "academic"
  | "market_analysis"
  | "technical_insights"
  | "comparative_study"
  | "vacation_planner";

export interface SettingsRecord {
  user_name: string | null;
  user_email: string | null;
  user_bio: string | null;
  theme: ThemeMode | null;
  color_mode: ColorMode | null;
  max_depth_search: number | null;
  default_report_fmt: DefaultReportFormat | null;
  default_research_template: DefaultResearchTemplate | null;
  default_bucket: string | null;
  notification_on_complete_research: boolean;
  show_error_on_alerts: boolean;
  sound_effect: boolean;
  default_model: string | null;
  ai_name: string | null;
  ai_personality: string | null;
  ai_custom_prompt: string | null;
  stream_response: boolean;
  show_citations: boolean;
  thinking_in_chats: boolean;
  keep_backup: boolean;
  temperory_data_retention: number | null;
}

export type SettingsPatchRequest = Partial<SettingsRecord>;

export const getSettings = async (): Promise<SettingsRecord> => {
  return requestData(api.get<SettingsRecord>("/settings/"));
};

export const createSettings = async (
  payload: SettingsPatchRequest,
): Promise<SettingsRecord> => {
  return requestData(api.post<SettingsRecord>("/settings/", payload));
};

export const replaceSettings = async (
  payload: SettingsRecord,
): Promise<SettingsRecord> => {
  return requestData(api.put<SettingsRecord>("/settings/", payload));
};

export const patchSettings = async (
  payload: SettingsPatchRequest,
): Promise<SettingsRecord> => {
  return requestData(api.patch<SettingsRecord>("/settings/", payload));
};

export const deleteSettings = async (): Promise<void> => {
  await requestVoid(api.delete("/settings/"));
};

// UI compatibility helpers for existing workspace pages
export interface WorkspaceCreate {
  name: string;
  description?: string;
  icon?: string | null;
  accentColor?: string | null;
  bannerUrl?: string | null;
  aiMode?: "auto" | "offline" | "local" | "online";
  enableResearch?: boolean;
  enableChat?: boolean;
  connectedBucketId?: string | null;
  bucket?: string | null;
}

export interface WorkspacePatch {
  name?: string;
  description?: string;
  icon?: string | null;
  accentColor?: string | null;
  bannerUrl?: string | null;
  aiMode?: "auto" | "offline" | "local" | "online";
  enableResearch?: boolean;
  enableChat?: boolean;
  connectedBucketId?: string | null;
}

export interface WorkspaceOut {
  id: string;
  name: string;
  description: string;
  icon?: string | null;
  accentColor?: string | null;
  aiMode: "auto" | "offline" | "online";
  enableResearch: boolean;
  enableChat: boolean;
  bannerUrl?: string | null;
  connectedBucketId?: string | null;
  createdAt?: string;
  updatedAt?: string;
  resourceCount: number;
}

export interface CreateWorkspacePayload extends WorkspaceCreate {
  bannerImage?: File | null;
  resources?: File[];
  customIcon?: File | null;
  bucket?: string | null;
}

const toWorkspaceAiConfig = (
  aiMode?: "auto" | "offline" | "local" | "online",
): WorkspaceAiConfig => {
  if (aiMode === "offline" || aiMode === "local") return "local";
  if (aiMode === "online") return "online";
  return "auto";
};

const fromWorkspaceAiConfig = (
  aiConfig: WorkspaceAiConfig,
): "auto" | "offline" | "online" => {
  if (aiConfig === "local") return "offline";
  return aiConfig;
};

const mapWorkspaceRecordToOut = (record: WorkspaceRecord): WorkspaceOut => {
  return {
    id: record.id,
    name: record.name,
    description: record.desc,
    icon: record.icon,
    accentColor: record.accent_clr,
    aiMode: fromWorkspaceAiConfig(record.ai_config),
    enableResearch: record.workspace_research_agents,
    enableChat: record.workspace_chat_agents,
    bannerUrl: record.banner_img,
    connectedBucketId: record.connected_bucket_id,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    resourceCount: record.resource_count ?? 0,
  };
};

export const getAllWorkspaces = async (query?: WorkspaceListQuery): Promise<{ workspaces: WorkspaceOut[]; totalItems: number; totalPages: number; page: number }> => {
  const response = await listWorkspaceRecords({
    page: query?.page ?? 1,
    size: query?.size ?? 200,
    sortBy: query?.sortBy ?? "updated_at",
    sortOrder: query?.sortOrder ?? "desc",
    nameContains: query?.nameContains,
    descContains: query?.descContains,
    aiConfig: query?.aiConfig,
    connectedBucketId: query?.connectedBucketId,
  });
  return {
    workspaces: response.items.map(mapWorkspaceRecordToOut),
    totalItems: response.total_items,
    totalPages: response.total_pages,
    page: response.page,
  };
};

export const getWorkspaceById = async (id: string): Promise<WorkspaceOut> => {
  const record = await getWorkspaceRecord(id);
  return mapWorkspaceRecordToOut(record);
};

export const createWorkspace = async (
  payload: CreateWorkspacePayload,
): Promise<WorkspaceOut> => {
  const description = payload.description?.trim() || `${payload.name} workspace`;
  const hasAssetFiles = Boolean(payload.bannerImage || payload.customIcon || (payload.resources && payload.resources.length > 0));
  const bucketId = payload.connectedBucketId ?? payload.bucket ?? null;
  const created = hasAssetFiles
    ? await createWorkspaceRecordWithAssets({
      name: payload.name,
      desc: description,
      icon: payload.icon ?? null,
      accent_clr: payload.accentColor ?? null,
      connected_bucket_id: bucketId,
      ai_config: toWorkspaceAiConfig(payload.aiMode),
      workspace_research_agents: payload.enableResearch ?? true,
      workspace_chat_agents: payload.enableChat ?? true,
      banner_file: payload.bannerImage ?? null,
      icon_file: payload.customIcon ?? null,
      resource_files: (payload.resources && payload.resources.length > 0 && bucketId)
        ? payload.resources
        : undefined,
      resource_created_by: "local-user",
    })
    : await createWorkspaceRecord({
      name: payload.name,
      desc: description,
      icon: payload.icon ?? null,
      accent_clr: payload.accentColor ?? null,
      connected_bucket_id: bucketId,
      ai_config: toWorkspaceAiConfig(payload.aiMode),
      workspace_research_agents: payload.enableResearch ?? true,
      workspace_chat_agents: payload.enableChat ?? true,
    });
  return mapWorkspaceRecordToOut(created);
};

export const updateWorkspace = async (
  id: string,
  payload: WorkspaceCreate,
): Promise<WorkspaceOut> => {
  const description = payload.description?.trim() || `${payload.name} workspace`;
  const updated = await replaceWorkspaceRecord(id, {
    name: payload.name,
    desc: description,
    icon: payload.icon ?? null,
    accent_clr: payload.accentColor ?? null,
    banner_img: payload.bannerUrl ?? null,
    connected_bucket_id: payload.connectedBucketId ?? payload.bucket ?? null,
    ai_config: toWorkspaceAiConfig(payload.aiMode),
    workspace_research_agents: payload.enableResearch ?? true,
    workspace_chat_agents: payload.enableChat ?? true,
  });
  return mapWorkspaceRecordToOut(updated);
};

export const createWorkspaceWithAssets = async (
  payload: CreateWorkspacePayload,
): Promise<WorkspaceOut> => {
  const description = payload.description?.trim() || `${payload.name} workspace`;
  const created = await createWorkspaceRecordWithAssets({
    name: payload.name,
    desc: description,
    icon: payload.icon ?? null,
    accent_clr: payload.accentColor ?? null,
    connected_bucket_id: payload.connectedBucketId ?? payload.bucket ?? null,
    ai_config: toWorkspaceAiConfig(payload.aiMode),
    workspace_research_agents: payload.enableResearch ?? true,
    workspace_chat_agents: payload.enableChat ?? true,
    banner_file: payload.bannerImage ?? null,
    icon_file: payload.customIcon ?? null,
  });
  return mapWorkspaceRecordToOut(created);
};

export const uploadWorkspaceBanner = async (
  workspaceId: string,
  file: File,
): Promise<WorkspaceOut> => {
  const updated = await uploadWorkspaceBannerRecord(workspaceId, file);
  return mapWorkspaceRecordToOut(updated);
};

export const uploadWorkspaceIcon = async (
  workspaceId: string,
  file: File,
): Promise<WorkspaceOut> => {
  const updated = await uploadWorkspaceIconRecord(workspaceId, file);
  return mapWorkspaceRecordToOut(updated);
};

export const patchWorkspace = async (
  id: string,
  payload: WorkspacePatch,
): Promise<WorkspaceOut> => {
  const patchPayload: WorkspacePatchRequest = {
    name: payload.name,
    desc: payload.description,
    icon: payload.icon,
    accent_clr: payload.accentColor,
    connected_bucket_id: payload.connectedBucketId,
    ai_config:
      payload.aiMode === undefined
        ? undefined
        : toWorkspaceAiConfig(payload.aiMode),
    workspace_research_agents: payload.enableResearch,
    workspace_chat_agents: payload.enableChat,
  };

  const updated = await patchWorkspaceRecord(id, patchPayload);
  return mapWorkspaceRecordToOut(updated);
};

export const deleteWorkspace = async (id: string): Promise<void> => {
  await deleteWorkspaceRecord(id);
};

export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
    return;
  }

  delete api.defaults.headers.common.Authorization;
};

export default api;
