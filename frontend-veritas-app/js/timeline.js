import { api } from './api.js';
import { formatTime, getStatusClasses, showToast } from './utils.js';

const state = {
    crisisId: null,
    items: [],
    crisisMetadata: null, 
    filter: 'ALL',
    pollingInterval: null,
    notificationInterval: null,
    lastNotificationId: localStorage.getItem('sentinel_last_notif_id')
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    state.crisisId = urlParams.get('id');

    if (!state.crisisId) {
        window.location.href = 'index.html';
        return;
    }

    // Initial Fetch
    await loadCrisisDetails();
    await loadTimeline();
    await checkNotifications(); 

    // Live Polling (Every 4s for snappier updates)
    state.pollingInterval = setInterval(async () => {
        await Promise.all([loadTimeline(), loadCrisisDetails()]);
    }, 4000);
    
    state.notificationInterval = setInterval(checkNotifications, 30000);
    
    setupFilters();
});

// --- DATA FETCHING ---

async function loadCrisisDetails() {
    try {
        const crisis = await api.getCrisis(state.crisisId);
        if (crisis) {
            state.crisisMetadata = crisis;
            
            // Update Title & Meta
            document.title = `Timeline: ${crisis.name} - Sentinel AI`;
            
            // Populate Verdict Hero Section
            renderConclusion(crisis);
        }
    } catch (e) { 
        console.error("Failed to load crisis details", e); 
    }
}

async function loadTimeline() {
    try {
        const items = await api.getTimeline(state.crisisId);
        
        // Simple diff to avoid re-rendering DOM if data hasn't changed
        if (items.length !== state.items.length || (items.length > 0 && items[0].id !== state.items[0]?.id)) {
            state.items = items;
            renderKeyUpdates(items);
            renderTimeline();
        }
    } catch (error) { 
        console.warn("Timeline sync skipped:", error); 
    }
}

async function checkNotifications() {
    try {
        const notification = await api.getLatestNotification();
        if (notification && notification.id !== state.lastNotificationId) {
            state.lastNotificationId = notification.id;
            localStorage.setItem('sentinel_last_notif_id', notification.id);
            
            let type = 'info';
            if (notification.notification_type === 'CATASTROPHIC_ALERT') type = 'error';
            if (notification.notification_type === 'MISINFO_ALERT') type = 'success';
            
            showToast(notification.content, type, notification.crisis_id);
        }
    } catch (e) {}
}

// --- RENDERING LOGIC ---

function renderConclusion(crisis) {
    // Elements
    const badge = document.getElementById('conclusion-badge');
    const text = document.getElementById('conclusion-text');
    const dateEl = document.getElementById('conclusion-updated-at');
    const bgPulse = document.getElementById('conclusion-bg-pulse');
    const title = document.getElementById('crisis-name');
    const container = document.getElementById('conclusion-section');

    if (!badge || !container) return;

    // 1. Content Updates
    title.innerText = crisis.name;
    text.innerText = crisis.verdict_summary || "Sentinel AI is aggregating verified claims and cross-referencing data sources...";
    
    const dateStr = crisis.updated_at ? formatTime(crisis.updated_at) : 'Syncing...';
    dateEl.innerText = `LAST INTEL UPDATE: ${dateStr}`;

    // 2. Theme Logic (Dynamic Glows)
    const status = crisis.verdict_status ? crisis.verdict_status.toUpperCase() : 'PENDING';
    
    // Reset base classes
    badge.className = 'px-4 py-1.5 rounded-md border text-[10px] font-bold font-mono uppercase tracking-widest transition-all duration-500';
    
    if (status.includes('MISINFORMATION') || status.includes('HOAX')) {
        // PURPLE THEME (Hoax)
        badge.innerText = "🛡️ LETHAL MISINFORMATION";
        badge.classList.add('bg-purple-500/20', 'text-purple-300', 'border-purple-500/50', 'shadow-[0_0_15px_#9333ea]');
        
        bgPulse.className = "absolute top-0 left-0 w-full h-full bg-gradient-to-r from-purple-900/20 via-transparent to-transparent opacity-50 transition-all duration-1000";
        container.classList.add('border-purple-500/30');
    }
    else if (status.includes('CATASTROPHIC') || status.includes('EMERGENCY')) {
        // RED THEME (Real Disaster)
        badge.innerText = "🚨 CATASTROPHIC EMERGENCY";
        badge.classList.add('bg-red-500/20', 'text-red-200', 'border-red-500/50', 'animate-pulse', 'shadow-[0_0_15px_#dc2626]');
        
        bgPulse.className = "absolute top-0 left-0 w-full h-full bg-gradient-to-r from-red-900/40 via-transparent to-transparent opacity-60 transition-all duration-1000";
        container.classList.add('border-red-500/30');
    } 
    else if (status.includes('CONFIRMED')) {
        // ORANGE THEME (Verified Event)
        badge.innerText = "⚠️ CONFIRMED SITUATION";
        badge.classList.add('bg-orange-500/10', 'text-orange-400', 'border-orange-500/50');
        
        bgPulse.className = "absolute top-0 left-0 w-full h-1 bg-orange-500 shadow-[0_0_20px_#f97316]";
    } 
    else {
        // BLUE THEME (Developing/Pending)
        badge.innerText = "📡 DEVELOPING NARRATIVE";
        badge.classList.add('bg-blue-500/10', 'text-blue-400', 'border-blue-500/50');
        
        bgPulse.className = "absolute top-0 left-0 w-full h-1 bg-blue-500/50";
    }
}

