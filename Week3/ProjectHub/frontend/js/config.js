// ==================== CONFIG ====================
const CONFIG = {
    API_BASE_URL: "http://127.0.0.1:8000",
    API_TIMEOUT: 30000,
    DEBOUNCE_DELAY: 300,
    REFRESH_INTERVAL: 30000, // 30 seconds
    PAGE_SIZES: [10, 25, 50, 100]
};

// ==================== API ====================
const API = {
    // Main request function with better error handling
    async request(path, method = "GET", body = null, options = {}) {
        const token = localStorage.getItem("token");
        const headers = { 
            "Content-Type": "application/json",
            ...options.headers 
        };
        
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const config = {
            method,
            headers,
            ...options
        };
        
        if (body) config.body = JSON.stringify(body);

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), CONFIG.API_TIMEOUT);
            config.signal = controller.signal;

            const response = await fetch(CONFIG.API_BASE_URL + path, config);
            clearTimeout(timeoutId);
            
            if (response.status === 401) {
                localStorage.removeItem("token");
                showToast("Session expired. Please login again.", "warning");
                setTimeout(() => window.location = "index.html", 1500);
                return null;
            }
            
            if (response.status === 403) {
                showToast("You don't have permission to perform this action", "error");
                return null;
            }
            
            if (response.status === 204) {
                return { success: true };
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || "Request failed");
            }
            
            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                showToast("Request timeout. Please try again.", "error");
            } else {
                console.error("API Error:", error);
                showToast(error.message || "An error occurred", "error");
            }
            throw error;
        }
    },

    // ==================== AUTH ====================
    login: (credentials) => API.request("/auth/login", "POST", credentials),

    // ==================== USERS ====================
    getUsers: (skip = 0, limit = 100) => API.request(`/users/?skip=${skip}&limit=${limit}`),
    getUser: (id) => API.request(`/users/${id}`),
    createUser: (data) => API.request("/users/", "POST", data),
    updateUser: (id, data) => API.request(`/users/${id}`, "PUT", data),
    deleteUser: (id) => API.request(`/users/${id}`, "DELETE"),

    // ==================== PROJECTS ====================
    getProjects: (skip = 0, limit = 100) => API.request(`/projects/?skip=${skip}&limit=${limit}`),
    getProject: (id) => API.request(`/projects/${id}`),
    createProject: (data) => API.request("/projects/", "POST", data),
    updateProject: (id, data) => API.request(`/projects/${id}`, "PUT", data),
    deleteProject: (id) => API.request(`/projects/${id}`, "DELETE"),
    getProjectTasks: (projectId) => API.request(`/tasks/?project_id=${projectId}&limit=100`),
    getProjectOwner: (ownerId) => API.request(`/users/${ownerId}`),

    // ==================== TASKS ====================
    getTasks: (projectId = null, skip = 0, limit = 100) => {
        let url = `/tasks/?skip=${skip}&limit=${limit}`;
        if (projectId) url += `&project_id=${projectId}`;
        return API.request(url);
    },
    getTask: (id) => API.request(`/tasks/${id}`),
    createTask: (data) => API.request("/tasks/", "POST", data),
    updateTask: (id, data) => API.request(`/tasks/${id}`, "PUT", data),
    deleteTask: (id) => API.request(`/tasks/${id}`, "DELETE"),
};

// ==================== UTILITIES ====================

// Toast notification with icons
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || 'ℹ'}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Format date
function formatDate(dateString, options = {}) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...options
    };
    return date.toLocaleDateString('en-US', defaultOptions);
}

// Format datetime
function formatDateTime(dateString) {
    return formatDate(dateString, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Relative time (e.g., "2 hours ago")
function timeAgo(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };
    
    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
        }
    }
    return 'Just now';
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ==================== CONFIRM DIALOG SYSTEM ====================

// Enhanced confirm dialog with callback support
function showConfirmDialog(options) {
    const {
        title = 'Confirm Action',
        message = 'Are you sure?',
        confirmText = 'Delete',
        cancelText = 'Cancel',
        confirmClass = 'btn-danger',
        icon = '⚠️',
        onConfirm = () => {},
        onCancel = () => {}
    } = options;

    const dialog = document.getElementById('confirmDialog');
    if (!dialog) {
        console.error('Confirm dialog element not found');
        return;
    }

    // Update dialog content dynamically
    dialog.querySelector('.confirm-dialog-icon').textContent = icon;
    const titleEl = dialog.querySelector('#confirmTitle');
    const messageEl = dialog.querySelector('#confirmMessage');
    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.innerHTML = message;
    
    const confirmBtn = dialog.querySelector('#confirmDeleteBtn');
    confirmBtn.textContent = confirmText;
    confirmBtn.className = `btn ${confirmClass}`;
    
    const cancelBtn = dialog.querySelector('.btn-secondary');
    cancelBtn.textContent = cancelText;

    // Store callbacks
    dialog._confirmCallback = onConfirm;
    dialog._cancelCallback = onCancel;

    // Show dialog with animation
    dialog.classList.add('show');
}

// Enhanced close confirm dialog
function closeConfirmDialog() {
    const dialog = document.getElementById('confirmDialog');
    if (dialog) {
        dialog.classList.remove('show');
        // Clear callbacks
        dialog._confirmCallback = null;
        dialog._cancelCallback = null;
    }
}

