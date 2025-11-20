# Claude-Style UI - Quick User Guide

## 🎨 New Features Overview

Your AI Agentic System now has a professional Claude.ai-inspired interface with advanced code editing and preview capabilities!

---

## 🗂️ **Tabbed File Interface**

### Opening Files
- Click any file in the left sidebar
- File opens in a new tab at the top of the code panel
- Multiple files can be open simultaneously

### Tab Features
- **Active Tab**: Highlighted with blue border
- **Unsaved Tab**: Shows orange dot (●) when edited
- **Close Tab**: Click the `×` button on each tab
- **Switch Tabs**: Click any tab to view that file

### Tips
- Tabs persist until you close them manually
- Closing unsaved tabs will prompt for confirmation
- Tab names show the filename (not full path)

---

## ✏️ **Edit Mode**

### Enabling Edit Mode
1. Click the **Edit** button (purple) in toolbar
2. Or press `Ctrl+E` keyboard shortcut
3. Code editor gets a blue outline and becomes editable

### Editing Code
- Type directly in the code panel
- Changes are tracked automatically
- Orange "Unsaved" indicator appears in header
- Orange dot (●) appears in tab name

### Saving Changes
1. Click the **Save** button (blue) in toolbar
2. Or press `Ctrl+S` keyboard shortcut
3. Success feedback: Button shows "✅ Saved!" for 2 seconds
4. Unsaved indicators disappear

### Disabling Edit Mode
- Click **View** button (was Edit) to exit edit mode
- Code returns to read-only view mode
- Blue outline disappears

---

## 👁️ **Live Preview**

### When to Use
- Available for HTML files only
- Perfect for viewing UI layouts, dashboards, forms
- Shows real-time rendered output

### Activating Preview
1. Open an HTML file (e.g., `index.html`)
2. Click **Preview** button (orange) in toolbar
3. Preview panel slides in from right side
4. Code and preview shown side-by-side

### Preview Features
- **Iframe Rendering**: Shows actual HTML output
- **Refresh Button**: Click 🔄 to reload preview
- **Side-by-Side View**: Code on left, preview on right
- **Hide Preview**: Click button again to close

### Tips
- Edit the code and click refresh to see changes
- Preview works with embedded CSS and JavaScript
- Multiple HTML files each have their own preview

---

## 🎨 **Clickable UI File Messages**

### Automatic Detection
When the Dev Agent creates UI files (like `index.html`), you'll see a special message in the chat:

**Purple gradient message box with:**
- 🎨 Icon and file creation notification
- **"View UI & Live Preview"** button

### How to Use
1. Look for purple messages in chat after UI generation
2. Click the **"🎨 View UI & Live Preview"** button
3. File automatically opens with live preview enabled
4. No need to manually navigate to the file!

### Example Scenario
```
You: "Create a dashboard with charts"
Dev Agent: "Created index.html with interactive dashboard"
[Purple Box] → "🎨 View UI & Live Preview" button appears
You: Click button → Dashboard opens with live preview
```

---

## 🛠️ **Enhanced Toolbar**

### Button Reference

| Button | Color | Function | Shortcut |
|--------|-------|----------|----------|
| **Edit** | Purple | Toggle edit mode | `Ctrl+E` |
| **Save** | Blue | Save changes | `Ctrl+S` |
| **Run** | Green | Execute code | - |
| **Preview** | Orange | Toggle live preview | - |
| **Copy** | Gray | Copy to clipboard | - |
| **Download** | Gray | Download file | - |
| **Expand** | Gray | Fullscreen mode | - |
| **Close** | Gray | Close file viewer | - |

### Button States
- **Disabled**: Grayed out (e.g., Save when not in edit mode)
- **Active**: Changed icon (e.g., Preview → Hide Preview)
- **Success**: Green checkmark (e.g., Saved!)

---

## 📊 **Status Indicators**

### Header Status Bar
Located in the toolbar header:

1. **Connection Status**
   - 🟢 Green dot + "Connected"
   - Always visible
   - Shows WebSocket connection state

2. **Unsaved Changes**
   - 🟠 Orange dot + "Unsaved"
   - Appears when file is edited
   - Disappears after saving

3. **File Type Badge**
   - Color-coded language badge
   - Shows: PYTHON, JAVASCRIPT, HTML, CSS, etc.
   - Changes with active tab

### Footer Indicators
Located at bottom of code panel:

1. **File Size**: 📏 Shows KB/MB
2. **Line Count**: 🔤 Shows total lines
3. **File Type**: 💾 Shows full type name
4. **Edit Mode**: ✏️ (only when editing)

---

## ⌨️ **Keyboard Shortcuts**

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save current file (edit mode only) |
| `Ctrl+E` | Toggle edit mode |

