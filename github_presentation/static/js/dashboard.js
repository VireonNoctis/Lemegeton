// Dashboard JavaScript - Tailwind-based Monitoring Interface

function updateStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // Update timestamp
            document.getElementById('timestamp').textContent = new Date(data.timestamp).toLocaleString();
            
            // Update system stats
            if (data.system) {
                updateProgressBar('cpu', data.system.cpu_percent);
                updateProgressBar('memory', data.system.memory_percent);
                updateProgressBar('disk', data.system.disk_percent);
                
                document.getElementById('memory-usage').textContent = 
                    `${data.system.memory_used_gb} GB / ${data.system.memory_total_gb} GB`;
                document.getElementById('disk-free').textContent = `${data.system.disk_free_gb} GB free`;
                document.getElementById('db-size').textContent = `${data.system.database_size_mb} MB`;
            }
            
            // Update health status
            if (data.health) {
                const healthElement = document.getElementById('health-status');
                healthElement.textContent = data.health.status.toUpperCase();
                
                // Update Tailwind classes based on status
                healthElement.className = 'px-3 py-1 rounded-full text-sm font-medium ';
                if (data.health.status === 'healthy') {
                    healthElement.className += 'bg-green-500/20 text-green-300 border border-green-500/30';
                } else if (data.health.status === 'warning') {
                    healthElement.className += 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30';
                } else {
                    healthElement.className += 'bg-red-500/20 text-red-300 border border-red-500/30';
                }
                
                const issuesElement = document.getElementById('health-issues');
                if (data.health.issues.length > 0) {
                    issuesElement.innerHTML = `
                        <div class="bg-red-500/10 border border-red-500/20 rounded-xl p-4 mt-4">
                            <div class="flex items-center gap-2 mb-2">
                                <div class="w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-xs font-bold text-white">!</div>
                                <strong class="text-red-300 font-medium">Issues Detected</strong>
                            </div>
                            <ul class="space-y-1 text-sm text-red-200 ml-7">
                                ${data.health.issues.map(issue => `
                                    <li class="flex items-center gap-2">
                                        <span class="w-1 h-1 bg-red-400 rounded-full"></span>
                                        ${issue}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>`;
                } else {
                    issuesElement.innerHTML = `
                        <div class="bg-green-500/10 border border-green-500/20 rounded-xl p-4 mt-4">
                            <div class="flex items-center gap-2">
                                <span class="text-green-400 text-lg">✅</span>
                                <span class="text-green-300 font-medium">All systems operational</span>
                            </div>
                        </div>`;
                }
            }
        })
        .catch(error => {
            console.error('Error updating stats:', error);
            showConnectionError();
        });
}

function updateProgressBar(type, percent) {
    const bar = document.getElementById(type + '-progress');
    const text = document.getElementById(type + '-percent');
    
    if (bar && text) {
        bar.style.width = percent + '%';
        text.textContent = percent + '%';
        
        // Update Tailwind color classes based on percentage and type
        let colorClass = '';
        if (type === 'cpu') {
            colorClass = percent > 85 ? 'bg-red-500' : 
                        percent > 70 ? 'bg-yellow-500' : 'bg-green-500';
        } else if (type === 'memory') {
            colorClass = percent > 85 ? 'bg-red-500' : 
                        percent > 70 ? 'bg-yellow-500' : 'bg-purple-500';
        } else if (type === 'disk') {
            colorClass = percent > 85 ? 'bg-red-500' : 
                        percent > 70 ? 'bg-yellow-500' : 'bg-cyan-500';
        }
        
        // Apply new classes
        bar.className = `h-2.5 rounded-full progress-animation ${colorClass}`;
    }
}

function showConnectionError() {
    const timestamp = document.getElementById('timestamp');
    if (timestamp) {
        timestamp.textContent = 'Connection Error';
        timestamp.className = 'font-mono text-red-400';
    }
    
    // Visual feedback for connection issues using Tailwind classes
    const cards = document.querySelectorAll('.card-hover');
    cards.forEach(card => {
        card.classList.add('opacity-50', 'blur-sm');
    });
    
    // Remove error state after a few seconds
    setTimeout(() => {
        cards.forEach(card => {
            card.classList.remove('opacity-50', 'blur-sm');
        });
        if (timestamp) {
            timestamp.className = 'font-mono text-slate-200';
        }
    }, 3000);
}

function initializeDashboard() {
    // Initial stats update
    updateStats();
    
    // Staggered card animation on load
    const cards = document.querySelectorAll('.card-hover');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 150);
    });
    
    // Add interactive effects
    addCardInteractions();
    console.log('✅ Tailwind Dashboard initialized');
}

function addCardInteractions() {
    const cards = document.querySelectorAll('.card-hover');
    
    cards.forEach(card => {
        // Enhanced hover effect
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-8px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0) scale(1)';
        });
        
        // Click ripple effect
        card.addEventListener('click', (e) => {
            const ripple = document.createElement('div');
            const rect = card.getBoundingClientRect();
            const size = 60;
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.className = 'absolute bg-white/30 rounded-full pointer-events-none';
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.style.transform = 'scale(0)';
            ripple.style.transition = 'transform 0.6s ease-out';
            
            card.style.position = 'relative';
            card.appendChild(ripple);
            
            setTimeout(() => ripple.style.transform = 'scale(2)', 10);
            setTimeout(() => ripple.remove(), 600);
        });
    });
    
    // Progress bar hover effects
    const progressBars = document.querySelectorAll('[id$="-progress"]');
    progressBars.forEach(bar => {
        bar.addEventListener('mouseenter', () => {
            bar.classList.add('shadow-lg', 'scale-105');
        });
        bar.addEventListener('mouseleave', () => {
            bar.classList.remove('shadow-lg', 'scale-105');
        });
    });
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'r' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        updateStats();
        
        // Visual feedback
        const header = document.querySelector('h1');
        if (header) {
            header.classList.add('animate-pulse');
            setTimeout(() => header.classList.remove('animate-pulse'), 1000);
        }
    }
});

// Auto-update every 30 seconds
setInterval(updateStats, 30000);

// Initialize on page load
window.addEventListener('load', initializeDashboard);