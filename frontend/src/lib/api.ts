const API_BASE = typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || "/api")
  : "http://backend:8000";

export async function searchYouTube(query: string, maxResults: number = 10, searchType: string = "all") {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  
  try {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&max_results=${maxResults}&search_type=${searchType}`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) throw new Error("Search failed");
    return res.json();
  } catch (error) {
    clearTimeout(timeoutId);
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
