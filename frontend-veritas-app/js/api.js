/**
 * Sentinel AI - API Client Layer
 * Handles all secure communication with the Veritas Verification Engine.
 */

// --- CONFIGURATION ---
// Automatically detects if running locally or on a deployed server.
const IS_LOCAL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

// REPLACE THIS URL with your actual Railway/Render backend URL when deploying.
const PRODUCTION_API_URL = "https://YOUR_RAILWAY_URL.up.railway.app/api/v1";
const LOCAL_API_URL = "http://localhost:8000/api/v1";

const API_BASE_URL = IS_LOCAL ? LOCAL_API_URL : PRODUCTION_API_URL;

class ApiClient {
    
    /**
     * Core request wrapper with standardized error handling.
     */
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        const config = {
            ...options,
            headers
        };

        try {
            const response = await fetch(url, config);

            // Handle non-200 responses (404, 500, etc.)
            if (!response.ok) {
                const errorBody = await response.json().catch(() => ({}));
                const errorMessage = errorBody.detail || `HTTP Error: ${response.status}`;
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            // This catches network errors (offline) and the explicit throws above
            console.warn(`[Sentinel API] Request Failed: ${endpoint}`, error);
            throw error; // Re-throw for UI to handle (e.g., showing a toast)
        }
    }

    // --- 1. PUBLIC DASHBOARD ENDPOINTS ---

    /**
     * GET /crises/
     * Retrieves the live grid of active threats.
     * Used by: index.html (Dashboard)
     */
    async getCrises() {
        return this.request('/crises/');
    }

    /**
     * GET /crises/{id}
     * Retrieves metadata and the Master Verdict for a specific crisis.
     * Used by: timeline.html (Hero Section)
     */
    async getCrisis(crisisId) {
        if (!crisisId) throw new Error("Crisis ID is required");
        return this.request(`/crises/${crisisId}`);
    }

    /**
     * GET /crises/{id}/timeline
     * Retrieves the verified timeline items (claims, debunks).
     * Used by: timeline.html (Feed)
     */
    async getTimeline(crisisId) {
        if (!crisisId) throw new Error("Crisis ID is required");
        return this.request(`/crises/${crisisId}/timeline`);
    }

    // --- 2. AD-HOC INTELLIGENCE ENDPOINTS ---

    /**
     * POST /analyze
     * Submits a user query (rumor) for autonomous verification.
     * Returns a job ID to poll.
     */
    async startAdHocAnalysis(queryText) {
        if (!queryText || queryText.length < 5) {
            throw new Error("Query text must be at least 5 characters.");
        }
        return this.request('/analyze', {
            method: 'POST',
            body: JSON.stringify({ query_text: queryText })
        });
    }

    /**
     * GET /analyze/{id}
     * Polls the status of a specific verification job.
     * Returns: { status: "PROCESSING" | "COMPLETED", verdict_status: "...", ... }
     */
    async getAdHocAnalysisStatus(analysisId) {
        if (!analysisId) throw new Error("Analysis ID is required");
        return this.request(`/analyze/${analysisId}`);
    }

    // --- 3. SYSTEM ENDPOINTS ---

    /**
     * GET /notifications/latest
     * Polling endpoint for system-wide "Red Alerts" (e.g. "STOP SHARING X").
     */
    async getLatestNotification() {
        return this.request('/notifications/latest');
    }
}

// Export a singleton instance
export const api = new ApiClient();