// Convenience function for delete confirmations
function confirmDelete(itemName, itemType = 'item', onConfirm) {
    showConfirmDialog({
        title: `Delete ${itemType.charAt(0).toUpperCase() + itemType.slice(1)}`,
        message: `
            <p class="confirm-text">Are you sure you want to delete this ${itemType}?</p>
            <p class="confirm-item-name">"${escapeHtml(itemName)}"</p>
            <p class="confirm-warning">This action cannot be undone.</p>
        `,
        confirmText: 'Delete',
        cancelText: 'Cancel',
        confirmClass: 'btn-danger',
        icon: '🗑️',
        onConfirm: () => {
            onConfirm();
            showToast(`${itemType.charAt(0).toUpperCase() + itemType.slice(1)} deleted successfully`, 'success');
        }
    });
}

// Legacy function support
function confirmAction(message, onConfirm, onCancel) {
    showConfirmDialog({
        title: 'Confirm Action',
        message: message,
        onConfirm: onConfirm,
        onCancel: onCancel
    });
}

// Initialize confirm dialog event listeners
document.addEventListener('DOMContentLoaded', () => {
    const dialog = document.getElementById('confirmDialog');
    if (!dialog) return;

    const confirmBtn = dialog.querySelector('#confirmDeleteBtn');
    const cancelBtn = dialog.querySelector('.btn-secondary');

    confirmBtn.addEventListener('click', () => {
        if (dialog._confirmCallback) {
            dialog._confirmCallback();
        }
        closeConfirmDialog();
    });

    cancelBtn.addEventListener('click', () => {
        if (dialog._cancelCallback) {
            dialog._cancelCallback();
        }
        closeConfirmDialog();
    });

    // Close on overlay click
    dialog.addEventListener('click', (e) => {
        if (e.target === dialog) {
            if (dialog._cancelCallback) {
                dialog._cancelCallback();
            }
            closeConfirmDialog();
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && dialog.classList.contains('show')) {
            if (dialog._cancelCallback) {
                dialog._cancelCallback();
            }
            closeConfirmDialog();
        }
    });
});

// Logout function
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        window.location = "index.html";
    }
}

// Loading spinner
function showLoading(element) {
    if (!element) return;
    element.innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"></div>
            <p>Loading...</p>
        </div>
    `;
}

function hideLoading(element) {
    if (!element) return;
    const spinner = element.querySelector('.loading-container');
    if (spinner) spinner.remove();
}

// Check authentication
function requireAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = 'index.html';
        return false;
    }
    return true;
}

// Get user info from token (simple decode)
function getUserFromToken() {
    const token = localStorage.getItem('token');
    if (!token) return null;
    
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload;
    } catch {
        return null;
    }
}

// Export to CSV
function exportToCSV(data, filename) {
    if (!data || data.length === 0) {
        showToast('No data to export', 'warning');
        return;
    }
    
    const headers = Object.keys(data[0]);
    const csvContent = [
        headers.join(','),
        ...data.map(row => headers.map(h => {
            let val = row[h] === null ? '' : row[h];
            val = String(val).replace(/"/g, '""');
            return `"${val}"`;
        }).join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${filename}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
}

// Search filter
function filterData(data, searchTerm, fields) {
    if (!searchTerm) return data;
    const term = searchTerm.toLowerCase();
    return data.filter(item => 
        fields.some(field => {
            const value = item[field];
            return value && String(value).toLowerCase().includes(term);
        })
    );
}

// Sort data
function sortData(data, field, direction = 'asc') {
    return [...data].sort((a, b) => {
        const aVal = a[field];
        const bVal = b[field];
        
        if (aVal === bVal) return 0;
        if (aVal === null || aVal === undefined) return 1;
        if (bVal === null || bVal === undefined) return -1;
        
        const comparison = aVal < bVal ? -1 : 1;
        return direction === 'asc' ? comparison : -comparison;
    });
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape to close modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal-overlay.show');
        modals.forEach(modal => {
            modal.classList.remove('show');
        });
    }
    
    // Ctrl+K for search (if exists)
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('.search-input');
        if (searchInput) searchInput.focus();
    }
});

// Initialize tooltips
document.addEventListener('mouseover', (e) => {
    if (e.target.title && !e.target.getAttribute('data-tooltip')) {
        e.target.setAttribute('data-tooltip', e.target.title);
        e.target.title = '';
    }
});

document.addEventListener('mouseout', (e) => {
    if (e.target.getAttribute('data-tooltip')) {
        e.target.title = e.target.getAttribute('data-tooltip');
    }
});

// ==================== BACKWARD COMPATIBILITY ====================
// Export functions globally for all pages
const getUsers = API.getUsers;
const getUser = API.getUser;
const createUser = API.createUser;
const updateUser = API.updateUser;
const deleteUser = API.deleteUser;

const getProjects = API.getProjects;
const getProject = API.getProject;
const createProject = API.createProject;
const updateProject = API.updateProject;
const deleteProject = API.deleteProject;
const getProjectTasks = API.getProjectTasks;
const getProjectOwner = API.getProjectOwner;

const getTasks = API.getTasks;
const getTask = API.getTask;
const createTask = API.createTask;
const updateTask = API.updateTask;
const deleteTask = API.deleteTask;

const login = API.login;

// ==================== BACKWARD COMPATIBILITY ====================

