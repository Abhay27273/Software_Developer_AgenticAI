# Split View Optimization - Claude-Style Chat Shrinking

## Overview
Implemented automatic chat panel shrinking when files are opened, creating a side-by-side layout that matches Claude's interface behavior.

## Problem Solved
**Before:** When clicking a file, the chat and code panels were displayed as equal-width columns (1fr 1fr), not giving the code panel enough space.

**After:** Chat panel shrinks to a fixed narrow width (400px), code panel expands to fill remaining space, just like Claude!

## Changes Made

### 1. **Grid Layout Optimization**

#### Desktop (>1024px)
```css
.content-area.split-active {
    grid-template-columns: 400px 1fr; /* Chat: 400px fixed, Code: flexible */
    gap: 24px;
}
```
- **Chat Panel**: Fixed at **400px** width
- **Code Panel**: Takes **all remaining space** (1fr)
- **Gap**: Reduced to **24px** for efficiency

#### Tablet (≤1024px, >900px)
```css
.content-area.split-active {
    grid-template-columns: 320px 1fr; /* Even narrower chat on tablets */
    gap: 16px;
}
```
- **Chat Panel**: Narrower at **320px**
- **Code Panel**: Still takes remaining space
- **Gap**: Further reduced to **16px**

#### Mobile (≤900px)
```css
.content-area.split-active {
    grid-template-columns: 1fr; /* Stack vertically */
}
```
- **Layout**: Stacks vertically (no side-by-side)
- **Both panels**: Full width

### 2. **Compact Chat Messages in Split View**

When in split view, messages become even more compact:

```css
.content-area.split-active .chat-message {
    max-width: 95%; /* Use more of narrow column */
    padding: 8px 12px; /* More compact padding */
    font-size: 13px; /* Slightly smaller text */
    gap: 10px; /* Tighter spacing */
}
```

**Adjustments:**
- **Padding**: `10px 14px` → `8px 12px`
- **Font Size**: `14px` → `13px`
- **Max Width**: `85%` → `95%` (use narrow space efficiently)
- **Gap**: `12px` → `10px`

### 3. **Avatar Sizing in Split View**

```css
.content-area.split-active .chat-avatar {
    width: 28px;  /* Smaller from 32px */
    height: 28px;
    font-size: 14px; /* Smaller from 16px */
}
```

### 4. **Chat History Spacing**

```css
.content-area.split-active .chat-history {
    gap: 10px; /* Tighter from 12px */
}
```

### 5. **File Viewer Padding**

```css
.content-area.split-active .file-viewer-panel {
    padding-left: 20px; /* Reduced from 30px */
}
```

## Visual Results

### Layout Behavior

**When No File is Open:**
```
┌────────────────────────────────────────────┐
│                                            │
│            Chat Panel (centered)           │
│              Max-width: 720px              │
│                                            │
└────────────────────────────────────────────┘
```

**When File is Opened (Desktop):**
```
┌─────────────────┬──────────────────────────┐
│   Chat Panel    │     Code Panel          │
│   (400px)       │     (Expands!)          │
│                 │                          │
│  Compact msgs   │   Full file view        │
│  Smaller text   │   Syntax highlighting   │
│  Tight spacing  │   Line numbers          │
│                 │   File metadata         │
└─────────────────┴──────────────────────────┘
```

**When File is Opened (Tablet):**
```
┌──────────┬───────────────────────────────┐
│  Chat    │        Code Panel            │
│  (320px) │        (Larger!)             │
│          │                               │
│  Tiny    │     Full view                │
│  msgs    │                               │
└──────────┴───────────────────────────────┘
```

### Space Distribution

**Desktop (1920px wide example):**
- Sidebar: 220px
- Chat: 400px
- Gap: 24px
- Code: ~1276px (remaining space!)
- **Code gets 66% of screen!** 🎉

**Laptop (1440px wide example):**
- Sidebar: 220px
- Chat: 400px
- Gap: 24px
- Code: ~796px (remaining space)
- **Code gets 55% of screen!**

## Comparison with Claude

### ✅ Matches Claude's Behavior

1. **Chat shrinks** when file opens (not equal columns)
2. **Code expands** to fill available space
3. **No vertical stacking** on desktop (side-by-side)
4. **Messages get more compact** in narrow chat
5. **Fixed chat width** (not percentage-based)
6. **Fluid code panel** (takes remaining space)

### Key Similarities

| Feature | Claude | Our Implementation |
|---------|--------|-------------------|
| Chat width in split | ~400-450px | 400px (desktop) |
| Code panel | Flexible (1fr) | Flexible (1fr) ✓ |
| Message compact | Yes | Yes ✓ |
| Auto-shrink chat | Yes | Yes ✓ |
| Vertical stack mobile | Yes | Yes ✓ |

## User Experience Benefits

### 1. **More Code Visible**
- Code panel gets 2-3x more space than chat
- See entire file width without scrolling
- Better for reviewing generated code

### 2. **Efficient Chat**
- Still readable at 400px width
- Messages wrap nicely
- All functionality preserved

### 3. **Natural Flow**
- Click file → Chat shrinks automatically
- Close file → Chat expands back
- No manual adjustments needed

### 4. **Responsive Design**
- Desktop: Side-by-side with compact chat
- Tablet: Even narrower chat (320px)
- Mobile: Vertical stack

## Technical Details

### Grid System
```css
/* Default: Single column for chat only */
.content-area {
    display: flex;
    flex-direction: column;
}

/* Split activated: Two columns */
.content-area.split-active {
    display: grid;
    grid-template-columns: 400px 1fr;
}
```

### Automatic Activation
```javascript
// In showFileContent() method:
this.contentArea.classList.add('split-active');
```

### Responsive Breakpoints
- **> 1024px**: 400px chat, flexible code
- **900-1024px**: 320px chat, flexible code
- **< 900px**: Vertical stack

## Testing Checklist

- [x] Chat shrinks to 400px when file opens
- [x] Code panel expands to fill space
- [x] Messages remain readable in narrow chat
- [x] Avatars scale down appropriately
- [x] No horizontal scrolling in chat
- [x] File viewer shows full width content
- [x] Tablet shows 320px chat width
- [x] Mobile stacks vertically
- [x] Chat expands back when file closes
- [x] All responsive breakpoints work

## Performance

- **Layout Shift**: Minimal (CSS grid handles it)
- **Reflow**: Optimized (single grid change)
- **Smooth**: No jank or flickering
- **Paint**: Efficient (isolated to grid cells)

## Browser Compatibility

- ✅ Chrome/Edge (CSS Grid support)
- ✅ Firefox (CSS Grid support)
- ✅ Safari (CSS Grid support)
- ✅ Mobile browsers (Grid + media queries)

## Future Enhancements

1. **Adjustable Split**: Drag divider between chat and code
2. **Remember Ratio**: Save user's preferred split
3. **Keyboard Shortcut**: Toggle split view
4. **Animation**: Smooth transition when shrinking
5. **Three-column**: Chat, code, preview

## Summary

The split view now works exactly like Claude's interface:
- **Chat automatically shrinks** to 400px (desktop) or 320px (tablet)
- **Code panel expands** to take all remaining space
- **Messages get more compact** in split view
- **Responsive** behavior on all screen sizes
- **No manual adjustment** needed - it just works!

**Result:** A professional, efficient layout that maximizes code visibility while keeping chat accessible and readable. 🎯
