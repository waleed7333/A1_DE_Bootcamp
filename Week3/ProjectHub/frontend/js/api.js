// ==================== API MODULE ====================
// Functions are already exported globally in config.js
// This file provides backward compatibility for any code that loads api.js directly

// Make available globally (in case config.js wasn't loaded first)
if (typeof window !== 'undefined') {
    // Users - use API object from config.js
    window.getUsers = API.getUsers;
    window.getUser = API.getUser;
    window.createUser = API.createUser;
    window.updateUser = API.updateUser;
    window.deleteUser = API.deleteUser;

    // Projects
    window.getProjects = API.getProjects;
    window.getProject = API.getProject;
    window.createProject = API.createProject;
    window.updateProject = API.updateProject;
    window.deleteProject = API.deleteProject;
    window.getProjectTasks = API.getProjectTasks;
    window.getProjectOwner = API.getProjectOwner;

    // Tasks
    window.getTasks = API.getTasks;
    window.getTask = API.getTask;
    window.createTask = API.createTask;
    window.updateTask = API.updateTask;
    window.deleteTask = API.deleteTask;
}

