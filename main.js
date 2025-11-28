// --- Configuration & Constants ---
const API_BASE_URL = "/api/v1";
const CRISIS_ID = "mumbai-floods-2025";
const POLL_INTERVAL_MS = 30000; // 30 seconds (Action 3: Adaptive Polling)
const MIN_CLAIM_LENGTH = 10;

// Trust UX Colors mapping
const STATUS_COLORS = {
    'VERIFIED': { icon: '✅', label: 'VERIFIED', color: 'status-VERIFIED' },
    'DEBUNKED': { icon: '❌', label: 'DEBUNKED', color: 'status-DEBUNKED' },
    'UNCONFIRMED': { icon: '🟡', label: 'UNCONFIRMED', color: 'status-UNCONFIRMED' },
};

// State to track current timeline items for diffing logic
let currentTimelineItemIds = new Set();
let lastUpdateTime = new Date().toISOString();

// --- DOM Elements ---
// Note: These elements must exist in the loaded index.html file
const timelineContainer = document.getElementById('timeline-container');
const skeletonContainer = document.getElementById('skeleton-container');
const claimModal = document.getElementById('claim-modal');
const submitClaimBtn = document.getElementById('submit-claim-btn');
const cancelClaimBtn = document.getElementById('cancel-claim-btn');
const claimForm = document.getElementById('claim-form');
const claimTextInput = document.getElementById('claim-text-input');
const verifyNowBtn = document.getElementById('verify-now-btn');
const charCountDisplay = document.getElementById('char-count');
const submissionReceipt = document.getElementById('submission-receipt');
const toastContainer = document.getElementById('toast-container');

// --- Utility Functions ---

/**
 * Action 6: Displays an in-app toast notification.
 * @param {string} message - The notification message.
 * @param {string} type - The status type ('VERIFIED', 'DEBUNKED', 'UNCONFIRMED').
 */
