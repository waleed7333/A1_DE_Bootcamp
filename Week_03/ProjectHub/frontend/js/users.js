// Users JavaScript

// Check authentication
if (!localStorage.getItem('token')) {
    window.location.href = 'index.html';
}

let usersData = [];

// Load users on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadUsers();
});

// Load users
async function loadUsers() {
    try {
        usersData = await getUsers() || [];
        renderUsers();
    } catch (error) {
        console.error('Error loading users:', error);
        showToast('Error loading users', 'error');
    }
}

// Render users
function renderUsers() {
    const tableBody = document.getElementById('usersTableBody');
    const tableContainer = document.querySelector('.table-container');
    const emptyState = document.getElementById('emptyState');
    
    if (usersData.length === 0) {
        tableContainer.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }
    
    tableContainer.style.display = 'block';
    emptyState.style.display = 'none';
    
    tableBody.innerHTML = usersData.map(u => {
        const initial = u.username.charAt(0).toUpperCase();
        const isActive = u.is_active !== false;
        
        return `
            <tr>
                <td>
                    <div class="user-cell">
                        <div class="user-avatar">${initial}</div>
                        <div class="user-details">
                            <h4>${escapeHtml(u.username)}</h4>
                        </div>
                    </div>
                </td>
                <td>${escapeHtml(u.email) || '-'}</td>
                <td>
                    <span class="status-badge ${isActive ? 'active' : 'inactive'}">
                        ${isActive ? 'Active' : 'Inactive'}
                    </span>
                </td>
                <td>${formatDate(u.created_at)}</td>
                <td>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn-icon" onclick="editUser(${u.id})" title="Edit">✏️</button>
                        <button class="btn-icon danger" onclick="confirmDeleteUser(${u.id})" title="Delete">🗑️</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// Show add/edit user modal
function showUserModal(userId = null) {
    const modal = document.getElementById('userModal');
    const title = document.getElementById('modalTitle');
    const passwordGroup = document.getElementById('passwordGroup');
    
    // Reset form
    document.getElementById('userForm').reset();
    document.getElementById('userId').value = '';
    
    if (userId) {
        // Edit mode
        const user = usersData.find(u => u.id === userId);
        if (user) {
            title.textContent = 'Edit User';
            document.getElementById('userId').value = user.id;
            document.getElementById('userUsername').value = user.username;
            document.getElementById('userEmail').value = user.email || '';
            passwordGroup.style.display = 'none';
        }
    } else {
        title.textContent = 'Add New User';
        passwordGroup.style.display = 'block';
    }
    
    modal.classList.add('show');
}

// Close user modal
function closeUserModal() {
    document.getElementById('userModal').classList.remove('show');
}

// Save user (create or update)
async function saveUser() {
    const userId = document.getElementById('userId').value;
    const username = document.getElementById('userUsername').value.trim();
    const email = document.getElementById('userEmail').value.trim();
    const password = document.getElementById('userPassword').value;
    
    if (!username) {
        showToast('Please Enter username', 'warning');
        return;
    }
    
    if (!email) {
        showToast('Please Enter email', 'warning');
        return;
    }
    
    const data = {
        username,
        email,
        is_active: true
    };
    
    // Only require password for new users
    if (!userId && !password) {
        showToast('Please Enter password', 'warning');
        return;
    }
    
    if (password) {
        data.password = password;
    }
    
    try {
        if (userId) {
            // Update
            await updateUser(userId, data);
            showToast('User updated successfully', 'success');
        } else {
            // Create
            await createUser(data);
            showToast('User created successfully', 'success');
        }
        
        closeUserModal();
        await loadUsers();
    } catch (error) {
        console.error('Error saving user:', error);
        showToast('Error saving user', 'error');
    }
}

// Edit user
function editUser(userId) {
    showUserModal(userId);
}

// Confirm delete user
function confirmDeleteUser(userId) {
    const user = usersData.find(u => u.id === userId);
    const userName = user ? user.username : 'this user';
    
    confirmDelete(userName, 'user', async () => {
        await deleteUserById(userId);
    });
}

// Delete user
async function deleteUserById(userId) {
    try {
        await deleteUser(userId);
        showToast('User deleted successfully', 'success');
        await loadUsers();
    } catch (error) {
        console.error('Error deleting user:', error);
        showToast('Error deleting user', 'error');
    }
}

