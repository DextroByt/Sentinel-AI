import { api } from './api.js';
import { showToast } from './utils.js';

// --- STATE ---
let activeCrises = [];
let filteredCrises = [];
let currentFilter = 'ALL'; // ALL, INDIA, GLOBAL
let pollingInterval = null;
let notificationInterval = null;
let lastNotificationId = localStorage.getItem('sentinel_last_notif_id');

// --- DOM ELEMENTS ---
const grid = document.getElementById('crisis-grid');
const filterBtns = document.querySelectorAll('.region-btn');

const adhocForm = document.getElementById('adhoc-analysis-form');
const adhocInput = document.getElementById('adhoc-input');
const submitBtn = document.getElementById('submit-btn');
const formStatus = document.getElementById('form-status');
const resultContainer = document.getElementById('adhoc-result-container');
const verdictText = document.getElementById('adhoc-verdict-text');
const badge = document.getElementById('adhoc-badge');
const sourcesList = document.getElementById('adhoc-sources-list');

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    await fetchCrises();
    await checkNotifications();
    
    // Polling (Live Updates)
    setInterval(fetchCrises, 5000); 
    notificationInterval = setInterval(checkNotifications, 30000);
    
    setupRegionFilter();
    setupScrollSpy();
});

// --- FUNCTIONS ---

function setupScrollSpy() {
    const navLinks = document.querySelectorAll('nav a');
    const sections = document.querySelectorAll('section[id]');

    const observerOptions = {
        root: null,
        rootMargin: '-50% 0px -50% 0px', 
        threshold: 0
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                navLinks.forEach(link => {
                    link.classList.remove('text-white', 'font-medium');
                    link.classList.add('text-gray-400');
                });
                const activeLink = document.querySelector(`nav a[href="#${entry.target.id}"]`);
                if (activeLink) {
                    activeLink.classList.remove('text-gray-400');
                    activeLink.classList.add('text-white', 'font-medium');
                }
            }
        });
    }, observerOptions);

    sections.forEach(section => observer.observe(section));
}

function setupRegionFilter() {
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => {
                b.classList.remove('active', 'bg-white', 'text-black', 'shadow-lg');
                b.classList.add('text-gray-400', 'hover:text-white', 'hover:bg-white/10');
            });
            btn.classList.add('active', 'bg-white', 'text-black', 'shadow-lg');
            btn.classList.remove('text-gray-400', 'hover:text-white', 'hover:bg-white/10');
            
            currentFilter = btn.getAttribute('data-filter');
            applyFilter();
        });
    });
}

async function fetchCrises() {
    try {
        activeCrises = await api.getCrises();
        applyFilter();
    } catch (error) {
        console.error('API Error:', error);
        renderErrorState();
    }
}

function applyFilter() {
    if (currentFilter === 'ALL') {
        filteredCrises = activeCrises;
    } else if (currentFilter === 'INDIA') {
        filteredCrises = activeCrises.filter(c => (c.location && c.location.includes('India')));
    } else if (currentFilter === 'GLOBAL') {
        filteredCrises = activeCrises.filter(c => (!c.location || !c.location.includes('India')));
    }
    renderDashboard();
}

async function checkNotifications() {
    try {
        const notification = await api.getLatestNotification();
        if (notification && notification.id !== lastNotificationId) {
            lastNotificationId = notification.id;
            localStorage.setItem('sentinel_last_notif_id', notification.id);
            
            let type = 'info';
            if (notification.notification_type === 'CATASTROPHIC_ALERT') type = 'error'; 
            if (notification.notification_type === 'MISINFO_ALERT') type = 'success';
            
            showToast(notification.content, type, notification.crisis_id);
        }
    } catch (e) {}
}

