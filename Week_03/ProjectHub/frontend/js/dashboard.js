// ==================== DASHBOARD JAVASCRIPT ====================

// Check authentication
if (!localStorage.getItem('token')) {
    window.location.href = 'index.html';
}

// Dashboard state
const dashboardState = {
    projects: [],
    tasks: [],
    users: [],
    loading: true,
    refreshInterval: null
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

// Initialize dashboard
async function initDashboard() {
    try {
        showLoadingState();
        
        const [projects, tasks, users] = await Promise.all([
            API.getProjects(0, 10),
            API.getTasks(null, 0, 10),
            API.getUsers(0, 10)
        ]);

        dashboardState.projects = projects || [];
        dashboardState.tasks = tasks || [];
        dashboardState.users = users || [];
        
        updateStats();
        renderRecentProjects();
        renderRecentTasks();
        renderQuickActions();
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showToast('Error loading dashboard data', 'error');
    } finally {
        hideLoadingState();
    }
}

// Update statistics cards
function updateStats() {
    const { projects, tasks, users } = dashboardState;
    
    // Animate numbers
    animateValue('projectsCount', 0, projects.length, 500);
    animateValue('tasksCount', 0, tasks.length, 500);
    animateValue('usersCount', 0, users.length, 500);
    
    const pendingTasks = tasks.filter(t => t.status === 'pending').length;
    document.getElementById('pendingCount').textContent = pendingTasks;
}

// Animate number counting
function animateValue(elementId, start, end, duration) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const range = end - start;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (range * easeOut));
        
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// Render recent projects
function renderRecentProjects() {
    const container = document.getElementById('recentProjects');
    if (!container) return;
    
    const { projects } = dashboardState;
    
    if (projects.length === 0) {
        container.innerHTML = `
            <li class="recent-item">
                <div class="recent-item-info">
                    <div class="recent-item-title" style="color: var(--text-muted)">
                        No projects yet
                    </div>
                </div>
            </li>
        `;
        return;
    }
    
    container.innerHTML = projects.slice(0, 5).map(p => `
        <li class="recent-item" onclick="window.location.href='projects.html'">
            <div class="recent-item-icon project">📁</div>
            <div class="recent-item-info">
                <div class="recent-item-title">${escapeHtml(p.title)}</div>
                <div class="recent-item-meta">
                    ${escapeHtml(p.description) || 'No description'} • ${formatDate(p.created_at)}
                </div>
            </div>
            <span class="badge badge-active">Active</span>
        </li>
    `).join('');
}

// Render recent tasks
function renderRecentTasks() {
    const container = document.getElementById('recentTasks');
    if (!container) return;
    
    const { tasks, projects } = dashboardState;
    
    if (tasks.length === 0) {
        container.innerHTML = `
            <li class="recent-item">
                <div class="recent-item-info">
                    <div class="recent-item-title" style="color: var(--text-muted)">
                        No tasks yet
                    </div>
                </div>
            </li>
        `;
        return;
    }
    
    container.innerHTML = tasks.slice(0, 5).map(t => {
        const project = projects.find(p => p.id === t.project_id);
        const statusClass = t.status === 'completed' ? 'completed' : 
                          t.status === 'in_progress' ? 'progress' : 'pending';
        const statusText = t.status === 'completed' ? 'Completed' : 
                          t.status === 'in_progress' ? 'In Progress' : 'Pending';
        const icon = t.status === 'completed' ? '✅' : '⏳';
        
        return `
            <li class="recent-item" onclick="window.location.href='tasks.html'">
                <div class="recent-item-icon task">${icon}</div>
                <div class="recent-item-info">
                    <div class="recent-item-title">${escapeHtml(t.title)}</div>
                    <div class="recent-item-meta">
                        ${escapeHtml(project?.title || 'Unassigned')} • ${timeAgo(t.created_at)}
                    </div>
                </div>
                <span class="task-status status-${statusClass}">${statusText}</span>
            </li>
        `;
    }).join('');
}

// Render quick actions
function renderQuickActions() {
    const container = document.getElementById('quickActions');
    if (!container) return;
    
    container.innerHTML = `
        <div class="quick-action" onclick="window.location.href='projects.html'">
            <div class="quick-action-icon">➕</div>
            <span>New Project</span>
        </div>
        <div class="quick-action" onclick="window.location.href='tasks.html'">
            <div class="quick-action-icon">✅</div>
            <span>New Task</span>
        </div>
        <div class="quick-action" onclick="window.location.href='users.html'">
            <div class="quick-action-icon">👤</div>
            <span>Add User</span>
        </div>
    `;
}

// Loading state
function showLoadingState() {
    const statsContainer = document.querySelector('.dashboard-stats');
    if (statsContainer) {
        statsContainer.style.opacity = '0.5';
        statsContainer.style.pointerEvents = 'none';
    }
}

function hideLoadingState() {
    const statsContainer = document.querySelector('.dashboard-stats');
    if (statsContainer) {
        statsContainer.style.opacity = '1';
        statsContainer.style.pointerEvents = 'auto';
    }
}

