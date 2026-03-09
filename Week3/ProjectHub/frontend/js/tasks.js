// Tasks JavaScript

// Check authentication
if (!localStorage.getItem('token')) {
    window.location.href = 'index.html';
}

let tasksData = [];
let projectsData = [];

// Load tasks on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadTasks();
});

// Load tasks
async function loadTasks() {
    try {
        const [tasks, projects] = await Promise.all([getTasks(), getProjects()]);
        tasksData = tasks || [];
        projectsData = projects || [];
        
        renderTasks();
    } catch (error) {
        console.error('Error loading tasks:', error);
        showToast('Error loading tasks', 'error');
    }
}

// Render tasks
function renderTasks() {
    const list = document.getElementById('tasksList');
    const emptyState = document.getElementById('emptyState');
    
    if (tasksData.length === 0) {
        list.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }
    
    list.style.display = 'flex';
    emptyState.style.display = 'none';
    
    list.innerHTML = tasksData.map(t => {
        const project = projectsData.find(p => p.id === t.project_id);
        const projectName = project ? project.title : 'Unassigned';
        
        const statusClass = t.status === 'completed' ? 'completed' : 
                          t.status === 'in_progress' ? 'progress' : 'pending';
        const statusText = t.status === 'completed' ? 'Completed' : 
                          t.status === 'in_progress' ? 'In Progress' : 'Pending';
        
        return `
            <div class="task-card">
                <div class="task-checkbox ${t.status === 'completed' ? 'completed' : ''}" 
                     onclick="toggleTaskStatus(${t.id}, '${t.status}')">
                    ${t.status === 'completed' ? '✓' : ''}
                </div>
                <div class="task-content">
                    <div class="task-title ${t.status === 'completed' ? 'completed' : ''}">${escapeHtml(t.title)}</div>
                    <div class="task-meta">
                        <span>📁 ${escapeHtml(projectName)}</span>
                        <span>📅 ${formatDate(t.created_at)}</span>
                    </div>
                </div>
                <span class="task-status status-${statusClass}">${statusText}</span>
                <div class="task-actions">
                    <button class="btn-icon" onclick="editTask(${t.id})" title="Edit">✏️</button>
                    <button class="btn-icon danger" onclick="confirmDeleteTask(${t.id})" title="Delete">🗑️</button>
                </div>
            </div>
        `;
    }).join('');
}

// Toggle task status
async function toggleTaskStatus(taskId, currentStatus) {
    const newStatus = currentStatus === 'completed' ? 'pending' : 'completed';
    
    try {
        await updateTask(taskId, { status: newStatus });
        showToast('Task status updated', 'success');
        await loadTasks();
    } catch (error) {
        console.error('Error updating task:', error);
        showToast('Error updating task', 'error');
    }
}

// Show add/edit task modal
async function showTaskModal(taskId = null) {
    const modal = document.getElementById('taskModal');
    const title = document.getElementById('modalTitle');
    const projectSelect = document.getElementById('taskProject');
    
    // Reset form
    document.getElementById('taskForm').reset();
    document.getElementById('taskId').value = '';
    
    // Load projects
    projectSelect.innerHTML = '<option value="">Select Project</option>' + 
        projectsData.map(p => `<option value="${p.id}">${escapeHtml(p.title)}</option>`).join('');
    
    if (taskId) {
        // Edit mode
        const task = tasksData.find(t => t.id === taskId);
        if (task) {
            title.textContent = 'Edit Task';
            document.getElementById('taskId').value = task.id;
            document.getElementById('taskTitle').value = task.title;
            document.getElementById('taskDescription').value = task.description || '';
            document.getElementById('taskProject').value = task.project_id;
            document.getElementById('taskStatus').value = task.status || 'pending';
        }
    } else {
        title.textContent = 'Add New Task';
    }
    
    modal.classList.add('show');
}

// Close task modal
function closeTaskModal() {
    document.getElementById('taskModal').classList.remove('show');
}

// Save task (create or update)
async function saveTask() {
    const taskId = document.getElementById('taskId').value;
    const title = document.getElementById('taskTitle').value.trim();
    const description = document.getElementById('taskDescription').value.trim();
    const projectId = document.getElementById('taskProject').value;
    const status = document.getElementById('taskStatus').value;
    
    if (!title) {
        showToast('Please enter task title', 'warning');
        return;
    }
    
    if (!projectId) {
        showToast('Please select project', 'warning');
        return;
    }
    
    const data = {
        title,
        description,
        project_id: parseInt(projectId),
        status
    };
    
    try {
        if (taskId) {
            // Update
            await updateTask(taskId, data);
            showToast('Task updated successfully', 'success');
        } else {
            // Create
            await createTask(data);
            showToast('Task created successfully', 'success');
        }
        
        closeTaskModal();
        await loadTasks();
    } catch (error) {
        console.error('Error saving task:', error);
        showToast('Error saving task', 'error');
    }
}

// Edit task
function editTask(taskId) {
    showTaskModal(taskId);
}

// Confirm delete task
function confirmDeleteTask(taskId) {
    const task = tasksData.find(t => t.id === taskId);
    const taskName = task ? task.title : 'this task';
    
    confirmDelete(taskName, 'task', async () => {
        await deleteTaskById(taskId);
    });
}

// Delete task
async function deleteTaskById(taskId) {
    try {
        await deleteTask(taskId);
        showToast('Task deleted successfully', 'success');
        await loadTasks();
    } catch (error) {
        console.error('Error deleting task:', error);
        showToast('Error deleting task', 'error');
    }
}

