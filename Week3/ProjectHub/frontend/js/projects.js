// Projects JavaScript

// Check authentication
if (!localStorage.getItem('token')) {
    window.location.href = 'index.html';
}

let projectsData = [];
let usersData = [];

// Load projects on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadProjects();
});

// Load projects
async function loadProjects() {
    try {
        const [projects, users] = await Promise.all([getProjects(), getUsers()]);
        projectsData = projects || [];
        usersData = users || [];
        
        renderProjects();
    } catch (error) {
        console.error('Error loading projects:', error);
        showToast('Error loading projects', 'error');
    }
}

// Render projects
function renderProjects() {
    const grid = document.getElementById('projectsGrid');
    const emptyState = document.getElementById('emptyState');
    
    if (projectsData.length === 0) {
        grid.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }
    
    grid.style.display = 'grid';
    emptyState.style.display = 'none';
    
    grid.innerHTML = projectsData.map(p => {
        const owner = usersData.find(u => u.id === p.owner_id);
        const ownerName = owner ? owner.username : 'Unassigned';
        const ownerInitial = ownerName.charAt(0);
        
        return `
            <div class="project-card">
                <div class="project-card-header">
                    <span class="project-card-badge badge-active">Active</span>
                    <div class="project-actions">
                        <button class="btn-icon" onclick="viewProject(${p.id})" title="View">👁️</button>
                        <button class="btn-icon" onclick="editProject(${p.id})" title="Edit">✏️</button>
                        <button class="btn-icon danger" onclick="confirmDeleteProject(${p.id})" title="Delete">🗑️</button>
                    </div>
                </div>
                <div class="project-card-body">
                    <h3 class="project-card-title">${escapeHtml(p.title)}</h3>
                    <p class="project-card-desc">${escapeHtml(p.description) || 'No description'}</p>
                    <div class="project-card-meta">
                        <div class="meta-item">
                            <span class="icon">📅</span>
                            <span>${formatDate(p.created_at)}</span>
                        </div>
                    </div>
                </div>
                <div class="project-card-footer">
                    <div class="project-owner">
                        <div class="project-owner-avatar">${ownerInitial}</div>
                        <span class="project-owner-name">${escapeHtml(ownerName)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Show add project modal
async function showProjectModal(projectId = null) {
    const modal = document.getElementById('projectModal');
    const title = document.getElementById('modalTitle');
    const ownerSelect = document.getElementById('projectOwner');
    
    // Reset form
    document.getElementById('projectForm').reset();
    document.getElementById('projectId').value = '';
    
    // Load users for owner select
    ownerSelect.innerHTML = '<option value="">Select Owner</option>' + 
        usersData.map(u => `<option value="${u.id}">${escapeHtml(u.username)}</option>`).join('');
    
    if (projectId) {
        // Edit mode
        const project = projectsData.find(p => p.id === projectId);
        if (project) {
            title.textContent = 'Edit Project';
            document.getElementById('projectId').value = project.id;
            document.getElementById('projectTitle').value = project.title;
            document.getElementById('projectDescription').value = project.description || '';
            document.getElementById('projectOwner').value = project.owner_id;
        }
    } else {
        title.textContent = 'Add New Project';
    }
    
    modal.classList.add('show');
}

// Close project modal
function closeProjectModal() {
    document.getElementById('projectModal').classList.remove('show');
}

// Save project (create or update)
async function saveProject() {
    const projectId = document.getElementById('projectId').value;
    const title = document.getElementById('projectTitle').value.trim();
    const description = document.getElementById('projectDescription').value.trim();
    const ownerId = document.getElementById('projectOwner').value;
    
    if (!title) {
        showToast('Please enter project title', 'warning');
        return;
    }
    
    if (!ownerId) {
        showToast('Please select project owner', 'warning');
        return;
    }
    
    const data = {
        title,
        description,
        owner_id: parseInt(ownerId)
    };
    
    try {
        if (projectId) {
            // Update
            await updateProject(projectId, data);
            showToast('Project updated successfully', 'success');
        } else {
            // Create
            await createProject(data);
            showToast('Project created successfully', 'success');
        }
        
        closeProjectModal();
        await loadProjects();
    } catch (error) {
        console.error('Error saving project:', error);
        showToast('Error saving project', 'error');
    }
}

// Edit project
function editProject(projectId) {
    showProjectModal(projectId);
}

// View project details
async function viewProject(projectId) {
    const project = projectsData.find(p => p.id === projectId);
    if (!project) return;
    
    const owner = usersData.find(u => u.id === project.owner_id);
    
    // Get project tasks
    let projectTasks = [];
    try {
        projectTasks = await getProjectTasks(projectId);
    } catch (e) {
        console.log('Could not load project tasks');
    }
    
    const content = document.getElementById('projectDetailContent');
    content.innerHTML = `
        <div class="project-detail-header">
            <div>
                <h2 class="project-detail-title">${escapeHtml(project.title)}</h2>
                <p class="project-detail-desc">${escapeHtml(project.description) || 'No description'}</p>
            </div>
            <span class="project-card-badge badge-active">Active</span>
        </div>
        
        <div class="project-detail-section">
            <h4>Project Owner</h4>
            <div class="project-detail-owner">
                <div class="project-owner-avatar">${owner ? owner.username.charAt(0) : '?'}</div>
                <div>
                    <strong>${escapeHtml(owner ? owner.username : 'Unassigned')}</strong>
                    <br><small style="color: var(--text-muted)">${owner ? owner.email : ''}</small>
                </div>
            </div>
        </div>
        
        <div class="project-detail-section">
            <h4>Tasks (${projectTasks.length})</h4>
            ${projectTasks.length > 0 ? `
                <ul class="project-tasks-list">
                    ${projectTasks.map(t => `
                        <li class="project-task-item">
                            <span>${t.status === 'completed' ? '✅' : '⏳'}</span>
                            <span>${escapeHtml(t.title)}</span>
                        </li>
                    `).join('')}
                </ul>
            ` : '<p style="color: var(--text-muted)">No tasks for this project</p>'}
        </div>
        
        <div class="project-detail-section">
            <h4>Additional Info</h4>
            <p style="color: var(--text-muted)">Created: ${formatDate(project.created_at)}</p>
        </div>
    `;
    
    document.getElementById('projectDetailModal').classList.add('show');
}

// Close project detail modal
function closeProjectDetailModal() {
    document.getElementById('projectDetailModal').classList.remove('show');
}

// Confirm delete project
function confirmDeleteProject(projectId) {
    const project = projectsData.find(p => p.id === projectId);
    const projectName = project ? project.title : 'this project';
    
    confirmDelete(projectName, 'project', async () => {
        await deleteProjectById(projectId);
    });
}

// Delete project
async function deleteProjectById(projectId) {
    try {
        await deleteProject(projectId);
        showToast('Project deleted successfully', 'success');
        await loadProjects();
    } catch (error) {
        console.error('Error deleting project:', error);
        showToast('Error deleting project', 'error');
    }
}

