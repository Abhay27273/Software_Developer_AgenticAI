# 🎨 UI Improvement Plan - Akino AI Agent System

## Current Issues Identified

1. ❌ **Generic AI emojis** - Using common emojis (🤖, 📁, 📄, etc.)
2. ❌ **"Akino" name not visible** - No clear branding/avatar
3. ❌ **Blank progress bar** in PM Agent panel
4. ❌ **Cluttered file tree** - Shows cache files, config files, etc.
5. ❌ **No project organization** - Past projects mixed with current
6. ❌ **Limited features** - No file upload, image support, etc.

---

## 🎯 Improvement Strategy

### 1. Modern Emoji System (Unique & Professional)

Replace generic emojis with unique, professional icons:

#### Current vs. Proposed Emojis

| Agent/Feature | Current | Proposed | Reasoning |
|--------------|---------|----------|-----------|
| **PM Agent** | 🤖 | 🎯 | Target/goal-oriented planning |
| **Dev Agent** | 🤖 | ⚡ | Fast, powerful development |
| **QA Agent** | 🧪 | 🔍 | Investigation/inspection |
| **Ops Agent** | 🚀 | 🌐 | Global deployment |
| **File Created** | 📄 | ✨ | Magic/creation |
| **Folder** | 📁 | 📦 | Package/module |
| **Success** | ✅ | 💚 | Positive outcome |
| **Error** | ❌ | 🔴 | Alert/attention |
| **Building** | 🔧 | ⚙️ | Process/mechanism |
| **Testing** | 🧪 | 🎪 | Performance/show |
| **Deploying** | 🚀 | 🌊 | Flow/continuous |
| **Repository** | 📦 | 🗂️ | Organization |
| **Progress** | ⏳ | 🔄 | Cycle/iteration |
| **User** | 👤 | 💬 | Communication |
| **Priority** | ⭐ | 🎖️ | Achievement/rank |

#### Advanced Emoji Combinations

```javascript
// Agent Status Indicators
const AGENT_EMOJIS = {
    pm: {
        idle: '🎯',
        active: '🎯✨',
        complete: '🎯💚',
        error: '🎯🔴'
    },
    dev: {
        idle: '⚡',
        active: '⚡💫',
        complete: '⚡💚',
        error: '⚡🔴'
    },
    qa: {
        idle: '🔍',
        active: '🔍🔬',
        complete: '🔍💚',
        error: '🔍🔴'
    },
    ops: {
        idle: '🌐',
        active: '🌐🌊',
        complete: '🌐💚',
        error: '🌐🔴'
    }
};

// File Type Emojis
const FILE_EMOJIS = {
    '.py': '🐍',
    '.js': '📜',
    '.ts': '📘',
    '.html': '🌐',
    '.css': '🎨',
    '.json': '📋',
    '.md': '📝',
    '.yml': '⚙️',
    '.docker': '🐳',
    'folder': '📦'
};
```

---

### 2. Akino Branding & Avatar System

#### Problem: "Akino" name not visible

**Solution**: Create a distinctive avatar/logo system

```html
<!-- Akino Logo Component -->
<div class="akino-avatar">
    <div class="akino-logo">
        <span class="akino-letter">A</span>
        <div class="akino-pulse"></div>
    </div>
    <span class="akino-name">Akino</span>
</div>
```

```css
.akino-avatar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    color: white;
    margin-bottom: 20px;
}

.akino-logo {
    position: relative;
    width: 40px;
    height: 40px;
    background: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.akino-letter {
    font-size: 24px;
    font-weight: 800;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.akino-pulse {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.5);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.1); opacity: 0.5; }
}

.akino-name {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 1px;
}
```

#### Agent Avatars with Unique Icons

