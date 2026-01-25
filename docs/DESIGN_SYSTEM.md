# Design System

A modern, professional design system with dark and light themes inspired by Ubiquiti's UniFi Network application.

## Overview

This design system provides:

- **Dark and light themes** with automatic system preference detection
- **Theme persistence** via localStorage
- **Signature blue accent** (#006FFF) for primary actions
- **Left sidebar navigation** that expands on hover
- **Clean typography** using Inter font
- **Consistent spacing** and component styling
- **Mobile responsive** with overlay sidebar

---

## Quick Start Guide

### Step 1: Copy Files

Copy the following files to your project:

```
your-project/
├── static/
│   ├── css/
│   │   └── main.css          # All styles (~1400 lines)
│   └── js/
│       └── main.js           # JavaScript utilities
└── templates/
    └── base.html             # Base template with sidebar layout
```

### Step 2: Update Project-Specific Values

1. **In `main.js`**: Change the localStorage key for theme:
   ```javascript
   const THEME_KEY = 'your-project-theme';  // Change 'sipring-theme' to your project name
   ```

2. **In `base.html`**: Update the inline theme script:
   ```javascript
   const theme = localStorage.getItem('your-project-theme') || ...
   ```

3. **In `base.html`**: Update app name in sidebar logo:
   ```html
   <span>Your App Name</span>
   ```

4. **In `base.html`**: Update navigation items to match your routes.

### Step 3: Include Required Resources

In your HTML `<head>`:

```html
<!-- Google Fonts - Inter -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<!-- Main CSS -->
<link rel="stylesheet" href="/static/css/main.css">

<!-- CRITICAL: Prevent theme flash - must be BEFORE CSS loads -->
<script>
    (function() {
        const theme = localStorage.getItem('your-project-theme') ||
            (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        document.documentElement.setAttribute('data-theme', theme);
    })();
</script>
```

Before `</body>`:

```html
<script src="/static/js/main.js"></script>
```

---

## Important Learnings & Gotchas

### 1. SVG Icons Must Be Inlined

**Problem**: External SVG sprite files (`<use href="/static/icons.svg#icon-name">`) don't work reliably across browsers due to CORS and caching issues.

**Solution**: Inline the entire SVG sprite in your base template:

```html
<!-- At the end of <body>, before scripts -->
<svg xmlns="http://www.w3.org/2000/svg" style="display: none;">
    <symbol id="icon-plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
    </symbol>
    <!-- More symbols... -->
</svg>
```

Then reference with just the hash:
```html
<svg><use href="#icon-plus"></use></svg>
```

### 2. Prevent Theme Flash on Page Load

**Problem**: Without special handling, users see a flash of the wrong theme before JavaScript loads.

**Solution**: Add an inline script in `<head>` BEFORE the CSS link that immediately sets the `data-theme` attribute:

```html
<script>
    (function() {
        const theme = localStorage.getItem('your-project-theme') ||
            (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        document.documentElement.setAttribute('data-theme', theme);
    })();
</script>
```

### 3. SVG Sizing Issues

**Problem**: SVGs can become unexpectedly large or small in different contexts.

**Solution**: Always set explicit `min-width`, `min-height`, `max-width`, `max-height` on SVGs:

```css
.some-icon svg {
    width: 20px;
    height: 20px;
    min-width: 20px;
    min-height: 20px;
    max-width: 20px;
    max-height: 20px;
}
```

### 4. Collapsed Sidebar Element Overflow

**Problem**: Elements like the theme toggle can stick out of the collapsed sidebar.

**Solution**: Hide elements with `opacity: 0` when collapsed, show on hover:

```css
.theme-toggle-track {
    opacity: 0;
    transition: opacity var(--transition-fast);
}

.sidebar:hover .theme-toggle-track {
    opacity: 1;
}
```

### 5. Mobile Sidebar

**Problem**: Sidebar needs to be a full-width overlay on mobile.

**Solution**: Use CSS transform to hide/show, with an overlay backdrop:

```css
@media (max-width: 768px) {
    .sidebar {
        transform: translateX(-100%);
        width: var(--sidebar-width-expanded);
    }
    .sidebar.mobile-open {
        transform: translateX(0);
    }
}
```

---

## Color Palette

### Dark Theme (Default)

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#1C1E2D` | Main page background |
| `--bg-secondary` | `#212335` | Secondary areas, card footers |
| `--bg-card` | `#282A40` | Card backgrounds |
| `--bg-elevated` | `#2E3047` | Hover states, elevated surfaces |
| `--bg-input` | `#1A1C28` | Input field backgrounds |
| `--sidebar-bg` | `#16171F` | Sidebar background (darker) |
| `--accent` | `#006FFF` | Primary buttons, links, focus rings |
| `--accent-hover` | `#0080FF` | Hover state for accent |
| `--accent-muted` | `rgba(0,111,255,0.15)` | Subtle backgrounds |
| `--text-primary` | `#FFFFFF` | Headings, primary content |
| `--text-secondary` | `#BABEC6` | Body text, descriptions |
| `--text-muted` | `#80828A` | Labels, hints, disabled text |
| `--success` | `#00CA8B` | Success states, enabled |
| `--warning` | `#F39C12` | Warning states |
| `--error` | `#F5174F` | Error states, destructive actions |
| `--border` | `#383A4F` | Card borders, input borders |
| `--border-light` | `#2E3047` | Subtle dividers |
| `--divider` | `rgba(255,255,255,0.08)` | Section dividers |

### Light Theme

Activated by setting `data-theme="light"` on `<html>`:

| Token | Light Value |
|-------|-------------|
| `--bg-primary` | `#F5F6FA` |
| `--bg-secondary` | `#FFFFFF` |
| `--bg-card` | `#FFFFFF` |
| `--bg-elevated` | `#F0F1F5` |
| `--bg-input` | `#FFFFFF` |
| `--sidebar-bg` | `#FAFBFC` |
| `--accent` | `#0059CC` |
| `--accent-hover` | `#0066E6` |
| `--text-primary` | `#1A1C28` |
| `--text-secondary` | `#5A5E6B` |
| `--text-muted` | `#8A8E99` |
| `--border` | `#E0E2E9` |
| `--border-light` | `#ECEDF2` |
| `--divider` | `rgba(0,0,0,0.06)` |

---

## Typography

### Font Family

```css
--font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
```

### Font Sizes

| Token | Size | Usage |
|-------|------|-------|
| `--text-xs` | 11px | Labels, hints |
| `--text-sm` | 12px | Small text, badges |
| `--text-base` | 14px | Body text |
| `--text-md` | 16px | Card titles |
| `--text-lg` | 18px | Section headers |
| `--text-xl` | 24px | Page titles |
| `--text-2xl` | 32px | Large headings |
| `--text-metric` | 48px | Dashboard metrics |

### Label Style (Uppercase)

Used for form labels, table headers, section titles:

```css
font-size: var(--text-xs);
font-weight: 600;
text-transform: uppercase;
letter-spacing: 0.05em;
color: var(--text-muted);
```

---

## Spacing Scale

| Token | Value |
|-------|-------|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 20px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-10` | 40px |

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Small elements |
| `--radius-md` | 6px | Buttons, inputs |
| `--radius-lg` | 8px | Cards |
| `--radius-xl` | 12px | Large cards |
| `--radius-full` | 9999px | Pills, badges |

---

## Layout Structure

### Basic Page Structure

```html
<div class="app-layout">
    <!-- Mobile toggle button -->
    <button class="sidebar-toggle" aria-label="Toggle navigation">
        <svg><use href="#icon-menu"></use></svg>
    </button>

    <!-- Sidebar -->
    <aside class="sidebar">
        <div class="sidebar-header">
            <a href="/" class="sidebar-logo">
                <svg><use href="#icon-logo"></use></svg>
                <span>App Name</span>
            </a>
        </div>
        <nav class="sidebar-nav">
            <a href="/" class="sidebar-nav-item active">
                <svg><use href="#icon-dashboard"></use></svg>
                <span>Dashboard</span>
            </a>
            <!-- More nav items -->
        </nav>
        <div class="sidebar-footer">
            <!-- Theme toggle goes here -->
        </div>
    </aside>

    <!-- Mobile overlay -->
    <div class="sidebar-overlay"></div>

    <!-- Main content -->
    <main class="main-content">
        <div class="content-wrapper">
            <!-- Page content -->
        </div>
    </main>
</div>
```

### Page Header

```html
<div class="page-header">
    <div>
        <h1 class="page-title">Page Title</h1>
        <p class="page-subtitle">Optional subtitle text</p>
    </div>
    <div class="page-actions">
        <button class="btn btn-primary">Action</button>
    </div>
</div>
```

---

## Components

### Buttons

```html
<!-- Primary (blue filled) -->
<button class="btn btn-primary">
    <svg><use href="#icon-plus"></use></svg>
    Create
</button>

<!-- Secondary (ghost/outline) -->
<button class="btn btn-secondary">Cancel</button>

<!-- Success (green) -->
<button class="btn btn-success">Save</button>

<!-- Danger (red outline, fills on hover) -->
<button class="btn btn-danger">Delete</button>

<!-- Ghost (no border) -->
<button class="btn btn-ghost">View</button>

<!-- Sizes -->
<button class="btn btn-primary btn-sm">Small</button>
<button class="btn btn-primary btn-lg">Large</button>

<!-- Icon only -->
<button class="btn btn-icon btn-secondary">
    <svg><use href="#icon-copy"></use></svg>
</button>
```

### Cards

```html
<div class="card">
    <div class="card-header">
        <div class="card-header-left">
            <span class="card-title">Card Title</span>
            <span class="badge badge-success">Active</span>
        </div>
        <div class="card-actions">
            <button class="btn btn-primary btn-sm">Action</button>
        </div>
    </div>
    <div class="card-body">
        <!-- Content -->
    </div>
    <div class="card-footer">
        <button class="btn btn-ghost btn-sm">Cancel</button>
        <button class="btn btn-primary btn-sm">Save</button>
    </div>
</div>
```

### Card Grid

```html
<div class="card-grid">
    <div class="card">...</div>
    <div class="card">...</div>
</div>
```

### Forms

```html
<div class="form-section">
    <div class="form-section-title">Section Title</div>
    <div class="form-row">
        <div class="form-group">
            <label class="form-label form-label-required">Field Name</label>
            <input type="text" class="form-control" placeholder="Placeholder">
            <div class="form-hint">Helper text goes here</div>
        </div>
        <div class="form-group">
            <label class="form-label">Select Field</label>
            <select class="form-control">
                <option>Option 1</option>
                <option>Option 2</option>
            </select>
        </div>
    </div>
</div>
```

### Badges

```html
<span class="badge badge-success">
    <span class="status-dot status-dot-success"></span>
    Enabled
</span>
<span class="badge badge-warning">Disabled</span>
<span class="badge badge-error">Error</span>
<span class="badge badge-info">Active</span>
```

### Status Dots

```html
<!-- Static -->
<span class="status-dot status-dot-success"></span>
<span class="status-dot status-dot-warning"></span>
<span class="status-dot status-dot-error"></span>
<span class="status-dot status-dot-info"></span>

<!-- With pulse animation -->
<span class="status-dot status-dot-success pulse"></span>
```

### Code Box (URL/Code Display)

```html
<div class="code-box">
    <code>https://example.com/api/endpoint</code>
    <button class="btn-copy" onclick="copyToClipboard('https://example.com/api/endpoint', this)">
        <svg><use href="#icon-copy"></use></svg>
    </button>
</div>
```

### Stats Grid

```html
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-label">Total Items</div>
        <div class="stat-value">42</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Active</div>
        <div class="stat-value has-pulse">
            3
            <span class="status-dot status-dot-success pulse"></span>
        </div>
    </div>
</div>
```

### Property Grid (Detail Views)

```html
<div class="property-grid">
    <div class="property-item">
        <div class="property-label">Label</div>
        <div class="property-value">Value</div>
    </div>
    <div class="property-item">
        <div class="property-label">UUID</div>
        <div class="property-value mono">550e8400-e29b-41d4-a716-446655440000</div>
    </div>
</div>
```

### Alerts

```html
<div class="alert alert-success">
    <svg><use href="#icon-check"></use></svg>
    <div class="alert-content">
        <div class="alert-title">Success</div>
        <div class="alert-message">Operation completed successfully.</div>
    </div>
</div>

<div class="alert alert-warning">...</div>
<div class="alert alert-error">...</div>
<div class="alert alert-info">...</div>
```

### Empty State

```html
<div class="empty-state">
    <svg><use href="#icon-inbox"></use></svg>
    <h2 class="empty-state-title">No items yet</h2>
    <p class="empty-state-message">Create your first item to get started.</p>
    <button class="btn btn-primary">Create Item</button>
</div>
```

### Tables

```html
<div class="table-wrapper">
    <table class="table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Item Name</td>
                <td><span class="badge badge-success">Active</span></td>
                <td>
                    <button class="btn btn-ghost btn-sm">Edit</button>
                </td>
            </tr>
        </tbody>
    </table>
</div>
```

### Theme Toggle

```html
<div class="theme-toggle" onclick="toggleTheme()" role="button" tabindex="0" aria-label="Toggle theme">
    <div class="theme-toggle-icons">
        <svg class="icon-sun"><use href="#icon-sun"></use></svg>
        <svg class="icon-moon"><use href="#icon-moon"></use></svg>
    </div>
    <div class="theme-toggle-track"></div>
    <span class="theme-toggle-label">Dark Mode</span>
</div>
```

### Action Bar (Detail Pages)

```html
<div class="action-bar">
    <div class="action-bar-left">
        <button class="btn btn-primary">Primary Action</button>
        <button class="btn btn-secondary">Secondary</button>
    </div>
    <div class="action-bar-right">
        <button class="btn btn-danger">Delete</button>
    </div>
</div>
```

---

## JavaScript Utilities

### Theme Management

```javascript
// Toggle between light and dark
toggleTheme();

// Theme is automatically persisted to localStorage
// Respects system preference when no stored preference exists
```

### Toast Notifications

```javascript
showToast('Message here');                    // Success (default)
showToast('Error message', 'error');          // Error
showToast('Custom duration', 'success', 5000); // 5 seconds
```

### Copy to Clipboard

```javascript
copyToClipboard('text to copy', buttonElement);
// Shows a toast notification and temporarily changes button icon to checkmark
```

### Keyboard Shortcuts (Customizable)

The default shortcuts in main.js:
- `Alt+N` - New item
- `Alt+D` - Dashboard
- `Escape` - Close mobile sidebar

---

## Available Icons

The SVG sprite includes these icons (all use Feather Icons style):

| Icon ID | Description |
|---------|-------------|
| `icon-logo` | Phone with signal (app logo) |
| `icon-dashboard` | Grid layout |
| `icon-plus` | Plus sign |
| `icon-api` | Document with lines |
| `icon-bell` | Notification bell |
| `icon-edit` | Pencil/edit |
| `icon-copy` | Copy/duplicate |
| `icon-clone` | Clone/duplicate with overlay |
| `icon-trash` | Delete/trash |
| `icon-eye` | View/preview |
| `icon-x` | Close/cancel |
| `icon-check` | Checkmark |
| `icon-menu` | Hamburger menu |
| `icon-arrow-left` | Back arrow |
| `icon-stop` | Stop/square |
| `icon-test` | Flask/beaker |
| `icon-alert` | Warning circle |
| `icon-inbox` | Inbox/empty |
| `icon-sun` | Light theme |
| `icon-moon` | Dark theme |
| `icon-github` | GitHub logo |
| `icon-heart` | Heart/favorites |
| `icon-about` | Question mark circle |

Usage:
```html
<svg><use href="#icon-name"></use></svg>
```

---

## Responsive Breakpoints

The design system uses a mobile-first approach with one primary breakpoint at 768px:

```css
@media (max-width: 768px) {
    /* Mobile styles */
}
```

### Mobile Behavior

- Sidebar transforms to full-width overlay drawer
- Mobile toggle button appears (hidden on desktop)
- Cards stack vertically
- Form rows become single column
- Page actions span full width
- Action bars stack vertically

---

## Utility Classes

### Text Colors
- `.text-muted` - Muted text color
- `.text-secondary` - Secondary text color
- `.text-success` - Green text
- `.text-warning` - Orange text
- `.text-error` - Red text

### Spacing
- `.mt-0`, `.mt-2`, `.mt-4`, `.mt-6` - Margin top
- `.mb-0`, `.mb-2`, `.mb-4`, `.mb-6` - Margin bottom

### Flexbox
- `.flex` - Display flex
- `.flex-wrap` - Flex wrap
- `.items-center` - Align items center
- `.justify-between` - Justify space between
- `.gap-2`, `.gap-3`, `.gap-4` - Gap utilities

### Accessibility
- `.sr-only` - Screen reader only (visually hidden)

---

## Accessibility

- All interactive elements have visible focus states (blue ring)
- Color contrast meets WCAG AA standards
- Keyboard navigation supported throughout
- ARIA labels on icon-only buttons
- Reduced motion support via `prefers-reduced-motion`
- Theme toggle is keyboard accessible (Enter/Space)

---

## File Reference

```
static/
├── css/
│   └── main.css          # All styles (~1400 lines)
└── js/
    └── main.js           # Theme, toasts, clipboard, sidebar toggle

templates/
└── base.html             # Layout with sidebar, includes inline SVG sprite
```

---

## Checklist for New Projects

1. [ ] Copy `static/css/main.css`
2. [ ] Copy `static/js/main.js`
3. [ ] Copy base template structure
4. [ ] Update localStorage key in JS (`THEME_KEY`)
5. [ ] Update localStorage key in inline head script
6. [ ] Update app name in sidebar
7. [ ] Update navigation items
8. [ ] Add/remove icons from SVG sprite as needed
9. [ ] Include Google Fonts (Inter) in head
10. [ ] Test theme toggle works
11. [ ] Test mobile responsive behavior
12. [ ] Verify no theme flash on page load
