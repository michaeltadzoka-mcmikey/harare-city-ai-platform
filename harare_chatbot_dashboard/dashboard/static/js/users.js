// users.js - User management for Harare Municipal Dashboard

let currentUsers = [];
let filteredUsers = [];
let currentTempPassword = '';

document.addEventListener('DOMContentLoaded', function () {
    loadUsers();

    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
        statusFilter.addEventListener('change', filterUsers);
    }

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterUsers, 300));
    }

    const newUserBtn = document.getElementById('newUserBtn');
    if (newUserBtn) {
        newUserBtn.addEventListener('click', showCreateModal);
    }
});

async function loadUsers() {
    const tbody = document.getElementById('userTableBody');
    if (!tbody) {
        console.error('Table body element not found');
        return;
    }

    tbody.innerHTML = '<tr><td colspan="8" class="loading">Loading users...</td></tr>';

    try {
        const response = await fetch('/users/api/list');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load users');
        }

        currentUsers = data.users || [];
        filterUsers();
    } catch (error) {
        console.error('Error loading users:', error);
        tbody.innerHTML = '<tr><td colspan="8" class="error">Failed to load users</td></tr>';
    }
}

function filterUsers() {
    const statusFilter = document.getElementById('statusFilter');
    const searchInput = document.getElementById('searchInput');
    if (!statusFilter || !searchInput) return;

    const status = statusFilter.value;
    const searchTerm = searchInput.value.toLowerCase();

    filteredUsers = currentUsers.filter(user => {
        if (status === 'active' && !user.is_active) return false;
        if (status === 'suspended' && user.is_active) return false;
        if (searchTerm) {
            return (user.username && user.username.toLowerCase().includes(searchTerm)) ||
                (user.name && user.name.toLowerCase().includes(searchTerm)) ||
                (user.email && user.email.toLowerCase().includes(searchTerm));
        }
        return true;
    });

    displayUsers(filteredUsers);
}

function displayUsers(users) {
    const tbody = document.getElementById('userTableBody');
    if (!tbody) return;

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No users found</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(user => {
        const flags = [];
        if (user.can_manage_users) flags.push('<span class="flag-badge">Manage Users</span>');
        if (user.can_manage_knowledge) flags.push('<span class="flag-badge">Manage Knowledge</span>');
        const flagsHtml = flags.length ? flags.join(' ') : '<span class="flag-badge read-only">Read‑Only</span>';

        const statusClass = user.is_active ? 'status-active' : 'status-suspended';
        const statusText = user.is_active ? 'Active' : 'Suspended';

        const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString() : '-';

        return `
            <tr>
                <td>${escapeHtml(user.username)}</td>
                <td>${escapeHtml(user.email)}</td>
                <td>${escapeHtml(user.name || '-')}</td>
                <td>${escapeHtml(user.department ? user.department.replace(/_/g, ' ') : '-')}</td>
                <td>${flagsHtml}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td>${lastLogin}</td>
                <td>
                    <button class="action-btn edit" onclick="editUser(${user.id})" title="Edit user">Edit</button>
                    <button class="action-btn reset" onclick="showResetConfirm(${user.id}, '${escapeHtml(user.name || user.username)}')" title="Reset password">Reset</button>
                    ${user.is_active ?
                `<button class="action-btn suspend" onclick="showSuspendConfirm(${user.id}, '${escapeHtml(user.name || user.username)}')" title="Suspend user">Suspend</button>` :
                `<button class="action-btn reactivate" onclick="showReactivateConfirm(${user.id}, '${escapeHtml(user.name || user.username)}')" title="Reactivate user">Reactivate</button>`
            }
                </td>
            </tr>
        `;
    }).join('');
}