```javascript
const AGENT_AVATARS = {
    pm: {
        icon: '🎯',
        name: 'Akino PM',
        color: '#667eea',
        gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    },
    dev: {
        icon: '⚡',
        name: 'Akino Dev',
        color: '#f093fb',
        gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
    },
    qa: {
        icon: '🔍',
        name: 'Akino QA',
        color: '#4facfe',
        gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
    },
    ops: {
        icon: '🌐',
        name: 'Akino Ops',
        color: '#43e97b',
        gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)'
    }
};
```

---

### 3. Fix PM Agent Progress Bar

#### Current Issue: Blank progress bar

**Solution**: Implement real-time progress tracking

```javascript
class ProgressTracker {
    constructor() {
        this.totalTasks = 0;
        this.completedTasks = 0;
        this.progressBar = document.getElementById('pm-progress-bar');
        this.progressText = document.getElementById('pm-progress-text');
    }
    
    updateProgress(completed, total) {
        this.completedTasks = completed;
        this.totalTasks = total;
        
        const percentage = total > 0 ? (completed / total) * 100 : 0;
        
        // Update progress bar
        if (this.progressBar) {
            this.progressBar.style.width = `${percentage}%`;
            this.progressBar.style.background = this.getProgressColor(percentage);
        }
        
        // Update text
        if (this.progressText) {
            this.progressText.textContent = `${completed}/${total} tasks completed (${Math.round(percentage)}%)`;
        }
    }
    
    getProgressColor(percentage) {
        if (percentage < 30) return 'linear-gradient(90deg, #f093fb 0%, #f5576c 100%)';
        if (percentage < 70) return 'linear-gradient(90deg, #ffd89b 0%, #19547b 100%)';
        return 'linear-gradient(90deg, #43e97b 0%, #38f9d7 100%)';
    }
}
```

```html
<!-- Enhanced Progress Bar HTML -->
<div class="pm-progress-container">
    <div class="pm-progress-header">
        <span class="pm-progress-label">🔄 Project Progress</span>
        <span id="pm-progress-text" class="pm-progress-text">0/0 tasks</span>
    </div>
    <div class="pm-progress-bar-container">
        <div id="pm-progress-bar" class="pm-progress-bar" style="width: 0%"></div>
    </div>
    <div class="pm-progress-stats">
        <span id="pm-stats-pending" class="pm-stat">⏳ Pending: 0</span>
        <span id="pm-stats-progress" class="pm-stat">⚡ In Progress: 0</span>
        <span id="pm-stats-complete" class="pm-stat">💚 Complete: 0</span>
    </div>
</div>
```

```css
.pm-progress-container {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.pm-progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.pm-progress-label {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary);
}

.pm-progress-text {
    font-size: 13px;
    color: var(--text-secondary);
    font-weight: 500;
}

.pm-progress-bar-container {
    width: 100%;
    height: 8px;
    background: #f0f0f0;
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 12px;
}

.pm-progress-bar {
    height: 100%;
    border-radius: 999px;
    transition: width 0.3s ease, background 0.3s ease;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
}

.pm-progress-stats {
    display: flex;
    gap: 16px;
    font-size: 12px;
}

.pm-stat {
    display: flex;
    align-items: center;
    gap: 4px;
    color: var(--text-secondary);
}
```

---

### 4. Smart File Tree Filtering

#### Problem: Shows cache, config, and unnecessary files

**Solution**: Implement intelligent filtering