**Coming Soon:**
- `Ctrl+Tab` - Switch to next tab
- `Ctrl+Shift+Tab` - Switch to previous tab
- `Ctrl+W` - Close active tab
- `Ctrl+F` - Find in file

---

## 🔄 **Typical Workflows**

### Workflow 1: View Generated Code
1. Dev Agent generates files
2. Click file in sidebar
3. File opens in new tab
4. View code with syntax highlighting

### Workflow 2: Edit and Save Code
1. Open file in tab
2. Click **Edit** button (or `Ctrl+E`)
3. Make your changes
4. Press `Ctrl+S` to save
5. See "✅ Saved!" confirmation

### Workflow 3: Preview UI Components
1. Open HTML file (e.g., `index.html`)
2. Click **Preview** button
3. See rendered output side-by-side
4. Edit code → Click refresh → See updates

### Workflow 4: Quick UI Access
1. Request UI creation: "Create a login page"
2. Wait for Dev Agent to generate files
3. Purple message appears in chat
4. Click **"🎨 View UI & Live Preview"** button
5. Instantly see UI with preview panel

---

## 💡 **Pro Tips**

### Tab Management
- Keep frequently used files open in tabs
- Close unused tabs to reduce clutter
- Unsaved tabs show a warning before closing

### Edit Mode Best Practices
- Enable edit mode only when needed
- Save frequently to avoid losing changes
- Exit edit mode when done to prevent accidental edits

### Live Preview Optimization
- Use preview for HTML files only
- Click refresh after major changes
- Preview uses iframe sandbox for safety

### File Navigation
- Click tabs to switch between files
- Use sidebar to open new files
- Active tab is always highlighted

---

## 🐛 **Troubleshooting**

### Preview Not Showing
**Problem**: Preview button does nothing
**Solution**: Preview only works for `.html` files. Check file type badge.

### Can't Save Changes
**Problem**: Save button is disabled
**Solution**: Enable edit mode first (click Edit button or `Ctrl+E`)

### Tab Showing Orange Dot
**Problem**: Orange dot won't go away
**Solution**: You have unsaved changes. Click Save (`Ctrl+S`) to persist changes.

### Code Not Editable
**Problem**: Can't type in code panel
**Solution**: Enable edit mode first. Click Edit button (purple) in toolbar.

### Clickable UI Message Not Appearing
**Problem**: Dev agent created HTML but no purple message
**Solution**: Message detection is keyword-based. Try asking: "Create index.html UI"

---

## 📱 **Responsive Behavior**

### Desktop (1920x1080)
- Full tabs row visible
- Live preview side-by-side
- All toolbar buttons shown

### Laptop (1366x768)
- Tabs may scroll horizontally
- Live preview may be narrower
- All features work normally

### Tablet (768x1024)
- Compact tab spacing
- Sidebar auto-hides
- Preview below code (stacked)

### Mobile (375x667)
- Single tab visible at a time
- Toolbar buttons wrap
- Preview in separate view

---

## 🚀 **What's Different from Before?**

### Before
- ❌ One file at a time
- ❌ View-only code
- ❌ No live preview
- ❌ Manual file navigation
- ❌ No edit/save capability

### Now
- ✅ Multiple tabs
- ✅ Edit and save code
- ✅ Live HTML preview
- ✅ Clickable UI file buttons
- ✅ Professional toolbar
- ✅ Status indicators
- ✅ Keyboard shortcuts

---

## 🎓 **Learning Path**

### Beginner (First 5 minutes)
1. Open a file → See it in a tab
2. Open another file → See both tabs
3. Click tabs to switch between them

### Intermediate (First 15 minutes)
1. Enable edit mode on a file
2. Make a simple change
3. Save with Ctrl+S
4. See success feedback

### Advanced (First 30 minutes)
1. Open HTML file
2. Enable live preview
3. Edit code in one panel
4. See changes in preview
5. Use keyboard shortcuts

---

## ❓ **FAQ**

**Q: How many tabs can I have open?**
A: No hard limit, but 5-10 is recommended for performance.

**Q: Can I edit multiple files at once?**
A: Edit mode applies to one file at a time (active tab).

**Q: Does saving send changes to the server?**
A: Currently saves to client state. Server sync coming soon.

**Q: Can I preview JavaScript files?**
A: No, preview is HTML-only. Use Run button for JS (coming soon).

**Q: What happens if I refresh the page?**
A: Tabs close and you return to welcome screen. Tab persistence coming soon.

**Q: Can I change tab order?**
A: Not yet. Drag-and-drop reordering is a planned feature.

---

## 🎉 **Enjoy Your New UI!**

You now have a professional, Claude-inspired interface with all the tools you need for efficient code viewing, editing, and previewing.

**Happy Coding!** 🚀
