# SIPring Design System

A UniFi-inspired design system with dark and light themes for web applications.

## Overview

This design system provides a modern, professional interface inspired by Ubiquiti's UniFi Network application. It features:

- **Dark and light themes** with automatic system preference detection
- **Theme persistence** via localStorage
- **Signature blue accent** (#006FFF) for primary actions
- **Left sidebar navigation** that collapses on hover
- **Clean typography** using Inter font
- **Consistent spacing** and component styling

## Quick Start

### 1. Include Required Files

```html
<!-- In your <head> -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/css/main.css">

<!-- Prevent flash of wrong theme -->
<script>
    (function() {
        const theme = localStorage.getItem('sipring-theme') ||
            (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        document.documentElement.setAttribute('data-theme', theme);
    })();
</script>

<!-- Before </body> -->
<script src="/static/js/main.js"></script>
```

### 2. Basic Page Structure

```html
<div class="app-layout">
    <aside class="sidebar">
        <!-- Sidebar content -->
    </aside>
    <main class="main-content">
        <div class="content-wrapper">
            <!-- Page content -->
        </div>
    </main>
</div>
```

---

## Color Palette

### Backgrounds

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#1C1E2D` | Main page background |
| `--bg-secondary` | `#212335` | Secondary areas, card footers |
| `--bg-card` | `#282A40` | Card backgrounds |
| `--bg-elevated` | `#2E3047` | Hover states, elevated surfaces |
| `--bg-input` | `#1A1C28` | Input field backgrounds |
| `--sidebar-bg` | `#16171F` | Sidebar background (darker) |

### Accent Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent` | `#006FFF` | Primary buttons, links, focus rings |
| `--accent-hover` | `#0080FF` | Hover state for accent |
| `--accent-muted` | `rgba(0,111,255,0.15)` | Subtle backgrounds |

### Text Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--text-primary` | `#FFFFFF` | Headings, primary content |
| `--text-secondary` | `#BABEC6` | Body text, descriptions |
| `--text-muted` | `#80828A` | Labels, hints, disabled text |

### Status Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--success` | `#00CA8B` | Success states, enabled |
| `--warning` | `#F39C12` | Warning states, disabled |
| `--error` | `#F5174F` | Error states, destructive actions |

### Border Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--border` | `#383A4F` | Card borders, input borders |
| `--border-light` | `#2E3047` | Subtle dividers |
| `--divider` | `rgba(255,255,255,0.08)` | Section dividers |

---

## Light Theme

The light theme is activated by setting `data-theme="light"` on the `<html>` element. All CSS custom properties automatically update.

### Light Theme Colors

| Token | Dark Value | Light Value |
|-------|-----------|-------------|
| `--bg-primary` | `#1C1E2D` | `#F5F6FA` |
| `--bg-secondary` | `#212335` | `#FFFFFF` |
| `--bg-card` | `#282A40` | `#FFFFFF` |
| `--bg-elevated` | `#2E3047` | `#F0F1F5` |
| `--bg-input` | `#1A1C28` | `#FFFFFF` |
| `--sidebar-bg` | `#16171F` | `#FAFBFC` |
| `--accent` | `#006FFF` | `#0059CC` |
| `--text-primary` | `#FFFFFF` | `#1A1C28` |
| `--text-secondary` | `#BABEC6` | `#5A5E6B` |
| `--text-muted` | `#80828A` | `#8A8E99` |
| `--border` | `#383A4F` | `#E0E2E9` |
| `--divider` | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.06)` |

### Theme Toggle

```html
<div class="theme-toggle" onclick="toggleTheme()" role="button" tabindex="0">
    <div class="theme-toggle-icons">
        <svg class="icon-sun"><use href="/static/icons/icons.svg#icon-sun"></use></svg>
        <svg class="icon-moon"><use href="/static/icons/icons.svg#icon-moon"></use></svg>
    </div>
    <div class="theme-toggle-track"></div>
    <span class="theme-toggle-label">Dark Mode</span>
</div>
```

### JavaScript Theme API

```javascript
// Toggle between light and dark
toggleTheme();

// The theme is automatically persisted to localStorage
// Key: 'sipring-theme'
// Values: 'light' or 'dark'