```javascript
class SmartFileTree {
    constructor() {
        this.excludePatterns = [
            '__pycache__',
            '.pytest_cache',
            'node_modules',
            '.git',
            '.venv',
            'venv',
            '.env',
            '.DS_Store',
            '*.pyc',
            '*.log',
            '.cache',
            'dist',
            'build',
            '.next',
            'coverage'
        ];
        
        this.projectOnlyMode = true; // Only show agent-generated projects
    }
    
    shouldExcludeFile(path) {
        return this.excludePatterns.some(pattern => {
            if (pattern.includes('*')) {
                const regex = new RegExp(pattern.replace('*', '.*'));
                return regex.test(path);
            }
            return path.includes(pattern);
        });
    }
    
    filterFileTree(tree) {
        if (this.projectOnlyMode) {
            // Only show files in generated_code/projects/
            return this.filterProjectsOnly(tree);
        }
        
        return tree.filter(item => {
            if (this.shouldExcludeFile(item.path)) {
                return false;
            }
            
            if (item.type === 'directory' && item.children) {
                item.children = this.filterFileTree(item.children);
                return item.children.length > 0;
            }
            
            return true;
        });
    }
    
    filterProjectsOnly(tree) {
        // Find the projects directory
        const projectsDir = tree.find(item => 
            item.name === 'projects' && item.type === 'directory'
        );
        
        if (!projectsDir) return [];
        
        // Return only current and archived projects
        return projectsDir.children.filter(item => 
            item.name === 'current' || item.name === 'archived'
        );
    }
}
```

#### File Tree UI with Toggle

```html
<div class="file-tree-header">
    <h3>📦 Projects</h3>
    <div class="file-tree-controls">
        <button id="toggle-filter" class="icon-btn" title="Toggle filter">
            <i class="fas fa-filter"></i>
        </button>
        <button id="refresh-tree" class="icon-btn" title="Refresh">
            <i class="fas fa-sync-alt"></i>
        </button>
    </div>
</div>
<div class="file-tree-filter-status">
    <span id="filter-status">🎯 Showing: Projects only</span>
</div>
<div id="file-tree" class="file-tree"></div>
```

---

### 5. Project Organization System

#### Problem: Past projects mixed with current

**Solution**: Hierarchical project structure

```
generated_code/
├── projects/
│   ├── current/           # Active project
│   │   ├── src/
│   │   ├── tests/
│   │   └── README.md
│   └── archived/          # Past projects
│       ├── 2024-11-20_game-engine/
│       ├── 2024-11-19_api-service/
│       └── 2024-11-18_dashboard/
├── cache/                 # Cached data (hidden from tree)
│   ├── llm_responses/
│   └── qa_results/
└── templates/             # Template library (separate section)
    ├── rest-api-fastapi/
    └── web-app-react/
```

#### UI Implementation

```html
<div class="sidebar-section">
    <div class="sidebar-section-header">
        <h3>📦 Current Project</h3>
        <button id="new-project-btn" class="icon-btn">
            <i class="fas fa-plus"></i>
        </button>
    </div>
    <div id="current-project-info" class="current-project-card">
        <!-- Dynamic content -->
    </div>
</div>

<div class="sidebar-section">
    <div class="sidebar-section-header">
        <h3>🗂️ Past Projects</h3>
        <button id="toggle-archived" class="icon-btn">
            <i class="fas fa-chevron-down"></i>
        </button>
    </div>
    <div id="archived-projects-list" class="archived-projects-list">
        <!-- Dynamic content -->
    </div>
</div>
```

---

### 6. Cache Management & AWS Integration

#### Local Cache Structure

```javascript
class CacheManager {
    constructor() {
        this.cacheDir = 'generated_code/cache/';
        this.maxCacheSize = 100 * 1024 * 1024; // 100MB
        this.maxCacheAge = 7 * 24 * 60 * 60 * 1000; // 7 days
    }
    
    async saveLLMResponse(key, response) {
        const cacheFile = `${this.cacheDir}llm_responses/${key}.json`;
        await this.writeCache(cacheFile, {
            response,
            timestamp: Date.now(),
            size: JSON.stringify(response).length
        });
    }
    
    async saveQAResult(taskId, result) {
        const cacheFile = `${this.cacheDir}qa_results/${taskId}.json`;
        await this.writeCache(cacheFile, {
            result,
            timestamp: Date.now()
        });
    }
    
    async cleanOldCache() {
        const now = Date.now();
        const cacheFiles = await this.listCacheFiles();
        
        for (const file of cacheFiles) {
            const stats = await this.getFileStats(file);
            if (now - stats.timestamp > this.maxCacheAge) {
                await this.deleteFile(file);
            }
        }
    }
}
```

