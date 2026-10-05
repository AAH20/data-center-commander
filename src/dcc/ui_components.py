"""Modular UI components for Data Center Commander.

Each view is a self-contained module that can be lazy-loaded.
Replaces the 84KB monolithic index.html with focused components.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Component registry
# ---------------------------------------------------------------------------

COMPONENTS: dict[str, str] = {
    "overview": "components/overview.html",
    "energy": "components/energy.html",
    "analytics": "components/analytics.html",
    "finance": "components/finance.html",
    "capacity": "components/capacity.html",
    "assets": "components/assets.html",
    "reliability": "components/reliability.html",
    "workflows": "components/workflows.html",
    "integrations": "components/integrations.html",
    "evidence": "components/evidence.html",
}


def get_component(name: str) -> str | None:
    """Get the HTML for a component by name."""
    if name not in COMPONENTS:
        return None
    path = Path(__file__).resolve().parents[2] / "ui" / COMPONENTS[name]
    if path.exists():
        return path.read_text()
    return None


def list_components() -> list[str]:
    """List all available component names."""
    return list(COMPONENTS.keys())


# ---------------------------------------------------------------------------
# Shared CSS (follows ui-ux-quality skill)
# ---------------------------------------------------------------------------

SHARED_CSS = """
:root {
  --color-bg: #0b111a;
  --color-panel: #121b28;
  --color-border: #28374a;
  --color-text: #e5edf8;
  --color-muted: #92a2b6;
  --color-accent: #65d5d0;
  --color-success: #6dd2a0;
  --color-warning: #ffc86e;
  --color-danger: #ff8888;
  --radius: 8px;
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  line-height: 1.5;
  overflow-x: hidden;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}

.card {
  background: var(--color-panel);
  border-radius: var(--radius);
  padding: 1.5rem;
  box-shadow: var(--shadow);
}

.card h2 {
  font-size: 1.25rem;
  margin-bottom: 0.75rem;
}

.card .value {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0.5rem 0;
}

.card .label {
  color: var(--color-muted);
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-panel);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.15s ease;
}

.btn:hover {
  background: var(--color-border);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-success { background: rgba(109, 210, 160, 0.15); color: var(--color-success); }
.badge-warning { background: rgba(255, 200, 110, 0.15); color: var(--color-warning); }
.badge-danger { background: rgba(255, 136, 136, 0.15); color: var(--color-danger); }

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th,
.table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.table th {
  color: var(--color-muted);
  font-weight: 500;
  font-size: 0.875rem;
}

.empty {
  padding: 2rem;
  text-align: center;
  color: var(--color-muted);
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--color-muted);
}

.error {
  padding: 1rem;
  border-radius: var(--radius);
  background: rgba(255, 136, 136, 0.1);
  color: var(--color-danger);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
"""


# ---------------------------------------------------------------------------
# Shared JavaScript utilities
# ---------------------------------------------------------------------------

SHARED_JS = """
// Shared utilities for DCC components
window.DCC = window.DCC || {};

DCC.utils = {
  formatNumber(value, unit) {
    if (value == null || value === undefined) return 'Unknown';
    const num = Number(value);
    if (!Number.isFinite(num)) return 'Unknown';
    return num.toLocaleString(undefined, { maximumFractionDigits: 3 }) + (unit ? ' ' + unit : '');
  },

  formatCurrency(value, currency) {
    if (value == null || value === undefined) return 'Not priced';
    try {
      return new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: currency || 'USD',
        maximumFractionDigits: 2
      }).format(Number(value));
    } catch {
      return Number(value).toFixed(2);
    }
  },

  formatDate(value) {
    if (!value) return '—';
    return new Date(value).toLocaleString();
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
  },

  async fetchJSON(path, options = {}) {
    const params = new URLSearchParams({ tenant_id: DCC.tenantId || '' });
    if (DCC.demoMode) params.set('demo', 'synthetic');
    const url = path + '?' + params.toString();
    const response = await fetch(url, { cache: 'no-store', ...options });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  },

  debounce(fn, ms) {
    let timeout;
    return (...args) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => fn(...args), ms);
    };
  }
};

// Component loader
DCC.loadComponent = async function(name) {
  const container = document.getElementById('view-' + name);
  if (!container) return;

  container.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const response = await fetch('/components/' + name + '.html');
    if (!response.ok) throw new Error('Component not found');
    container.innerHTML = await response.text();
    if (window.DCC.components && DCC.components[name]) {
      DCC.components[name].mount(container);
    }
  } catch (error) {
    container.innerHTML = '<div class="error">Failed to load: ' + DCC.utils.escapeHtml(error.message) + '</div>';
  }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  DCC.tenantId = new URLSearchParams(location.search).get('tenant_id');
  DCC.demoMode = new URLSearchParams(location.search).get('demo') === 'synthetic';

  // Load initial view from hash
  const hash = location.hash.slice(1) || 'overview';
  DCC.loadComponent(hash);

  // Handle nav clicks
  document.querySelectorAll('[data-view]').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      location.hash = view;
      DCC.loadComponent(view);
    });
  });
});
"""
