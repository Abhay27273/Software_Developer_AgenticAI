# 🎨 UI Implementation - Lucide-Style Icons

## Your Icon Preferences (Adapted for HTML/JS)

Since your UI is HTML/JavaScript (not React), I'll use Font Awesome icons that match your Lucide preferences:

### Icon Mapping (Lucide → Font Awesome)

```javascript
const AKINO_ICONS = {
    // Agent Personas
    pm: {
        icon: 'fa-bullseye',           // Target
        color: '#9333ea',              // purple-600
        bg: '#faf5ff',                 // purple-50
        label: 'Project Manager'
    },
    dev: {
        icon: 'fa-terminal',           // Terminal
        color: '#2563eb',              // blue-600
        bg: '#eff6ff',                 // blue-50
        label: 'Developer'
    },
    qa: {
        icon: 'fa-bug',                // Bug
        color: '#ea580c',              // orange-600
        bg: '#fff7ed',                 // orange-50
        label: 'QA Engineer'
    },
    ops: {
        icon: 'fa-server',             // Server
        color: '#475569',              // slate-600
        bg: '#f8fafc',                 // slate-50
        label: 'DevOps'
    },
    
    // Status States
    idle: {
        icon: 'fa-circle-notch',       // CircleDashed
        color: '#94a3b8',              // slate-400
        label: 'Idle'
    },
    active: {
        icon: 'fa-chart-line',         // Activity
        color: '#3b82f6',              // blue-500
        label: 'Active',
        animate: 'fa-pulse'
    },
    complete: {
        icon: 'fa-check-circle',       // CheckCircle2
        color: '#059669',              // emerald-600
        label: 'Complete'
    },
    error: {
        icon: 'fa-times-circle',       // XCircle
        color: '#dc2626',              // red-600
        label: 'Error'
    },
    warning: {
        icon: 'fa-exclamation-triangle', // AlertTriangle
        color: '#d97706',              // amber-600
        label: 'Warning'
    },
    
    // Actions
    creating: {
        icon: 'fa-sparkles',           // Sparkles
        color: '#4f46e5',              // indigo-600
        label: 'Creating'
    },
    building: {
        icon: 'fa-hammer',             // Hammer
        color: '#57534e',              // stone-600
        label: 'Building'
    },
    testing: {
        icon: 'fa-flask',              // TestTube2
        color: '#db2777',              // pink-600
        label: 'Testing'
    },
    deploying: {
        icon: 'fa-rocket',             // Rocket
        color: '#0891b2',              // cyan-600
        label: 'Deploying'
    },
    analyzing: {
        icon: 'fa-brain',              // BrainCircuit
        color: '#7c3aed',              // violet-600
        label: 'Analyzing'
    },
    
    // Files
    file: {
        icon: 'fa-file',               // File
        color: '#64748b',              // slate-500
        label: 'File'
    },
    folder: {
        icon: 'fa-folder',             // Folder
        color: '#60a5fa',              // blue-400
        label: 'Folder'
    },
    code: {
        icon: 'fa-file-code',          // FileCode
        color: '#0284c7',              // sky-600
        label: 'Source'
    },
    config: {
        icon: 'fa-cog',                // Settings
        color: '#475569',              // slate-600
        label: 'Config'
    },
    docs: {
        icon: 'fa-book-open',          // BookOpen
        color: '#0d9488',              // teal-600
        label: 'Docs'
    },
    
    // Progress
    progress: {
        icon: 'fa-spinner',            // Loader2
        color: '#2563eb',              // blue-600
        label: 'Processing',
        animate: 'fa-spin'
    },
    pending: {
        icon: 'fa-hourglass-half',     // Hourglass
        color: '#d97706',              // amber-600
        label: 'Pending',
        animate: 'fa-pulse'
    },
    success: {
        icon: 'fa-check-circle',       // CheckCircle2
        color: '#059669',              // emerald-600
        label: 'Success'
    },
    failed: {
        icon: 'fa-times-circle',       // XCircle
        color: '#dc2626',              // red-600
        label: 'Failed'
    }
};
```

## Implementation Steps

### Step 1: Update Font Awesome CDN (Already in your HTML)

Your HTML already has Font Awesome 6, which is perfect!

### Step 2: Create Icon Helper Functions

Add this to your JavaScript section in `templates/index.html`:

```javascript
// Icon Helper Functions
function getIconHTML(type, size = 16, extraClasses = '') {
    const config = AKINO_ICONS[type] || AKINO_ICONS.idle;
    const animate = config.animate || '';
    return `<i class="fas ${config.icon} ${animate} ${extraClasses}" 
               style="color: ${config.color}; font-size: ${size}px;"></i>`;
}

function getAgentIcon(agentType, status = null) {
    const agentConfig = AKINO_ICONS[agentType];
    const statusConfig = status ? AKINO_ICONS[status] : null;
    
    if (statusConfig) {
        return `${getIconHTML(agentType, 18)} ${getIconHTML(status, 14)}`;
    }
    return getIconHTML(agentType, 18);
}

function createStatusBadge(type, label = null, size = 'md') {
    const config = AKINO_ICONS[type];
    const displayLabel = label || config.label;
    const padding = size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm';
    
    return `
        <span class="inline-flex items-center gap-2 rounded-full border shadow-sm ${padding}"
              style="background-color: ${config.bg}; border-color: ${config.color}20;">
            ${getIconHTML(type, size === 'sm' ? 14 : 16)}
            <span style="color: ${config.color}; font-weight: 600;">${displayLabel}</span>
        </span>
    `;
}
```