#### AWS S3 Integration for Cache

```python
# In config.py
AWS_S3_CACHE_BUCKET = os.getenv("AWS_S3_CACHE_BUCKET", "akino-cache")
AWS_S3_PROJECTS_BUCKET = os.getenv("AWS_S3_PROJECTS_BUCKET", "akino-projects")

# In utils/aws_cache.py
import boto3
from pathlib import Path

class AWSCacheManager:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.cache_bucket = AWS_S3_CACHE_BUCKET
        self.projects_bucket = AWS_S3_PROJECTS_BUCKET
    
    def upload_cache(self, local_path: Path, s3_key: str):
        """Upload cache files to S3"""
        self.s3.upload_file(
            str(local_path),
            self.cache_bucket,
            s3_key,
            ExtraArgs={'StorageClass': 'INTELLIGENT_TIERING'}
        )
    
    def upload_project(self, project_dir: Path, project_name: str):
        """Upload archived project to S3"""
        for file_path in project_dir.rglob('*'):
            if file_path.is_file():
                s3_key = f"{project_name}/{file_path.relative_to(project_dir)}"
                self.s3.upload_file(
                    str(file_path),
                    self.projects_bucket,
                    s3_key
                )
    
    def download_project(self, project_name: str, local_dir: Path):
        """Download archived project from S3"""
        paginator = self.s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.projects_bucket, Prefix=project_name):
            for obj in page.get('Contents', []):
                s3_key = obj['Key']
                local_file = local_dir / s3_key
                local_file.parent.mkdir(parents=True, exist_ok=True)
                self.s3.download_file(self.projects_bucket, s3_key, str(local_file))
```

---

### 7. Advanced UI Features

#### Feature 1: File Upload Support

```html
<div class="input-attachments">
    <button id="attach-file-btn" class="attachment-btn" title="Attach file">
        <i class="fas fa-paperclip"></i>
    </button>
    <button id="attach-image-btn" class="attachment-btn" title="Attach image">
        <i class="fas fa-image"></i>
    </button>
    <input type="file" id="file-input" style="display: none;" multiple>
    <input type="file" id="image-input" style="display: none;" accept="image/*" multiple>
</div>
```

```javascript
class FileAttachmentHandler {
    constructor() {
        this.attachedFiles = [];
        this.maxFileSize = 10 * 1024 * 1024; // 10MB
        this.allowedTypes = [
            'text/plain',
            'application/json',
            'text/markdown',
            'image/png',
            'image/jpeg',
            'image/gif'
        ];
    }
    
    async handleFileUpload(files) {
        for (const file of files) {
            if (file.size > this.maxFileSize) {
                alert(`File ${file.name} is too large (max 10MB)`);
                continue;
            }
            
            if (!this.allowedTypes.includes(file.type)) {
                alert(`File type ${file.type} not supported`);
                continue;
            }
            
            const fileData = await this.readFile(file);
            this.attachedFiles.push({
                name: file.name,
                type: file.type,
                size: file.size,
                data: fileData
            });
            
            this.displayAttachment(file);
        }
    }
    
    async readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = reject;
            
            if (file.type.startsWith('image/')) {
                reader.readAsDataURL(file);
            } else {
                reader.readAsText(file);
            }
        });
    }
    
    displayAttachment(file) {
        const attachmentPreview = document.createElement('div');
        attachmentPreview.className = 'attachment-preview';
        attachmentPreview.innerHTML = `
            <span class="attachment-icon">${this.getFileIcon(file.type)}</span>
            <span class="attachment-name">${file.name}</span>
            <button class="attachment-remove" onclick="removeAttachment('${file.name}')">
                <i class="fas fa-times"></i>
            </button>
        `;
        document.getElementById('attachments-container').appendChild(attachmentPreview);
    }
    
    getFileIcon(type) {
        if (type.startsWith('image/')) return '🖼️';
        if (type.includes('json')) return '📋';
        if (type.includes('markdown')) return '📝';
        return '📄';
    }
}
```

