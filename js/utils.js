// --- Configuration & Constants (Shared) ---
const API_BASE_URL = "/api/v1";
const CRISIS_ID = "mumbai-floods-2025";
const POLL_INTERVAL_MS = 30000; // 30 seconds (Action 3: Adaptive Polling)
const MIN_CLAIM_LENGTH = 10;

// Trust UX Colors mapping (Shared)
const STATUS_COLORS = {
    'VERIFIED': { icon: '✅', label: 'VERIFIED', color: 'status-VERIFIED' },
    'DEBUNKED': { icon: '❌', label: 'DEBUNKED', color: 'status-DEBUNKED' },
    'UNCONFIRMED': { icon: '🟡', label: 'UNCONFIRMED', color: 'status-UNCONFIRMED' },
};

// --- Utility Functions (Shared) ---

/**
 * Action 6: Displays an in-app toast notification.
 * This is a shared utility used by the timeline page for impactful alerts.
 * @param {string} message - The notification message.
 * @param {string} type - The status type ('VERIFIED', 'DEBUNKED', 'UNCONFIRMED').
 */
function showToast(message, type) {
    const toastContainer = document.getElementById('toast-container');
    // Only show toast if the container exists (i.e., we are on the timeline page)
    if (!toastContainer) return;
    
    const status = STATUS_COLORS[type] || STATUS_COLORS['UNCONFIRMED'];
    const toast = document.createElement('div');
    
    // Visual Physics: Uses Tailwind classes for sliding up from bottom-right corner
    toast.className = `status-bg text-sm font-semibold px-4 py-3 rounded-xl shadow-2xl transition-all duration-300 transform translate-y-full opacity-0 max-w-xs`;
    toast.style.width = 'fit-content';
    toast.style.cursor = 'pointer';
    toast.innerHTML = `<div class="flex items-center space-x-2"><span>${status.icon}</span><span>${message}</span></div>`;
    
    toastContainer.appendChild(toast);
    
    // Use requestAnimationFrame for smooth 60fps animation
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-full', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
    });

    // Auto-hide the toast after 8 seconds
    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-full', 'opacity-0');
        setTimeout(() => {
            toast.remove();
        }, 300); // Wait for CSS transition to finish
    }, 8000);

    // Close on click
    toast.onclick = () => {
        toast.remove();
    };
}

/**
 * Renders a single timeline item card.
 * This is a shared utility function used by the timeline page.
 * @param {Object} item - The timeline item object.
 * @returns {HTMLElement} The created DOM element.
 */
function createTimelineCard(item) {
    const status = STATUS_COLORS[item.status] || STATUS_COLORS['UNCONFIRMED'];
    const card = document.createElement('div');
    card.id = `timeline-item-${item.id}`; // Unique ID for diffing
    card.className = "bg-white p-5 rounded-xl shadow-xl transition-all duration-300 hover:shadow-2xl";
    
    card.innerHTML = `
        <!-- Trust UX Color-Coded Header -->
        <div class="flex items-center justify-between mb-3 pb-3 border-b-2 border-gray-100">
            <span class="${status.color} px-3 py-1 text-sm font-bold uppercase rounded-full status-ring">
                ${status.icon} ${status.label}
            </span>
            <time class="text-xs text-gray-500">
                ${new Date(item.created_at).toLocaleString()}
            </time>
        </div>

        <!-- Claim Text -->
        <p class="text-lg font-semibold text-gray-800 mb-3">${item.claim_text}</p>
        
        <!-- Verdict Summary -->
        <p class="text-gray-600 italic mb-4">${item.summary}</p>
        
        <!-- Evidence Sources (JSON Evidence Storage) -->
        ${item.sources && item.sources.length > 0 ? `
            <div class="mt-4 pt-3 border-t border-gray-100">
                <p class="text-xs font-semibold uppercase text-gray-500 mb-2">Source Evidence (${item.sources.length})</p>
                <ul class="space-y-1">
                    ${item.sources.map(source => `
                        <li class="text-sm text-blue-600 hover:text-blue-800 truncate">
                            <a href="${source.uri}" target="_blank" rel="noopener noreferrer" title="${source.title || source.uri}">
                                ${source.title || source.uri}
                            </a>
                        </li>
                    `).join('')}
                </ul>
            </div>
        ` : '<p class="text-sm text-gray-400 mt-3 pt-3 border-t border-gray-100">No public sources available for this claim.</p>'}
    `;
    return card;
}