### Step 3: Update Akino Branding

Replace the sidebar header section with:

```html
<!-- Akino Branding -->
<div class="akino-brand">
    <div class="akino-avatar-main">
        <div class="akino-logo-circle">
            <span class="akino-letter">A</span>
            <div class="akino-pulse-ring"></div>
        </div>
    </div>
    <div class="akino-brand-text">
        <h1 class="akino-name">Akino</h1>
        <p class="akino-tagline">AI Development Assistant</p>
    </div>
</div>
```

### Step 4: Update Agent Messages

Find and replace in your WebSocket message handlers:

```javascript
// OLD
this.addChatMessage('🤖 **PM Agent**: Starting analysis...', 'ai');

// NEW
this.addChatMessage(`${getAgentIcon('pm', 'active')} **Akino PM**: Starting analysis...`, 'ai');

// OLD
this.addChatMessage('🧪 **QA Agent**: Testing file...', 'ai');

// NEW
this.addChatMessage(`${getAgentIcon('qa', 'testing')} **Akino QA**: Testing file...`, 'ai');

// OLD
this.addChatMessage('🚀 **Ops Agent**: Deploying...', 'ai');

// NEW
this.addChatMessage(`${getAgentIcon('ops', 'deploying')} **Akino Ops**: Deploying...`, 'ai');
```

### Step 5: Update File Tree Icons

```javascript
function renderFileItem(item, level = 0) {
    const indent = level * 20;
    const iconType = item.type === 'directory' ? 'folder' : getFileIconType(item.name);
    const icon = getIconHTML(iconType, 16);
    
    return `
        <div class="file-item" style="padding-left: ${indent}px;" 
             data-path="${item.path}" data-type="${item.type}">
            ${icon}
            <span class="file-name">${item.name}</span>
        </div>
    `;
}

function getFileIconType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'py': 'code',
        'js': 'code',
        'ts': 'code',
        'jsx': 'code',
        'tsx': 'code',
        'json': 'config',
        'yml': 'config',
        'yaml': 'config',
        'md': 'docs',
        'txt': 'docs'
    };
    return iconMap[ext] || 'file';
}
```

### Step 6: Update PM Agent Progress Bar

```javascript
function renderPMProgressBar(stats) {
    const { total, pending, inProgress, completed, failed } = stats;
    const percentage = total > 0 ? (completed / total) * 100 : 0;
    
    return `
        <div class="pm-progress-container">
            <div class="pm-progress-header">
                <span class="pm-progress-label">
                    ${getIconHTML('progress', 16)} Project Progress
                </span>
                <span class="pm-progress-text">${completed}/${total} tasks (${Math.round(percentage)}%)</span>
            </div>
            <div class="pm-progress-bar-bg">
                <div class="pm-progress-bar-fill" style="width: ${percentage}%; background: ${getProgressColor(percentage)}"></div>
            </div>
            <div class="pm-progress-stats">
                <span class="pm-stat">${getIconHTML('pending', 14)} Pending: ${pending}</span>
                <span class="pm-stat">${getIconHTML('active', 14)} In Progress: ${inProgress}</span>
                <span class="pm-stat">${getIconHTML('complete', 14)} Complete: ${completed}</span>
                ${failed > 0 ? `<span class="pm-stat">${getIconHTML('failed', 14)} Failed: ${failed}</span>` : ''}
            </div>
        </div>
    `;
}

function getProgressColor(percentage) {
    if (percentage < 30) return 'linear-gradient(90deg, #f093fb 0%, #f5576c 100%)';
    if (percentage < 70) return 'linear-gradient(90deg, #ffd89b 0%, #19547b 100%)';
    return 'linear-gradient(90deg, #43e97b 0%, #38f9d7 100%)';
}
```

### Step 7: Update Agent Tabs

```javascript
function renderAgentTabs() {
    const agents = ['pm', 'dev', 'qa', 'ops'];
    return agents.map(agent => {
        const config = AKINO_ICONS[agent];
        return `
            <button class="agent-tab" data-agent="${agent}">
                ${getIconHTML(agent, 18)}
                <span>${config.label}</span>
            </button>
        `;
    }).join('');
}
```

## Complete Implementation File

Would you like me to create a complete updated `index.html` file with all these changes applied? I can:

1. Keep your existing HTML structure
2. Replace all emojis with Font Awesome icons matching your Lucide preferences
3. Add the Akino branding
4. Fix the progress bar
5. Add file tree filtering
6. Update all agent messages

Just say "yes" and I'll create the complete updated file!
