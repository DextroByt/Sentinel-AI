// frontend-veritas-app/js/utils.js

// --- Audio Assets (Subtle Sci-Fi Ping) ---
const ALERT_SOUND = new Audio("data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU"); 

export async function requestNotificationPermission() {
    if (!("Notification" in window)) {
        console.warn("This browser does not support desktop notification");
        return;
    }
    
    if (Notification.permission !== "denied") {
        const permission = await Notification.requestPermission();
        if (permission === "granted") {
            localStorage.setItem('sentinel_notifications_enabled', 'true');
            
            // Welcome Toast
            showToast("Uplink Established. You are now connected to the Sentinel Network.", "success");
        }
    }
}

export function formatTime(isoString) {
    if (!isoString) return 'Syncing...';
    const date = new Date(isoString);
    
    // "Just now" logic
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    
    return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    }).format(date);
}

/**
 * Centralized Style Logic for Badges & Status Indicators.
 * Aligning with the Neon/Glass theme.
 */
export function getStatusClasses(status) {
    const s = status ? status.toUpperCase() : 'UNCONFIRMED';
    
    // 1. THREAT LEVELS (Master Verdicts)
    if (s.includes('CATASTROPHIC') || s.includes('EMERGENCY')) {
        return {
            text: 'text-red-200',
            bg: 'bg-red-600',
            bgText: 'bg-red-500/10 border-red-500/30',
            label: '🚨 CATASTROPHIC'
        };
    }
    if (s.includes('MISINFORMATION') || s.includes('HOAX')) {
        return {
            text: 'text-purple-200',
            bg: 'bg-purple-600',
            bgText: 'bg-purple-500/10 border-purple-500/30',
            label: '🛡️ HOAX DETECTED'
        };
    }

    // 2. ITEM STATUSES (Timeline Items)
    switch (s) {
        case 'VERIFIED':
            return {
                text: 'text-green-400',
                bg: 'bg-green-500',
                bgText: 'bg-green-500/10 border-green-500/20',
                label: 'VERIFIED REAL'
            };
        case 'DEBUNKED':
            return {
                text: 'text-red-400',
                bg: 'bg-red-500',
                bgText: 'bg-red-500/10 border-red-500/20',
                label: 'DEBUNKED'
            };
        case 'PROCESSING':
            return {
                text: 'text-blue-400',
                bg: 'bg-blue-500',
                bgText: 'bg-blue-500/10 border-blue-500/20',
                label: 'PROCESSING'
            };
        case 'FAILED':
            return {
                text: 'text-gray-400',
                bg: 'bg-gray-500',
                bgText: 'bg-gray-500/10 border-gray-500/20',
                label: 'ERROR'
            };
        case 'UNCONFIRMED':
        default:
            return {
                text: 'text-yellow-400',
                bg: 'bg-yellow-500',
                bgText: 'bg-yellow-500/10 border-yellow-500/20',
                label: 'UNCONFIRMED'
            };
    }
}

// --- GLASSMORPHIC TOAST SYSTEM ---
export function showToast(message, type = 'info', crisisId = null) {
    const userPrefersAlerts = localStorage.getItem('sentinel_notifications_enabled') !== 'false';

    // 1. Browser Notification (Background)
    if (Notification.permission === "granted" && userPrefersAlerts) {
        if (type === 'error' || type === 'info' || message.includes("EMERGENCY")) {
            try {
                const title = type === 'error' ? "🚨 Sentinel Alert" : "Sentinel Update";
                const notif = new Notification(title, {
                    body: message,
                    icon: "/favicon.ico", 
                    tag: "sentinel-alert", 
                    renotify: true
                });
                if (crisisId) {
                    notif.onclick = (event) => {
                        event.preventDefault();
                        window.focus();
                        window.location.href = `timeline.html?id=${crisisId}`;
                        notif.close();
                    };
                }
            } catch (e) { console.warn("Native notification failed:", e); }
        }
    }

    // 2. In-App Glass Toast (Foreground)
    const toast = document.createElement('div');

    // Styles based on type
    let colors = 'border-blue-500/30 text-blue-200 shadow-[0_4px_20px_rgba(59,130,246,0.2)]'; // Info
    let icon = `<svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;

    if (type === 'error') { // Critical / Crisis
        colors = 'border-red-500/30 text-red-200 shadow-[0_4px_20px_rgba(239,68,68,0.2)]';
        icon = `<span class="relative flex h-2 w-2 mr-1"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span></span>`;
    }
    if (type === 'success') { // Verified / Done
        colors = 'border-green-500/30 text-green-200 shadow-[0_4px_20px_rgba(34,197,94,0.2)]';
        icon = `<svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
    }

    const cursorClass = crisisId ? 'cursor-pointer hover:scale-105 active:scale-95' : '';

    // Structure
    toast.className = `fixed bottom-6 right-6 px-5 py-4 rounded-xl backdrop-blur-xl bg-black/60 border ${colors} ${cursorClass} flex items-start gap-3 max-w-sm z-[100] transition-all duration-500 opacity-0 translate-y-4 font-mono text-xs transform`;
    
    if (crisisId) {
        toast.onclick = () => { window.location.href = `timeline.html?id=${crisisId}`; };
    }

    toast.innerHTML = `
        <div class="mt-0.5 shrink-0">${icon}</div>
        <div class="flex flex-col gap-1">
            <span class="leading-relaxed font-medium">${message}</span>
            ${crisisId ? '<span class="text-[9px] opacity-60 uppercase tracking-wider flex items-center gap-1">View Intel <span class="text-[10px]">→</span></span>' : ''}
        </div>
    `;

    document.body.appendChild(toast);

    // Play Sound
    if (userPrefersAlerts) {
        ALERT_SOUND.play().catch(() => {}); 
    }

    // Animate In
    requestAnimationFrame(() => {
        toast.classList.remove('opacity-0', 'translate-y-4');
    });

    // Auto Dismiss
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-4');
        setTimeout(() => toast.remove(), 500);
    }, 5000); 
}