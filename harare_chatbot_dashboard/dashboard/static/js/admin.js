// admin.js
document.addEventListener('DOMContentLoaded', function() {
    let currentPage = 1;
    let totalPages = 1;
    let searchTerm = '';

    const tbody = document.getElementById('userTableBody');
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    const pageInfo = document.getElementById('pageInfo');

    // Load users
    function loadUsers(page = 1) {
        const params = new URLSearchParams({
            page: page,
            per_page: 20,
            search: searchTerm
        });
        fetch('/admin/api/users?' + params)
            .then(res => res.json())
            .then(data => {
                renderUsers(data.items);
                currentPage = data.page;
                totalPages = data.pages;
                pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
                prevBtn.disabled = currentPage <= 1;
                nextBtn.disabled = currentPage >= totalPages;
            });
    }

    function renderUsers(users) {
        tbody.innerHTML = '';
        users.forEach(u => {
            const row = tbody.insertRow();
            row.dataset.id = u.id;
            row.addEventListener('click', () => openEditModal(u));

            row.insertCell().textContent = u.username;
            row.insertCell().textContent = u.email;
            row.insertCell().textContent = u.department || '-';
            
            const flagsCell = row.insertCell();
            if (u.can_manage_users) flagsCell.innerHTML += '<span class="flag-badge">Users</span>';
            if (u.can_manage_knowledge) flagsCell.innerHTML += '<span class="flag-badge">Knowledge</span>';
            if (!u.can_manage_users && !u.can_manage_knowledge) flagsCell.textContent = '-';
            
            const statusCell = row.insertCell();
            const statusSpan = document.createElement('span');
            statusSpan.className = `badge ${u.active ? 'active' : 'inactive'}`;
            statusSpan.textContent = u.active ? 'Active' : 'Suspended';
            statusCell.appendChild(statusSpan);
            
            row.insertCell().textContent = u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never';
            
            const actionsCell = row.insertCell();
            const suspendBtn = document.createElement('button');
            suspendBtn.textContent = u.active ? 'Suspend' : 'Activate';
            suspendBtn.onclick = (e) => {
                e.stopPropagation();
                toggleSuspend(u.id, !u.active);
            };
            actionsCell.appendChild(suspendBtn);
        });
    }

    // Open edit modal
    function openEditModal(user) {
        document.getElementById('userId').value = user.id;
        document.getElementById('username').value = user.username;
        document.getElementById('email').value = user.email;
        document.getElementById('department').value = user.department || '';
        document.getElementById('canManageUsers').checked = user.can_manage_users;
        document.getElementById('canManageKnowledge').checked = user.can_manage_knowledge;
        document.getElementById('active').checked = user.active;
        document.getElementById('modalTitle').textContent = 'Edit User';
        document.getElementById('userModal').style.display = 'block';
    }

    // Save user (PUT)
    document.getElementById('userForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const id = document.getElementById('userId').value;
        const data = {
            username: document.getElementById('username').value,
            email: document.getElementById('email').value,
            department: document.getElementById('department').value,
            can_manage_users: document.getElementById('canManageUsers').checked,
            can_manage_knowledge: document.getElementById('canManageKnowledge').checked,
            active: document.getElementById('active').checked
        };
        fetch('/admin/api/users/' + id, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(res => {
            if (res.success) {
                document.getElementById('userModal').style.display = 'none';
                loadUsers(currentPage);
            } else {
                alert('Error: ' + res.error);
            }
        });
    });

    // Reset password
    document.getElementById('resetPasswordBtn').addEventListener('click', function() {
        const id = document.getElementById('userId').value;
        if (confirm('Reset password for this user?')) {
            fetch('/admin/api/users/' + id + '/reset-password', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    alert('New temporary password: ' + data.temp_password);
                    document.getElementById('userModal').style.display = 'none';
                });
        }
    });

    // Toggle suspend
    function toggleSuspend(id, makeActive) {
        fetch('/admin/api/users/' + id + '/suspend', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                loadUsers(currentPage);
            });
    }

    // Create new user
    document.getElementById('newUserBtn').addEventListener('click', function() {
        document.getElementById('createUserModal').style.display = 'block';
    });

    document.getElementById('createUserForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const data = {
            username: document.getElementById('newUsername').value,
            email: document.getElementById('newEmail').value,
            department: document.getElementById('newDepartment').value,
            can_manage_users: document.getElementById('newCanManageUsers').checked,
            can_manage_knowledge: document.getElementById('newCanManageKnowledge').checked
        };
        fetch('/admin/api/users', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(res => {
            if (res.temp_password) {
                document.getElementById('tempPassword').textContent = res.temp_password;
                document.getElementById('tempPasswordDisplay').style.display = 'block';
                document.getElementById('createUserForm').reset();
            } else {
                alert('Error: ' + res.error);
            }
        });
    });

    document.getElementById('closeTempPassword').addEventListener('click', function() {
        document.getElementById('createUserModal').style.display = 'none';
        document.getElementById('tempPasswordDisplay').style.display = 'none';
        loadUsers();
    });

    // Cancel buttons
    document.getElementById('cancelUserBtn').addEventListener('click', () => {
        document.getElementById('userModal').style.display = 'none';
    });
    document.getElementById('cancelCreateBtn').addEventListener('click', () => {
        document.getElementById('createUserModal').style.display = 'none';
    });

    // Search
    document.getElementById('searchBtn').addEventListener('click', function() {
        searchTerm = document.getElementById('searchInput').value;
        loadUsers(1);
    });

    // Pagination
    prevBtn.addEventListener('click', () => loadUsers(currentPage - 1));
    nextBtn.addEventListener('click', () => loadUsers(currentPage + 1));

    // Initial load
    loadUsers();
});