function renderKeyUpdates(items) {
    const container = document.getElementById('key-updates-grid');
    const section = document.getElementById('key-updates-section');
    
    const latestVerified = items.find(i => i.status === 'VERIFIED');
    const latestDebunked = items.find(i => i.status === 'DEBUNKED');

    const highlights = [latestVerified, latestDebunked].filter(Boolean);

    if (highlights.length === 0) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');
    container.innerHTML = '';

    highlights.forEach(item => {
        const styles = getStatusClasses(item.status);
        
        const html = `
            <div class="glass-panel p-4 rounded-xl border border-white/5 hover:border-white/10 transition group cursor-default">
                <div class="flex justify-between items-center mb-2">
                    <span class="${styles.text} text-[9px] font-bold uppercase tracking-widest border border-white/10 px-2 py-0.5 rounded bg-black/50">
                        ${styles.label}
                    </span>
                    <span class="text-[9px] text-gray-600 font-mono">${formatTime(item.timestamp)}</span>
                </div>
                <p class="text-gray-200 font-bold text-xs leading-snug mb-1">"${item.claim_text}"</p>
                <p class="text-gray-500 text-[10px] line-clamp-2">${item.summary}</p>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });
}

function renderTimeline() {
    const container = document.getElementById('timeline-feed');
    const filteredItems = state.filter === 'ALL' ? state.items : state.items.filter(i => i.status === state.filter);

    container.innerHTML = '';

    if (filteredItems.length === 0) {
        container.innerHTML = `
            <div class="pl-12 py-8 text-gray-500 text-xs font-mono italic flex items-center gap-3">
                <span class="w-2 h-2 rounded-full bg-gray-800"></span>
                No intelligence reports found for filter: <span class="text-white">${state.filter}</span>
            </div>`;
        return;
    }

    filteredItems.forEach((item) => {
        const styles = getStatusClasses(item.status);
        const dateStr = formatTime(item.timestamp);
        
        const locationHtml = item.location && item.location !== "Unknown" 
            ? `<span class="text-[9px] text-blue-400 font-mono uppercase tracking-wider flex items-center gap-1 ml-3 border-l border-white/10 pl-3">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                ${item.location}
               </span>`
            : ``;

        // --- TRUST METER LOGIC ---
        // 1. Calculate Confidence Color
        let score = item.confidence_score || 0;
        let barColor = 'bg-gray-600';
        let barGlow = '';
        
        if (score >= 90) {
            barColor = 'bg-green-500';
            barGlow = 'shadow-[0_0_10px_#22c55e]';
        } else if (score >= 70) {
            barColor = 'bg-blue-500';
            barGlow = 'shadow-[0_0_8px_#3b82f6]';
        } else if (score >= 50) {
            barColor = 'bg-yellow-500';
        }

        // 2. Generate Reasoning Trace HTML
        const trustMeterHtml = `
            <div class="mt-4 mb-3 pt-3 border-t border-white/5">
                <div class="flex justify-between items-end mb-1">
                    <span class="text-[9px] font-mono text-gray-500 uppercase tracking-widest">Confidence Index</span>
                    <span class="text-[10px] font-bold font-mono text-white">${score}%</span>
                </div>
                
                <div class="w-full bg-black/50 h-1.5 rounded-full overflow-hidden border border-white/5">
                    <div class="${barColor} ${barGlow} h-full rounded-full transition-all duration-1000 ease-out" style="width: ${score}%"></div>
                </div>
                
                <div class="flex items-start gap-2 mt-2 group/trace">
                    <span class="text-[9px] text-gray-600 font-mono uppercase mt-0.5">Trace:</span>
                    <p class="text-[9px] text-gray-500 font-mono leading-relaxed hover:text-gray-300 transition-colors cursor-help">
                        ${item.reasoning_trace || "Calculating signal strength..."}
                    </p>
                </div>
            </div>
        `;

        // Source Links Logic
        let sourceHtml = '';
        if (item.sources && item.sources.length > 0) {
             const links = item.sources.map(s => {
                const url = typeof s === 'string' ? s : s.url;
                const title = typeof s === 'string' ? new URL(s).hostname : s.title;
                return `<a href="${url}" target="_blank" class="text-gray-400 hover:text-blue-400 transition border-b border-gray-700 hover:border-blue-400 pb-0.5 decoration-0">${title}</a>`;
            }).join('<span class="mx-2 text-gray-700">/</span>');
            
            sourceHtml = `
                <div class="mt-2 flex flex-wrap items-center text-[9px] font-mono uppercase tracking-wider text-gray-500">
                    <span class="mr-2 text-gray-600">Sources:</span>
                    ${links}
                </div>`;
        }

        // Severity Glow Logic
        let severityClass = 'severity-low';
        if (item.status === 'DEBUNKED') severityClass = 'severity-hoax';
        if (item.status === 'CATASTROPHIC EMERGENCY' || item.summary.toLowerCase().includes('danger')) severityClass = 'severity-high';

        const html = `
            <div class="relative pb-8 group animate-fade-in pl-12">
                
                <div class="absolute left-[11px] top-[1.25rem] w-4 h-4 rounded-full bg-[#000000] border-2 border-gray-700 z-10 flex items-center justify-center shadow-[0_0_10px_rgba(0,0,0,1)] group-hover:border-white transition-colors duration-300">
                    <div class="w-1.5 h-1.5 rounded-full ${styles.bg} shadow-[0_0_6px_currentColor]"></div>
                </div>

                <div class="glass-panel p-6 rounded-xl border border-white/5 relative overflow-hidden ${severityClass}">
                    
                    <div class="flex justify-between items-start mb-3">
                        <div class="flex items-center">
                            <span class="${styles.text} text-[9px] font-bold uppercase tracking-widest bg-black/40 px-2 py-1 rounded border border-white/5">
                                ${styles.label}
                            </span>
                            <span class="text-[10px] text-gray-500 font-mono ml-3">${dateStr}</span>
                            ${locationHtml}
                        </div>
                    </div>

                    <h3 class="text-white font-bold text-sm mb-2 font-sans leading-snug">"${item.claim_text}"</h3>
                    <p class="text-gray-400 text-xs leading-relaxed font-light">
                        ${item.summary}
                    </p>

                    ${trustMeterHtml}
                    ${sourceHtml}
                </div>
            </div>`;
        container.insertAdjacentHTML('beforeend', html);
    });
}

// --- FILTERS ---

function setupFilters() {
    const buttons = document.querySelectorAll('.filter-btn');
    
    buttons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Reset all
            buttons.forEach(b => {
                b.classList.remove('active', 'bg-white', 'text-black', 'border-white/20');
                b.classList.add('text-gray-400', 'border-transparent', 'hover:bg-white/5');
            });

            // Activate target
            const target = e.currentTarget;
            target.classList.remove('text-gray-400', 'border-transparent', 'hover:bg-white/5');
            target.classList.add('active', 'bg-white', 'text-black', 'border-white/20');
            
            state.filter = target.getAttribute('data-filter');
            renderTimeline();
        });
    });
}