#### Feature 2: Image Preview in Chat

```javascript
function displayImageInChat(imageData, filename) {
    const chatHistory = document.getElementById('chat-history');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message user';
    messageDiv.innerHTML = `
        <div class="chat-avatar user">U</div>
        <div class="chat-content">
            <div class="image-attachment">
                <img src="${imageData}" alt="${filename}" class="chat-image">
                <span class="image-filename">${filename}</span>
            </div>
        </div>
    `;
    chatHistory.appendChild(messageDiv);
}
```

```css
.chat-image {
    max-width: 300px;
    max-height: 300px;
    border-radius: 8px;
    margin-top: 8px;
    cursor: pointer;
    transition: transform 0.2s;
}

.chat-image:hover {
    transform: scale(1.05);
}

.image-filename {
    display: block;
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 4px;
}
```

#### Feature 3: Code Diff Viewer

```html
<div class="code-diff-viewer">
    <div class="diff-header">
        <span class="diff-file-name">📄 main.py</span>
        <div class="diff-stats">
            <span class="diff-additions">+15</span>
            <span class="diff-deletions">-8</span>
        </div>
    </div>
    <div class="diff-content">
        <!-- Syntax-highlighted diff -->
    </div>
</div>
```

#### Feature 4: Real-time Collaboration Indicators

```javascript
class CollaborationIndicator {
    showAgentActivity(agentId, activity) {
        const indicator = document.createElement('div');
        indicator.className = 'agent-activity-indicator';
        indicator.innerHTML = `
            <div class="activity-pulse"></div>
            <span>${AGENT_AVATARS[agentId].icon} ${activity}</span>
        `;
        document.getElementById('activity-bar').appendChild(indicator);
        
        setTimeout(() => indicator.remove(), 5000);
    }
}
```

---

## 📋 Implementation Checklist

### Phase 1: Visual Improvements (Week 1)
- [ ] Replace all generic emojis with unique professional icons
- [ ] Implement Akino branding and avatar system
- [ ] Fix PM Agent progress bar with real-time updates
- [ ] Add agent status indicators with color coding

### Phase 2: File Management (Week 2)
- [ ] Implement smart file tree filtering
- [ ] Create project organization structure
- [ ] Add cache management system
- [ ] Integrate AWS S3 for cache storage

### Phase 3: Advanced Features (Week 3)
- [ ] Add file upload support
- [ ] Implement image preview in chat
- [ ] Create code diff viewer
- [ ] Add real-time collaboration indicators

### Phase 4: Polish & Testing (Week 4)
- [ ] Performance optimization
- [ ] Cross-browser testing
- [ ] Mobile responsiveness
- [ ] User acceptance testing

---

## 🎨 Design System

### Color Palette

```css
:root {
    /* Primary Colors */
    --akino-purple: #667eea;
    --akino-pink: #764ba2;
    --akino-blue: #4facfe;
    --akino-green: #43e97b;
    
    /* Agent Colors */
    --pm-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --dev-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    --qa-gradient: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    --ops-gradient: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
    
    /* Status Colors */
    --status-success: #43e97b;
    --status-warning: #ffd89b;
    --status-error: #f5576c;
    --status-info: #4facfe;
}
```

### Typography

```css
:root {
    --font-display: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-code: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    
    --text-xs: 11px;
    --text-sm: 13px;
    --text-base: 14px;
    --text-lg: 16px;
    --text-xl: 20px;
    --text-2xl: 24px;
}
```

---

## 🚀 Next Steps

1. **Review this plan** and prioritize features
2. **Create a prototype** with the new emoji system and Akino branding
3. **Implement file filtering** to clean up the file tree
4. **Fix the progress bar** in PM Agent panel
5. **Add file upload** capability for enhanced user interaction

Would you like me to start implementing any of these improvements?
