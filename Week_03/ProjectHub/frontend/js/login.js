// Login JavaScript

// Check if already logged in
if (localStorage.getItem('token')) {
    window.location.href = 'dashboard.html';
}

document.getElementById("loginForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const username = document.getElementById("username").value; 
    const password = document.getElementById("password").value;
    const errorDiv = document.getElementById("loginError");
    const submitBtn = this.querySelector('.btn-login');

    // Clear previous errors
    errorDiv.classList.remove('show');
    errorDiv.textContent = '';
    
    // Disable button during login
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="loading-spinner"></span> Signing In...';

    try {
        const apiUrl = "http://127.0.0.1:8000";
        
        const response = await fetch(apiUrl + "/auth/login", {
            method: "POST",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json" 
            },
            body: JSON.stringify({
                "username": username,
                "password": password
            })
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem("token", data.access_token);
            
            // Show success and redirect
            showToast("Logged in successfully", "success");
            
            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = "dashboard.html"; 
            }, 500);
        } else {
            const errorData = await response.json();
            errorDiv.textContent = errorData.detail || "Invalid Username or Password";
            errorDiv.classList.add('show');
        }
    } catch (error) {
        console.error("Connection Error:", error);
        errorDiv.textContent = "Could not connect to server. Please check your connection.";
        errorDiv.classList.add('show');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Sign In</span>';
    }
});

// Toast notification function
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        const newContainer = document.createElement('div');
        newContainer.className = 'toast-container';
        newContainer.id = 'toastContainer';
        document.body.appendChild(newContainer);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
    `;
    
    document.getElementById('toastContainer').appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