// System preference is respected when no stored preference exists
```

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

### Label Style

Labels use uppercase with letter-spacing:

```css
font-size: var(--text-xs);
font-weight: 600;
text-transform: uppercase;
letter-spacing: 0.05em;
color: var(--text-muted);
```

---

## Components

### Buttons

```html
<!-- Primary (blue filled) -->
<button class="btn btn-primary">
    <svg><use href="/static/icons/icons.svg#icon-plus"></use></svg>
    Create
</button>

<!-- Secondary (ghost/outline) -->
<button class="btn btn-secondary">Cancel</button>

<!-- Success (green) -->
<button class="btn btn-success">Test</button>

<!-- Danger (red outline) -->
<button class="btn btn-danger">Delete</button>

<!-- Ghost (no border) -->
<button class="btn btn-ghost">View</button>

<!-- Sizes -->
<button class="btn btn-primary btn-sm">Small</button>
<button class="btn btn-primary btn-lg">Large</button>

<!-- Icon only -->
<button class="btn btn-icon btn-secondary">
    <svg><use href="/static/icons/icons.svg#icon-copy"></use></svg>
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

### Code Box (URL display)

```html
<div class="code-box">
    <code>https://example.com/api/endpoint</code>
    <button class="btn-copy" onclick="copyToClipboard('url', this)">
        <svg><use href="/static/icons/icons.svg#icon-copy"></use></svg>
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

### Property Grid

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
    <svg><use href="/static/icons/icons.svg#icon-check"></use></svg>
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
    <svg><use href="/static/icons/icons.svg#icon-inbox"></use></svg>
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

---

## Layout

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

### Sidebar Navigation

```html
<aside class="sidebar">
    <div class="sidebar-header">
        <a href="/" class="sidebar-logo">
            <svg><!-- Logo icon --></svg>
            <span>App Name</span>
        </a>
    </div>
    <nav class="sidebar-nav">
        <a href="/" class="sidebar-nav-item active">
            <svg><use href="/static/icons/icons.svg#icon-dashboard"></use></svg>
            <span>Dashboard</span>
        </a>
        <a href="/settings" class="sidebar-nav-item">
            <svg><use href="/static/icons/icons.svg#icon-settings"></use></svg>
            <span>Settings</span>
        </a>
    </nav>
    <div class="sidebar-footer">
        <div class="sidebar-version">v1.0.0</div>
    </div>
</aside>
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

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Small elements |
| `--radius-md` | 6px | Buttons, inputs |
| `--radius-lg` | 8px | Cards |
| `--radius-xl` | 12px | Large cards |
| `--radius-full` | 9999px | Pills, badges |

---

## Responsive Breakpoints

The design system uses a mobile-first approach with one primary breakpoint:

```css
@media (max-width: 768px) {
    /* Mobile styles */
}
```

Mobile behavior:
- Sidebar transforms to overlay drawer
- Cards stack vertically
- Form rows become single column
- Action bars stack vertically

---

## JavaScript Utilities

### Toast Notifications

```javascript
showToast('Message here');                    // Success (default)
showToast('Error message', 'error');          // Error
showToast('Custom duration', 'success', 5000); // 5 seconds
```

### Copy to Clipboard

```javascript
copyToClipboard('text to copy', buttonElement);
```

---

## Accessibility

- All interactive elements have visible focus states
- Color contrast meets WCAG AA standards
- Keyboard navigation supported throughout
- ARIA labels on icon-only buttons
- Reduced motion support via `prefers-reduced-motion`

---

## Files Reference

```
static/
├── css/
│   └── main.css          # All styles (~900 lines)
├── js/
│   └── main.js           # JavaScript utilities
└── icons/
    └── icons.svg         # SVG sprite with all icons
```

---

## Applying to Other Projects

1. Copy the `static/css/main.css`, `static/js/main.js`, and `static/icons/icons.svg` files
2. Include Google Fonts (Inter) in your HTML head
3. Use the layout structure with `.app-layout`, `.sidebar`, and `.main-content`
4. Apply component classes as documented above
5. Customize CSS custom properties to adjust colors if needed