function escapeHtml(unsafe) {
    if (!unsafe) return unsafe;
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showCreateModal() {
    const modal = document.getElementById('userModal');
    if (!modal) {
        console.error('User modal not found');
        return;
    }

    document.getElementById('modalTitle').textContent = 'Create New User';
    document.getElementById('userId').value = '';
    document.getElementById('username').value = '';
    document.getElementById('username').disabled = false;
    document.getElementById('email').value = '';
    document.getElementById('name').value = '';
    document.getElementById('department').value = '';
    // Show password field and make it required
    document.getElementById('passwordField').style.display = 'block';
    document.getElementById('password').required = true;
    document.getElementById('password').value = '';
    document.getElementById('canManageUsers').checked = false;
    document.getElementById('canManageKnowledge').checked = false;
    document.getElementById('statusGroup').style.display = 'none';

    modal.style.display = 'block';
}

function editUser(userId) {
    const user = currentUsers.find(u => u.id === userId);
    if (!user) {
        console.error('User not found');
        return;
    }

    const modal = document.getElementById('userModal');
    if (!modal) return;

    document.getElementById('modalTitle').textContent = 'Edit User';
    document.getElementById('userId').value = user.id;
    document.getElementById('username').value = user.username;
    document.getElementById('username').disabled = true;
    document.getElementById('email').value = user.email;
    document.getElementById('name').value = user.name || '';
    document.getElementById('department').value = user.department || '';
    // Hide password field and remove required
    document.getElementById('passwordField').style.display = 'none';
    document.getElementById('password').required = false;
    document.getElementById('canManageUsers').checked = user.can_manage_users;
    document.getElementById('canManageKnowledge').checked = user.can_manage_knowledge;
    document.getElementById('isActive').value = user.is_active ? 'true' : 'false';
    document.getElementById('statusGroup').style.display = 'block';

    modal.style.display = 'block';
}

function closeModal() {
    document.getElementById('userModal').style.display = 'none';
}

async function saveUser(event) {
    event.preventDefault();

    const userId = document.getElementById('userId').value;
    const isEdit = userId !== '';

    const userData = {
        username: document.getElementById('username').value,
        email: document.getElementById('email').value,
        name: document.getElementById('name').value,
        department: document.getElementById('department').value,
        can_manage_users: document.getElementById('canManageUsers').checked,
        can_manage_knowledge: document.getElementById('canManageKnowledge').checked
    };

    if (!isEdit) {
        // Include password only for creation
        const password = document.getElementById('password').value;
        if (!password || password.length < 8) {
            alert('Password must be at least 8 characters');
            return;
        }
        userData.password = password;
    } else {
        userData.is_active = document.getElementById('isActive').value === 'true';
    }

    try {
        const url = isEdit ? `/users/api/user/${userId}` : '/users/api/user';
        const method = isEdit ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to save user');
        }

        closeModal();
        loadUsers();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

let resetUserId = null;

function showResetConfirm(userId, userName) {
    resetUserId = userId;
    document.getElementById('resetUserName').textContent = userName;
    document.getElementById('resetConfirmModal').style.display = 'block';
}

function closeResetConfirmModal() {
    document.getElementById('resetConfirmModal').style.display = 'none';
    resetUserId = null;
}

async function confirmResetPassword() {
    if (!resetUserId) return;

    try {
        const response = await fetch(`/users/api/user/${resetUserId}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Reset failed');
        }

        currentTempPassword = data.temp_password;
        document.getElementById('tempPasswordDisplay').textContent = currentTempPassword;
        document.getElementById('passwordModal').style.display = 'block';
        closeResetConfirmModal();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

let suspendUserId = null;

function showSuspendConfirm(userId, userName) {
    suspendUserId = userId;
    document.getElementById('suspendUserName').textContent = userName;
    document.getElementById('suspendConfirmModal').style.display = 'block';
}

function closeSuspendConfirmModal() {
    document.getElementById('suspendConfirmModal').style.display = 'none';
    suspendUserId = null;
}

async function confirmSuspend() {
    if (!suspendUserId) return;

    try {
        const response = await fetch(`/users/api/user/${suspendUserId}/suspend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Suspend failed');
        }

        closeSuspendConfirmModal();
        loadUsers();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

let reactivateUserId = null;

function showReactivateConfirm(userId, userName) {
    reactivateUserId = userId;
    document.getElementById('reactivateUserName').textContent = userName;
    document.getElementById('reactivateConfirmModal').style.display = 'block';
}

function closeReactivateConfirmModal() {
    document.getElementById('reactivateConfirmModal').style.display = 'none';
    reactivateUserId = null;
}

async function confirmReactivate() {
    if (!reactivateUserId) return;

    try {
        const response = await fetch(`/users/api/user/${reactivateUserId}/reactivate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Reactivate failed');
        }

        closeReactivateConfirmModal();
        loadUsers();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function closePasswordModal() {
    document.getElementById('passwordModal').style.display = 'none';
    currentTempPassword = '';
}

function copyPassword() {
    navigator.clipboard.writeText(currentTempPassword).then(() => {
        alert('Password copied to clipboard');
    }).catch(() => {
        alert('Failed to copy');
    });
}

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