function renderDashboard() {
    if (!grid) return;
    grid.innerHTML = '';

    if (filteredCrises.length === 0) {
        grid.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-24 border border-dashed border-white/10 rounded-2xl bg-white/5">
                <p class="text-gray-500 font-mono text-xs uppercase tracking-widest mb-2">System Status: Active</p>
                <p class="text-white font-bold">
                    ${currentFilter === 'INDIA' ? 'No active threats detected in India.' : 'Global feeds are currently clear.'}
                </p>
            </div>`;
        return;
    }

    filteredCrises.forEach(crisis => {
        const card = document.createElement('a');
        card.href = `timeline.html?id=${crisis.id}`;
        
        const rawVerdict = crisis.verdict_status ? crisis.verdict_status.toUpperCase() : 'PENDING';
        
        let statusConfig = {
            word: 'ANALYZING',
            styleClass: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
            severityClass: 'severity-low', 
            dotColor: 'bg-cyan-500'
        };

        if (rawVerdict.includes('MISINFORMATION') || rawVerdict.includes('HOAX')) {
            statusConfig = {
                word: 'HOAX DETECTED',
                styleClass: 'text-purple-300 border-purple-500/40 bg-purple-500/20 shadow-[0_0_15px_rgba(147,51,234,0.2)]',
                severityClass: 'severity-hoax', 
                dotColor: 'bg-purple-400'
            };
        } 
        else if (rawVerdict.includes('CATASTROPHIC') || rawVerdict.includes('EMERGENCY')) {
            statusConfig = {
                word: 'REAL CRISIS',
                styleClass: 'text-red-200 border-red-500/40 bg-red-500/20 shadow-[0_0_15px_rgba(220,38,38,0.2)] animate-pulse',
                severityClass: 'severity-high',
                dotColor: 'bg-red-500'
            };
        }
        else if (rawVerdict.includes('CONFIRMED')) {
            statusConfig = {
                word: 'VERIFIED EVENT',
                styleClass: 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10',
                severityClass: 'severity-low',
                dotColor: 'bg-emerald-500'
            };
        }

        const locationText = (crisis.location && crisis.location !== 'Unknown Location') ? crisis.location : 'Global Region';
        const dateObj = new Date(crisis.created_at);
        const timeStr = dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

        const tags = crisis.keywords.split(',').slice(0, 3).map(t => 
            `<span class="text-[9px] font-mono bg-white/5 px-2 py-1 rounded text-gray-400 border border-white/10 uppercase tracking-wider">${t.trim()}</span>`
        ).join('');

        const displayText = crisis.verdict_summary || crisis.description || 'Agents are currently aggregating data streams...';

        card.className = `glass-panel p-6 rounded-2xl group cursor-pointer flex flex-col h-full relative overflow-hidden ${statusConfig.severityClass}`;
        
        card.innerHTML = `
            <div class="flex justify-between items-start mb-4">
                <span class="text-[9px] font-bold border px-2 py-1 rounded-md tracking-widest uppercase ${statusConfig.styleClass} flex items-center gap-2">
                    <span class="w-1.5 h-1.5 rounded-full ${statusConfig.dotColor}"></span>
                    ${statusConfig.word}
                </span>
                <span class="text-[9px] font-mono text-gray-500 flex items-center gap-1">
                    ${timeStr}
                </span>
            </div>

            <div class="mb-3">
                <h3 class="text-lg font-bold text-white group-hover:text-blue-400 transition-colors leading-tight mb-1">${crisis.name}</h3>
                <div class="flex items-center gap-1 text-[10px] text-gray-400 font-mono uppercase tracking-wider">
                    <svg class="w-3 h-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    ${locationText}
                </div>
            </div>

            <p class="text-gray-400 text-xs leading-relaxed mb-6 line-clamp-3 font-light">
                ${displayText}
            </p>

            <div class="mt-auto pt-4 border-t border-white/5 flex flex-wrap gap-2">
                ${tags}
            </div>
            
            <div class="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300 transform group-hover:translate-x-1">
                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </div>
        `;
        grid.appendChild(card);
    });
}

// --- AD HOC FORM LOGIC ---
if (adhocForm) {
    adhocForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const queryText = adhocInput.value.trim();
        if (queryText.length < 5) return;
        
        if (pollingInterval) clearInterval(pollingInterval);
        
        setLoading(true);
        resultContainer.classList.add('hidden');
        showFeedback('Deploying Agents...', 'info');
        
        try {
            const initialRes = await api.startAdHocAnalysis(queryText);
            pollAnalysis(initialRes.id);
        } catch (error) {
            showFeedback('Connection Failed', 'error');
            setLoading(false);
        }
    });
}

function pollAnalysis(analysisId) {
    let attempts = 0;
    pollingInterval = setInterval(async () => {
        attempts++;
        try {
            const data = await api.getAdHocAnalysisStatus(analysisId);
            
            if (data.status === 'COMPLETED' || data.status === 'FAILED') {
                clearInterval(pollingInterval);
                setLoading(false);
                renderAdHocResult(data);
                showFeedback('Mission Complete', 'success');
            } else {
                const msg = attempts < 3 ? "Scanning Social Vectors..." : (attempts < 6 ? "Cross-referencing Media..." : "Synthesizing Verdict...");
                showFeedback(msg, 'info');
            }
            
            if (attempts >= 45) { 
                clearInterval(pollingInterval); 
                setLoading(false); 
                showFeedback('Timeout: Agent unresponsive', 'error');
            }
        } catch (err) { 
            clearInterval(pollingInterval); 
            setLoading(false); 
        }
    }, 2000); 
}

function renderAdHocResult(data) {
    resultContainer.classList.remove('hidden');
    
    // [UPDATED] Terminal-Style Badge Reset
    badge.className = 'text-[9px] font-bold font-mono px-2 py-0.5 rounded border uppercase';
    
    if (data.status === 'FAILED') {
        badge.classList.add('bg-red-900/30', 'text-red-400', 'border-red-500/30');
        badge.innerText = 'SYSTEM FAILURE';
        verdictText.innerHTML = `<span class="text-red-400">ERROR:</span> The pipeline encountered a critical failure.`;
        return;
    }

    const verdict = data.verdict_status || "UNCLEAR";
    
    if (verdict.includes('MISINFO') || verdict.includes('HOAX')) {
        badge.classList.add('bg-purple-900/30', 'text-purple-300', 'border-purple-500/30', 'shadow-[0_0_10px_rgba(168,85,247,0.2)]');
        badge.innerText = '⚠️ HOAX CONFIRMED';
    } else if (verdict.includes('VERIFIED') || verdict.includes('REAL')) {
        badge.classList.add('bg-green-900/30', 'text-green-400', 'border-green-500/30', 'shadow-[0_0_10px_rgba(74,222,128,0.2)]');
        badge.innerText = '✅ VERIFIED REAL';
    } else {
        badge.classList.add('bg-blue-900/30', 'text-blue-400', 'border-blue-500/30');
        badge.innerText = '❓ UNCONFIRMED';
    }
    
    verdictText.innerText = data.verdict_summary;
    sourcesList.innerHTML = '';
    
    if (data.verdict_sources?.length) {
        data.verdict_sources.forEach(s => {
            const li = document.createElement('li');
            li.className = "flex items-start gap-2 group/link";
            li.innerHTML = `
                <span class="text-blue-500 mt-0.5">›</span>
                <a href="${s.url}" target="_blank" class="hover:text-white transition-colors underline decoration-blue-500/30 decoration-1 underline-offset-4 group-hover/link:decoration-blue-400 truncate w-full">
                    ${s.title}
                </a>
            `;
            sourcesList.appendChild(li);
        });
    } else {
        sourcesList.innerHTML = '<li class="text-gray-500 italic">> No public data trace found. Verdict inferred from logic patterns.</li>';
    }
}

function renderErrorState() {
    if (!grid) return;
    grid.innerHTML = `
        <div class="col-span-full text-center p-12 border border-red-900/30 rounded-2xl bg-red-900/10">
            <p class="text-red-500 font-mono text-sm tracking-widest mb-2">⚠ CONNECTION LOST</p>
            <p class="text-gray-400 text-xs">Backend uplink is offline. Retrying...</p>
        </div>`;
}

function showFeedback(msg, type) {
    if (!formStatus) return;
    formStatus.innerText = `> ${msg}`;
    formStatus.className = `text-xs font-mono transition-opacity uppercase tracking-wider ${type==='error'?'text-red-500':'text-blue-400 animate-pulse'}`;
}

function setLoading(isLoading) {
    if (!submitBtn) return;
    submitBtn.disabled = isLoading;
    if(isLoading) {
        submitBtn.innerHTML = `<span class="animate-pulse">PROCESSING...</span>`;
        submitBtn.classList.add('opacity-75', 'cursor-wait');
    } else {
        submitBtn.innerHTML = `
            <span class="relative z-10 flex items-center gap-2">
                Initiate Scan
                <svg class="w-4 h-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </span>`;
        submitBtn.classList.remove('opacity-75', 'cursor-wait');
    }
}