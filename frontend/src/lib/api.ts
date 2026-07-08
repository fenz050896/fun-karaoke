type ApiErrorPayload = {
  code: string
  message: string
  detail?: string
}

export type SearchResponse = {
  ok?: boolean
  results: Array<{
    videoId: string
    title: string
    artist: string
    duration: number
  }>
  error?: ApiErrorPayload | null
}

export class ApiClientError extends Error {
  code?: string
  detail?: string

  constructor(message: string, code?: string, detail?: string) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.detail = detail
  }
}

const API_BASE = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || "/api")
  : "http://backend:8000";

async function readJsonError(res: Response, fallback: string) {
  try {
    const data = await res.json()
    const payload = data?.error
    if (payload?.message) {
      return new ApiClientError(payload.message, payload.code, payload.detail)
    }
    if (data?.detail) {
      return new ApiClientError(String(data.detail))
    }
  } catch {
    return new ApiClientError(fallback)
  }
  return new ApiClientError(fallback)
}

export async function searchYouTube(query: string, maxResults: number = 10, searchType: string = "all"): Promise<SearchResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&max_results=${maxResults}&search_type=${searchType}`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) throw await readJsonError(res, "Search failed");

    const data = await res.json()
    if (data?.ok === false && data?.error?.message) {
      throw new ApiClientError(data.error.message, data.error.code, data.error.detail)
    }

    return {
      ok: data?.ok ?? true,
      results: data?.results || [],
      error: data?.error ?? null,
    }
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiClientError('Search timed out. Try again.', 'request_timeout')
    }
    throw error;
  }
}

export async function checkTrackExists(videoId: string) {
  const res = await fetch(`${API_BASE}/track/${videoId}/exists`);
  if (!res.ok) throw new Error("Check failed");
  return res.json();
}

export async function startProcess(videoId: string, title: string, artist: string, mode: string = "karaoke", save: boolean = true) {
  const res = await fetch(`${API_BASE}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ videoId, title, artist, mode, save }),
  });
  if (!res.ok) throw new Error("Process failed");
  return res.json();
}

export async function getStatus(jobId: string) {
  const res = await fetch(`${API_BASE}/status/${jobId}`);
  if (!res.ok) throw new Error("Status check failed");
  return res.json();
}

// Get play queue (songs ready to play)
export async function getQueue() {
  const res = await fetch(`${API_BASE}/queue`);
  if (!res.ok) throw new Error("Queue fetch failed");
  return res.json();
}

// Get processing queue (songs being downloaded)
export async function getProcessingQueue() {
  const res = await fetch(`${API_BASE}/processing-queue`);
  if (!res.ok) throw new Error("Processing queue fetch failed");
  return res.json();
}

export async function clearFailedProcessingJobs() {
  const res = await fetch(`${API_BASE}/processing-queue/errors`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to clear failed jobs");
  return res.json();
}

// Add song to play queue
export async function addToQueue(videoId: string, title: string = "", artist: string = "") {
  const res = await fetch(`${API_BASE}/queue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ videoId, title, artist }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || "Failed to add to queue");
  }
  return res.json();
}

// Remove song from play queue
export async function removeFromQueue(videoId: string) {
  const res = await fetch(`${API_BASE}/queue/${videoId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to remove from queue");
  return res.json();
}

// Move song in queue
export async function moveQueueItem(videoId: string, direction: number = 1) {
  const res = await fetch(`${API_BASE}/queue/${videoId}/move?direction=${direction}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to move queue item");
  return res.json();
}

export async function getLocalFiles() {
  const res = await fetch(`${API_BASE}/local-files`);
  if (!res.ok) throw new Error("Failed to fetch local files");
  return res.json();
}

export async function getTrack(videoId: string) {
  const res = await fetch(`${API_BASE}/track/${videoId}`);
  if (!res.ok) throw new Error("Track not found");
  return res.json();
}

export function getInstrumentalUrl(videoId: string) {
  return `${API_BASE}/audio/${videoId}/instrumental`;
}

export function getFullAudioUrl(videoId: string) {
  return `${API_BASE}/audio/${videoId}/full`;
}
