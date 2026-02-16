/**
 * SIPring - Main JavaScript
 */

(function() {
    'use strict';

    // ==========================================================================
    // Theme Management
    // ==========================================================================

    const THEME_KEY = 'sipring-theme';

    function getStoredTheme() {
        return localStorage.getItem(THEME_KEY);
    }

    function setStoredTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
    }

    function getPreferredTheme() {
        const stored = getStoredTheme();
        if (stored) {
            return stored;
        }
        return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        setStoredTheme(theme);

        // Update toggle label if it exists
        const label = document.querySelector('.theme-toggle-label');
        if (label) {
            label.textContent = theme === 'light' ? 'Light Mode' : 'Dark Mode';
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const newTheme = current === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    }

    // Apply theme immediately on load (before DOM ready) to prevent flash
    setTheme(getPreferredTheme());

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
        if (!getStoredTheme()) {
            setTheme(e.matches ? 'light' : 'dark');
        }
    });

    // Expose toggle function globally
    window.toggleTheme = toggleTheme;

    // ==========================================================================
    // Toast Notifications
    // ==========================================================================

    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);

    function showToast(message, type = 'success', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <svg><use href="#icon-${type === 'success' ? 'check' : 'alert'}"></use></svg>
            <span class="toast-message">${message}</span>
        `;

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-out');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    window.showToast = showToast;

    // ==========================================================================
    // Sidebar Toggle (Mobile)
    // ==========================================================================

    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-open');
        });
    }

    if (sidebarOverlay && sidebar) {
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('mobile-open');
        });
    }

    // Close sidebar on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('mobile-open')) {
            sidebar.classList.remove('mobile-open');
        }
    });

    // ==========================================================================
    // Copy to Clipboard
    // ==========================================================================

    function copyToClipboard(text, button) {
        navigator.clipboard.writeText(text).then(() => {
            const originalHtml = button.innerHTML;
            button.innerHTML = '<svg><use href="#icon-check"></use></svg>';
            button.classList.add('copied');
            showToast('Copied to clipboard');

            setTimeout(() => {
                button.innerHTML = originalHtml;
                button.classList.remove('copied');
            }, 2000);
        }).catch(() => {
            showToast('Failed to copy', 'error');
        });
    }

    window.copyToClipboard = copyToClipboard;

    // ==========================================================================
    // Ring Actions
    // ==========================================================================

    function triggerRing(url, button) {
        const originalHtml = button.innerHTML;
        button.innerHTML = '<svg class="spin"><use href="#icon-bell"></use></svg> Ringing...';
        button.disabled = true;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                button.innerHTML = `<svg><use href="#icon-check"></use></svg> ${data.status || 'Done'}`;
                showToast(data.status || 'Ring triggered');

                setTimeout(() => {
                    button.innerHTML = originalHtml;
                    button.disabled = false;
                }, 3000);
            })
            .catch(error => {
                button.innerHTML = '<svg><use href="#icon-alert"></use></svg> Error';
                showToast('Failed to trigger ring', 'error');

                setTimeout(() => {
                    button.innerHTML = originalHtml;
                    button.disabled = false;
                }, 3000);
            });
    }

    window.triggerRing = triggerRing;

    // ==========================================================================
    // Test Ring
    // ==========================================================================

    function testRing(configId, button) {
        const originalHtml = button.innerHTML;
        button.innerHTML = '<svg class="spin"><use href="#icon-test"></use></svg> Testing...';
        button.disabled = true;

        fetch(`/api/configs/${configId}/test`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                button.innerHTML = `<svg><use href="#icon-check"></use></svg> ${data.result || 'Done'}`;
                showToast(data.result || 'Test completed');

                setTimeout(() => {
                    button.innerHTML = originalHtml;
                    button.disabled = false;
                }, 3000);
            })
            .catch(error => {
                button.innerHTML = '<svg><use href="#icon-alert"></use></svg> Error';
                showToast('Test failed', 'error');

                setTimeout(() => {
                    button.innerHTML = originalHtml;
                    button.disabled = false;
                }, 3000);
            });
    }

    window.testRing = testRing;

    // ==========================================================================
    // Clone Config
    // ==========================================================================

    function cloneConfig(configId) {
        fetch(`/api/configs/${configId}/clone`, { method: 'POST' })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Failed to clone configuration');
                }
            })
            .then(data => {
                showToast('Configuration cloned');
                window.location.href = `/config/${data.slug || data.id}/edit`;
            })
            .catch(error => {
                showToast(error.message, 'error');
            });
    }

    window.cloneConfig = cloneConfig;

    // ==========================================================================
    // Delete Config
    // ==========================================================================

    function deleteConfig(configId, name) {
        if (!confirm(`Delete configuration "${name}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        fetch(`/api/configs/${configId}`, { method: 'DELETE' })
            .then(response => {
                if (response.ok) {
                    showToast('Configuration deleted');
                    window.location.href = '/';
                } else {
                    throw new Error('Failed to delete configuration');
                }
            })
            .catch(error => {
                showToast(error.message, 'error');
            });
    }

    window.deleteConfig = deleteConfig;

    // ==========================================================================
    // Form Handling
    // ==========================================================================

    const configForm = document.getElementById('configForm');

    if (configForm) {
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const form = e.target;
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalHtml = submitBtn.innerHTML;

            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Saving...';

            const data = {
                name: form.name.value,
                slug: form.slug.value || null,
                sip_user: form.sip_user.value,
                sip_server: form.sip_server.value,
                sip_port: parseInt(form.sip_port.value),
                caller_name: form.caller_name.value,
                caller_user: form.caller_user.value,
                ring_duration: parseInt(form.ring_duration.value),
                local_port: parseInt(form.local_port.value),
                enabled: form.enabled.value === 'true'
            };

            const isEdit = form.dataset.configId;
            const url = isEdit ? `/api/configs/${form.dataset.configId}` : '/api/configs';
            const method = isEdit ? 'PUT' : 'POST';

            try {
                const response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    showToast(isEdit ? 'Configuration updated' : 'Configuration created');
                    window.location.href = '/';
                } else {
                    const error = await response.json();
                    showToast(error.detail || 'Failed to save configuration', 'error');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalHtml;
                }
            } catch (error) {
                showToast('Failed to save configuration: ' + error.message, 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHtml;
            }
        });
    }

    // ==========================================================================
    // Event Log Filtering & Pagination
    // ==========================================================================

    function filterEvents() {
        const range = document.getElementById('filter-range').value;
        const configId = document.getElementById('filter-config').value;
        const result = document.getElementById('filter-result').value;
        const triggerType = document.getElementById('filter-type').value;

        const params = new URLSearchParams();
        if (range) params.set('range', range);
        if (configId) params.set('config_id', configId);
        if (result) params.set('result', result);
        if (triggerType) params.set('trigger_type', triggerType);

        window.location.href = '/events?' + params.toString();
    }

    window.filterEvents = filterEvents;

    function loadPage(offset) {
        const params = new URLSearchParams(window.location.search);
        params.set('offset', offset);
        window.location.href = '/events?' + params.toString();
    }

    window.loadPage = loadPage;

    // ==========================================================================
    // Keyboard Shortcuts
    // ==========================================================================

    document.addEventListener('keydown', (e) => {
        // Alt+N: New configuration
        if (e.altKey && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/config/new';
        }

        // Alt+D: Dashboard
        if (e.altKey && e.key === 'd') {
            e.preventDefault();
            window.location.href = '/';
        }
    });

    // ==========================================================================
    // Active Nav Item
    // ==========================================================================

    // ==========================================================================
    // Local Timezone Conversion
    // ==========================================================================

    document.querySelectorAll('time[datetime]').forEach(el => {
        const d = new Date(el.getAttribute('datetime'));
        if (!isNaN(d)) {
            const pad = n => String(n).padStart(2, '0');
            el.textContent = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
                + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
        }
    });

    // ==========================================================================
    // Active Nav Item
    // ==========================================================================

    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.sidebar-nav-item');

    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath || (href === '/' && currentPath === '/')) {
            item.classList.add('active');
        } else if (href !== '/' && currentPath.startsWith(href)) {
            item.classList.add('active');
        }
    });

})();