function showToast(message, type) {
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

/**
 * Fetches and renders the timeline with Adaptive Polling and Diffing Logic (Action 3).
 */
async function loadTimeline() {
    try {
        // Show skeleton loaders if this is the initial load
        if (currentTimelineItemIds.size === 0) {
            skeletonContainer.classList.remove('hidden');
            // Clear only if the skeleton is visible to prevent flash
            if (timelineContainer.children.length > 0) timelineContainer.innerHTML = '';
        }

        const response = await fetch(`${API_BASE_URL}/crises/${CRISIS_ID}/timeline`);
        if (!response.ok) throw new Error("Network response was not ok.");
        
        const newItems = await response.json();
        const newItemIds = new Set(newItems.map(item => item.id));
        const newlyAddedItems = [];
        
        // Diffing Logic: Check for new items to prepend and notify
        newItems.forEach(item => {
            if (!currentTimelineItemIds.has(item.id)) {
                // Mark as new
                newlyAddedItems.push(item);
            }
            // Keep track of which items are currently in the response
            currentTimelineItemIds.add(item.id);
        });

        // Clear the old set and update with the latest IDs to ensure we track only current items
        currentTimelineItemIds = newItemIds;
        
        // Remove the skeleton loaders once real data is present
        skeletonContainer.classList.add('hidden');
        
        // --- Re-render/Update Logic ---
        // We use a DocumentFragment to minimize DOM reflows during update/sort
        const fragment = document.createDocumentFragment();
        
        // Use the fetched (and implicitly sorted by backend) list to re-order the cards
        newItems.forEach(item => {
            let element = document.getElementById(`timeline-item-${item.id}`);
            
            if (element) {
                // Item exists, detach it to re-attach later (for sorting)
                fragment.appendChild(element);
            } else {
                // Item is new, create and add to fragment
                element = createTimelineCard(item);
                fragment.appendChild(element);
            }
        });

        // Replace the timeline container content with the newly ordered fragment
        timelineContainer.innerHTML = '';
        // Since the API returns sorted data (newest first), appending them in order from the fragment 
        // ensures the correct visual order in the DOM.
        fragment.childNodes.forEach(child => {
            timelineContainer.appendChild(child);
        });
        
        // Send Toast Notifications for highly impactful new items (Action 6)
        newlyAddedItems.forEach(item => {
            const statusText = STATUS_COLORS[item.status].label;
            const toastMessage = `NEW ${statusText}: ${item.summary.substring(0, 50)}...`;
            showToast(toastMessage, item.status);
        });
        
    } catch (error) {
        console.error("Failed to load timeline:", error);
        // Optionally show an error toast
        if (currentTimelineItemIds.size === 0) {
            skeletonContainer.innerHTML = `<p class="text-red-600 text-center p-8">Error loading data. Check API connection.</p>`;
        }
    }
}

// --- Event Listeners and Initializers ---

// Modal Open/Close Logic
submitClaimBtn.addEventListener('click', () => {
    claimModal.classList.remove('hidden');
    claimModal.classList.add('flex');
    claimTextInput.focus();
    submissionReceipt.classList.add('hidden'); // Reset receipt
    claimTextInput.value = ''; // Clear input
    verifyNowBtn.disabled = true; // Reset button state
    charCountDisplay.classList.remove('text-green-500');
    charCountDisplay.classList.add('text-red-500');
    charCountDisplay.textContent = `0 / ${MIN_CLAIM_LENGTH} required`;
});

cancelClaimBtn.addEventListener('click', () => {
    claimModal.classList.add('hidden');
    claimModal.classList.remove('flex');
});

// Client-Side Validation (Action 4)
claimTextInput.addEventListener('input', () => {
    const length = claimTextInput.value.length;
    const isValid = length >= MIN_CLAIM_LENGTH;
    verifyNowBtn.disabled = !isValid;
    charCountDisplay.textContent = `${length} / ${MIN_CLAIM_LENGTH} required`;
    
    // Positive reinforcement UX
    if (isValid) {
        charCountDisplay.classList.remove('text-red-500');
        charCountDisplay.classList.add('text-green-500');
    } else {
        charCountDisplay.classList.remove('text-green-500');
        charCountDisplay.classList.add('text-red-500');
    }
});

// Claim Submission Handler (Action 4)
claimForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const claimText = claimTextInput.value.trim();
    if (claimText.length < MIN_CLAIM_LENGTH) return;

    // Disable button and show loading state
    verifyNowBtn.disabled = true;
    verifyNowBtn.textContent = 'Submitting...';

    try {
        const response = await fetch(`${API_BASE_URL}/crises/${CRISIS_ID}/submit-claim`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ claim_text: claimText })
        });

        if (!response.ok) {
            throw new Error("Submission failed. Server error.");
        }

        const receipt = await response.json();
        
        // Immediate Acknowledgement UX
        claimTextInput.style.display = 'none';
        claimForm.querySelector('.flex').style.display = 'none';
        
        document.getElementById('receipt-id').textContent = receipt.id.substring(0, 8) + '...';
        submissionReceipt.classList.remove('hidden');
        
        showToast(`Claim submitted! ID ${receipt.id.substring(0, 8)}. Status: PENDING.`, 'UNCONFIRMED');

        // Reset modal after a delay
        setTimeout(() => {
            claimModal.classList.add('hidden');
            claimModal.classList.remove('flex');
            claimTextInput.style.display = 'block';
            // Re-enable the flex container for buttons
            const buttonContainer = claimForm.querySelector('.flex');
            if (buttonContainer) buttonContainer.style.display = 'flex'; 
            verifyNowBtn.textContent = 'VERIFY NOW';
            
            // Re-run validation logic to ensure proper button state after reset
            claimTextInput.dispatchEvent(new Event('input')); 
        }, 5000);

    } catch (error) {
        console.error("Claim submission failed:", error);
        verifyNowBtn.textContent = 'Failed. Retry?';
        verifyNowBtn.disabled = false;
        showToast(`Failed to submit claim: ${error.message}`, 'DEBUNKED');
    }
});


// Initial Load and Adaptive Polling
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    loadTimeline();
    
    // Adaptive Polling (Action 3)
    setInterval(loadTimeline, POLL_INTERVAL_MS);
});