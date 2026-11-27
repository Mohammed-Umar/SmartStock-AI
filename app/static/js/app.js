/**
 * SmartStock AI: Modern Frontend Application Controller
 * Handles REST API communication, real-time Chart.js rendering,
 * explainable prediction visualizations, and proactive household inventory workflows.
 */

// Application State
const state = {
  activeView: 'dashboard',
  items: [],
  predictions: [],
  anomalies: [],
  shoppingList: [],
  stats: null,
  charts: {
    stockHealth: null,
    categorySpending: null,
    monthlyTrend: null,
    budgetCategory: null,
  },
  anomalyStatusFilter: 'UNRESOLVED',
};

// Initial Setup on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupModals();
  setupFormHandlers();
  refreshAllData();
});

// ==========================================================================
// Navigation & Views
// ==========================================================================

function setupNavigation() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const view = tab.getAttribute('data-view');
      switchView(view);
    });
  });
}

function switchView(viewName) {
  state.activeView = viewName;

  // Update tabs
  document.querySelectorAll('.nav-tab').forEach(t => {
    t.classList.toggle('active', t.getAttribute('data-view') === viewName);
  });

  // Update view sections
  document.querySelectorAll('.content-view').forEach(v => {
    v.classList.toggle('active', v.id === `view-${viewName}`);
  });

  // Load view-specific data
  if (viewName === 'dashboard') {
    renderDashboard();
  } else if (viewName === 'inventory') {
    loadInventory();
  } else if (viewName === 'predictions') {
    loadPredictions();
  } else if (viewName === 'anomalies') {
    loadAnomalies();
  } else if (viewName === 'shopping') {
    loadShoppingList();
  } else if (viewName === 'budget') {
    loadBudgetAnalytics();
  }
}

// ==========================================================================
// Master Data Refresh
// ==========================================================================

async function refreshAllData() {
  await Promise.all([
    fetchDashboardStats(),
    loadInventory(),
    loadPredictions(),
    loadAnomalies(),
    loadShoppingList(),
  ]);
  renderDashboard();
}

// ==========================================================================
// 1. Dashboard View Logic
// ==========================================================================

async function fetchDashboardStats() {
  try {
    const res = await fetch('/api/analytics/dashboard');
    if (!res.ok) throw new Error('Failed to fetch dashboard stats');
    const data = await res.json();
    state.stats = data;

    // Update KPI UI
    document.getElementById('dash-total-items').textContent = data.total_items;
    document.getElementById('dash-low-stock').textContent = data.low_stock_count;
    document.getElementById('dash-predicted-refills').textContent = data.predicted_refills_count;
    document.getElementById('dash-monthly-spend').textContent = `$${data.monthly_spending.toFixed(2)}`;
    document.getElementById('dash-waste-saved').textContent = `$${data.waste_prevented_cost.toFixed(2)}`;

    // Update Nav Badges
    document.getElementById('nav-item-count').textContent = data.total_items;
    document.getElementById('nav-anomaly-badge').textContent = data.active_anomalies_count;
    document.getElementById('nav-anomaly-badge').style.display = data.active_anomalies_count > 0 ? 'inline-flex' : 'none';

    // Urgent Banner
    const banner = document.getElementById('dash-urgent-banner');
    const bannerTitle = document.getElementById('urgent-banner-title');
    const bannerText = document.getElementById('urgent-banner-text');

    if (data.low_stock_count > 0 || data.predicted_refills_count > 0) {
      banner.style.display = 'flex';
      bannerTitle.textContent = `${data.low_stock_count} Critical / Low-Stock Item(s) Detected`;
      bannerText.textContent = `${data.predicted_refills_count} item(s) are forecasted to deplete completely within the next 5 days. Restock advised.`;
    } else {
      banner.style.display = 'none';
    }
  } catch (err) {
    console.error('Error fetching dashboard stats:', err);
  }
}

async function renderDashboard() {
  await fetchDashboardStats();
  renderQuickConsumeFavorites();
  renderRecentActivity();
  renderDashboardCharts();
}

function renderQuickConsumeFavorites() {
  const container = document.getElementById('quick-consume-container');
  container.innerHTML = '';

  // Show top items with quick consume buttons
  const frequentItems = state.items.slice(0, 6);
  if (frequentItems.length === 0) {
    container.innerHTML = '<div class="text-muted text-sm">No items available to consume.</div>';
    return;
  }

  frequentItems.forEach(item => {
    const el = document.createElement('div');
    el.className = 'quick-consume-item';

    // Determine quick decrement amount
    let quickAmount = 1;
    if (item.unit === 'L' || item.unit === 'kg') quickAmount = 0.25;
    else if (item.unit === 'g') quickAmount = 25;
    else if (item.unit === 'ml') quickAmount = 50;

    el.innerHTML = `
      <div class="quick-consume-info">
        <span class="quick-consume-name">${escapeHtml(item.name)}</span>
        <span class="quick-consume-stock">${item.current_quantity} ${item.unit} in stock</span>
      </div>
      <div class="quick-btn-group">
        <button class="btn btn-secondary btn-xs btn-stepper-btn" onclick="quickConsume(${item.id}, ${quickAmount})" title="Consume -${quickAmount} ${item.unit}">
          -${quickAmount}
        </button>
        <button class="btn btn-secondary btn-xs btn-stepper-btn" onclick="quickRestockItem(${item.id}, ${quickAmount})" title="Add +${quickAmount} ${item.unit}">
          +${quickAmount}
        </button>
        <button class="btn btn-primary btn-xs" onclick="openLogConsumptionModal(${item.id})" title="Custom Usage">
          Custom
        </button>
      </div>
    `;
    container.appendChild(el);
  });
}

async function renderRecentActivity() {
  const feed = document.getElementById('dashboard-activity-feed');
  try {
    const res = await fetch('/api/consumption?limit=6');
    const logs = await res.json();
    feed.innerHTML = '';

    if (logs.length === 0) {
      feed.innerHTML = '<div class="text-muted text-sm" style="padding: 10px;">No recent consumption recorded.</div>';
      return;
    }

    logs.forEach(log => {
      const itemEl = document.createElement('div');
      itemEl.className = 'activity-item';
      const isWaste = log.is_waste;
      itemEl.innerHTML = `
        <div class="activity-main">
          <div class="activity-dot ${isWaste ? 'waste' : ''}"></div>
          <div>
            <strong>${escapeHtml(log.item_name || 'Item')}</strong>: ${log.quantity_consumed} ${log.unit || ''}
            <div class="text-muted text-sm">${escapeHtml(log.reason)}</div>
          </div>
        </div>
        <div class="anomaly-meta">${log.consumption_date}</div>
      `;
      feed.appendChild(itemEl);
    });
  } catch (err) {
    console.error('Error fetching activity:', err);
  }
}

async function renderDashboardCharts() {
  try {
    // 1. Stock Health Doughnut Chart
    const healthRes = await fetch('/api/analytics/stock-health');
    const healthData = await healthRes.json();

    const ctxHealth = document.getElementById('chart-stock-health').getContext('2d');
    if (state.charts.stockHealth) state.charts.stockHealth.destroy();

    state.charts.stockHealth = new Chart(ctxHealth, {
      type: 'doughnut',
      data: {
        labels: healthData.labels,
        datasets: [{
          data: healthData.data,
          backgroundColor: ['#EF4444', '#F59E0B', '#3B82F6', '#10B981'],
          borderWidth: 2,
          borderColor: '#131B2B',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: '#94A3B8', font: { family: 'Plus Jakarta Sans', size: 11 } } },
        },
      },
    });

    // 2. Category Spending Chart
    const spendRes = await fetch('/api/analytics/spending');
    const spendData = await spendRes.json();

    const ctxSpend = document.getElementById('chart-category-spending').getContext('2d');
    if (state.charts.categorySpending) state.charts.categorySpending.destroy();

    state.charts.categorySpending = new Chart(ctxSpend, {
      type: 'bar',
      data: {
        labels: spendData.categories,
        datasets: [{
          label: 'Total Spent ($)',
          data: spendData.category_costs,
          backgroundColor: '#6366F1',
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#64748B', font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { color: '#64748B' }, grid: { color: '#1E293B' } },
        },
        plugins: {
          legend: { display: false },
        },
      },
    });
  } catch (err) {
    console.error('Error rendering dashboard charts:', err);
  }
}

// ==========================================================================
// 2. Inventory Management Logic
// ==========================================================================

let filterTimeout = null;
function debounceFilterItems() {
  clearTimeout(filterTimeout);
  filterTimeout = setTimeout(loadInventory, 250);
}

function filterItems() {
  loadInventory();
}

async function loadInventory() {
  try {
    const search = document.getElementById('inv-search-input')?.value.trim() || '';
    const category = document.getElementById('inv-cat-filter')?.value || 'All';
    const status = document.getElementById('inv-status-filter')?.value || 'ALL';

    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (category && category !== 'All') params.append('category', category);
    if (status && status !== 'ALL') params.append('status_filter', status);

    const res = await fetch(`/api/items?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to load items');
    const items = await res.json();
    state.items = items;

    // Populate table
    const tbody = document.getElementById('inventory-table-body');
    tbody.innerHTML = '';

    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted" style="padding: 30px;">No inventory items match the selected filter.</td></tr>`;
      return;
    }

    items.forEach(item => {
      const tr = document.createElement('tr');

      // Status badge and percent calculation
      const pct = Math.min(100, Math.round((item.current_quantity / item.optimal_quantity) * 100));
      let fillClass = 'good';
      let statusBadge = '<span class="badge badge-success">Good</span>';

      if (item.stock_status === 'CRITICAL' || item.stock_status === 'OUT_OF_STOCK') {
        fillClass = 'critical';
        statusBadge = '<span class="badge badge-danger">Critical</span>';
      } else if (item.stock_status === 'LOW') {
        fillClass = 'low';
        statusBadge = '<span class="badge badge-warning">Low Stock</span>';
      } else if (item.stock_status === 'EXPIRING_SOON') {
        fillClass = 'low';
        statusBadge = '<span class="badge badge-danger">Expiring Soon</span>';
      }

      const daysText = item.days_remaining !== null ? `${item.days_remaining}d left` : 'Analyzing';

      let quickAmount = 1;
      if (item.unit === 'L' || item.unit === 'kg') quickAmount = 0.25;
      else if (item.unit === 'g') quickAmount = 25;
      else if (item.unit === 'ml') quickAmount = 50;

      tr.innerHTML = `
        <td>
          <div style="font-weight: 700;">${escapeHtml(item.name)}</div>
          <span class="badge badge-muted" style="margin-top: 3px;">${escapeHtml(item.category)}</span>
        </td>
        <td>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div>
              <span style="font-family: var(--font-mono); font-weight: 700; font-size: 1rem;">${item.current_quantity}</span>
              <span class="text-muted">${item.unit}</span>
              <div class="text-muted text-sm">Target: ${item.optimal_quantity} ${item.unit}</div>
            </div>
            <div class="stepper-btn-group">
              <button class="btn-stepper" onclick="quickConsume(${item.id}, ${quickAmount})" title="Consume -${quickAmount} ${item.unit}">−</button>
              <button class="btn-stepper" onclick="quickRestockItem(${item.id}, ${quickAmount})" title="Add +${quickAmount} ${item.unit}">+</button>
            </div>
          </div>
        </td>
        <td>
          <div class="progress-wrapper">
            <div style="display: flex; justify-content: space-between; font-size: 0.72rem;">
              <span>${pct}%</span>
              ${statusBadge}
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill ${fillClass}" style="width: ${pct}%;"></div>
            </div>
          </div>
        </td>
        <td>
          <div style="font-size: 0.82rem; font-weight: 600;">${daysText}</div>
          <span class="text-muted text-sm">Refill: ${item.predicted_refill_date || 'N/A'}</span>
        </td>
        <td>
          <span style="font-family: var(--font-mono); font-weight: 600;">$${item.cost_per_unit.toFixed(2)}</span>
          <span class="text-muted text-sm">/${item.unit}</span>
        </td>
        <td>
          ${item.expiry_date ? `<span style="font-size: 0.82rem;">${item.expiry_date}</span>` : '<span class="text-muted text-sm">N/A</span>'}
        </td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-accent btn-xs" onclick="openLogConsumptionModal(${item.id})">Consume</button>
            <button class="btn btn-secondary btn-xs" onclick="openEditItemModal(${item.id})">Edit</button>
            <button class="btn btn-danger btn-xs" onclick="deleteItem(${item.id})">Delete</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading inventory:', err);
  }
}

// ==========================================================================
// 3. AI Refills & Predictions Logic
// ==========================================================================

async function loadPredictions() {
  try {
    const res = await fetch('/api/predictions');
    if (!res.ok) throw new Error('Failed to load predictions');
    const predictions = await res.json();
    state.predictions = predictions;

    const container = document.getElementById('predictions-cards-container');
    container.innerHTML = '';

    predictions.forEach(p => {
      const card = document.createElement('div');
      card.className = 'prediction-card';

      let urgBadge = '<span class="badge badge-success">ADEQUATE</span>';
      if (p.urgency === 'CRITICAL') urgBadge = '<span class="badge badge-danger">CRITICAL REFILL</span>';
      else if (p.urgency === 'LOW') urgBadge = '<span class="badge badge-warning">LOW STOCK</span>';
      else if (p.urgency === 'MODERATE') urgBadge = '<span class="badge badge-primary">MODERATE</span>';

      const exp = p.explainability;
      const reasonsHtml = exp.reasons.map(r => `<li>${escapeHtml(r)}</li>`).join('');

      card.innerHTML = `
        <div class="prediction-header">
          <div>
            <div class="pred-item-title">${escapeHtml(p.item_name)}</div>
            <div class="pred-item-cat">${escapeHtml(p.category)}</div>
          </div>
          ${urgBadge}
        </div>

        <div class="prediction-metrics">
          <div class="pred-metric">
            <span class="pred-metric-lbl">Current Stock</span>
            <span class="pred-metric-val">${p.current_quantity} <span style="font-size: 0.8rem; font-weight: 500;">${p.unit}</span></span>
          </div>
          <div class="pred-metric">
            <span class="pred-metric-lbl">Daily Burn Rate</span>
            <span class="pred-metric-val">${p.daily_burn_rate} <span style="font-size: 0.8rem; font-weight: 500;">${p.unit}/day</span></span>
          </div>
          <div class="pred-metric">
            <span class="pred-metric-lbl">Days Remaining</span>
            <span class="pred-metric-val text-primary">${p.days_remaining}d</span>
          </div>
          <div class="pred-metric">
            <span class="pred-metric-lbl">Predicted Refill Date</span>
            <span class="pred-metric-val" style="font-size: 1.05rem;">${p.predicted_refill_date}</span>
          </div>
        </div>

        <div class="pred-explain-box">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="pred-algo-badge">${escapeHtml(exp.algorithm_used)}</span>
            <span class="badge badge-primary" style="font-size: 0.68rem;">${Math.round(exp.confidence_score * 100)}% Confidence</span>
          </div>
          <ul class="pred-reasons-list">
            ${reasonsHtml}
          </ul>
          <div style="font-size: 0.78rem; color: #34D399; margin-top: 4px; font-weight: 600;">
            Recommendation: ${escapeHtml(exp.recommendation)}
          </div>
        </div>

        <div class="pred-actions">
          <button class="btn btn-primary btn-sm" style="width: 100%;" onclick="quickAddToShoppingList(${p.item_id})">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
            </svg>
            Add Refill to Shopping List
          </button>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading predictions:', err);
  }
}

// ==========================================================================
// 4. Anomalies & Waste Alerts Logic
// ==========================================================================

function filterAnomalies(status) {
  state.anomalyStatusFilter = status;
  document.querySelectorAll('#anomaly-filter-pills .pill-tab').forEach(p => {
    p.classList.toggle('active', p.getAttribute('data-status') === status);
  });
  loadAnomalies();
}

async function loadAnomalies() {
  try {
    const status = state.anomalyStatusFilter;
    const res = await fetch(`/api/anomalies?status=${status}`);
    if (!res.ok) throw new Error('Failed to load anomalies');
    const anomalies = await res.json();
    state.anomalies = anomalies;

    const container = document.getElementById('anomalies-container');
    container.innerHTML = '';

    if (anomalies.length === 0) {
      container.innerHTML = `
        <div class="card" style="padding: 40px; text-align: center; color: var(--text-muted);">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-bottom: 8px; color: #10B981;">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
          <div>All clear! No unusual consumption spikes or food waste alerts detected.</div>
        </div>
      `;
      return;
    }

    anomalies.forEach(anom => {
      const card = document.createElement('div');
      card.className = `anomaly-card severity-${anom.severity}`;

      let severityBadge = '<span class="badge badge-danger">HIGH SEVERITY</span>';
      if (anom.severity === 'MEDIUM') severityBadge = '<span class="badge badge-warning">MEDIUM</span>';
      else if (anom.severity === 'LOW') severityBadge = '<span class="badge badge-primary">LOW</span>';

      const isResolved = anom.status !== 'UNRESOLVED';

      card.innerHTML = `
        <div class="anomaly-info">
          <div class="anomaly-top">
            <span class="anomaly-item-name">${escapeHtml(anom.item_name)}</span>
            <span class="badge badge-muted">${escapeHtml(anom.category)}</span>
            ${severityBadge}
            ${isResolved ? `<span class="badge badge-muted">${escapeHtml(anom.status)}</span>` : ''}
          </div>
          <div class="anomaly-desc">${escapeHtml(anom.description)}</div>
          <div class="anomaly-meta">Anomaly Score: ${anom.anomaly_score} • Detected: ${anom.detected_at}</div>
        </div>

        <div style="display: flex; gap: 8px;">
          ${!isResolved ? `
            <button class="btn btn-secondary btn-xs" onclick="resolveAnomaly(${anom.id}, 'ACKNOWLEDGED')">
              Acknowledge
            </button>
            <button class="btn btn-danger btn-xs" onclick="resolveAnomaly(${anom.id}, 'DISMISSED')">
              Dismiss
            </button>
          ` : `
            <span class="text-muted text-sm">Resolved</span>
          `}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading anomalies:', err);
  }
}

async function triggerAnomalyScan() {
  try {
    const res = await fetch('/api/anomalies/detect-all', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    await loadAnomalies();
    await fetchDashboardStats();
  } catch (err) {
    showToast('Failed to execute anomaly scan', 'danger');
  }
}

async function resolveAnomaly(id, action) {
  try {
    const res = await fetch(`/api/anomalies/${id}/resolve?action=${action}`, { method: 'PUT' });
    if (!res.ok) throw new Error('Failed to resolve anomaly');
    showToast(`Anomaly marked as ${action}`, 'info');
    await loadAnomalies();
    await fetchDashboardStats();
  } catch (err) {
    showToast('Failed to resolve anomaly', 'danger');
  }
}

// ==========================================================================
// 5. Smart Shopping List Logic
// ==========================================================================

async function loadShoppingList() {
  try {
    const res = await fetch('/api/shopping?include_purchased=true');
    if (!res.ok) throw new Error('Failed to load shopping list');
    const items = await res.json();
    state.shoppingList = items;

    const tbody = document.getElementById('shopping-table-body');
    tbody.innerHTML = '';

    let activeCount = 0;
    let totalCost = 0;

    items.forEach(item => {
      if (!item.is_purchased) {
        activeCount++;
        totalCost += item.estimated_cost;
      }

      const tr = document.createElement('tr');
      if (item.is_purchased) {
        tr.style.opacity = '0.5';
      }

      let urgBadge = '<span class="badge badge-warning">RECOMMENDED</span>';
      if (item.urgency === 'URGENT') urgBadge = '<span class="badge badge-danger">URGENT</span>';
      else if (item.urgency === 'PLANNED') urgBadge = '<span class="badge badge-muted">PLANNED</span>';

      tr.innerHTML = `
        <td>${urgBadge}</td>
        <td>
          <div style="font-weight: 700;">${escapeHtml(item.item_name)}</div>
          <span class="badge badge-muted">${escapeHtml(item.category)}</span>
        </td>
        <td>
          <span style="font-family: var(--font-mono); font-weight: 700;">${item.quantity_needed}</span> ${item.unit}
        </td>
        <td>
          <span style="font-family: var(--font-mono); font-weight: 600; color: #34D399;">$${item.estimated_cost.toFixed(2)}</span>
        </td>
        <td>
          <span style="font-size: 0.82rem; color: var(--text-secondary);">${escapeHtml(item.reason)}</span>
        </td>
        <td>
          ${item.is_purchased ? '<span class="badge badge-success">PURCHASED & RESTOCKED</span>' : '<span class="badge badge-primary">ACTIVE</span>'}
        </td>
        <td>
          <div style="display: flex; gap: 6px;">
            ${!item.is_purchased ? `
              <button class="btn btn-primary btn-xs" onclick="markPurchased(${item.id})">
                ✓ Restock
              </button>
            ` : ''}
            <button class="btn btn-danger btn-xs" onclick="deleteShoppingItem(${item.id})">✕</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById('shopping-item-count').textContent = activeCount;
    document.getElementById('shopping-total-cost').textContent = `$${totalCost.toFixed(2)}`;
    document.getElementById('nav-shopping-badge').textContent = activeCount;
    document.getElementById('nav-shopping-badge').style.display = activeCount > 0 ? 'inline-flex' : 'none';

    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted" style="padding: 30px;">Your shopping cart is currently empty. Click "Auto-Generate AI Recommendations" to scan inventory.</td></tr>`;
    }
  } catch (err) {
    console.error('Error loading shopping list:', err);
  }
}

async function generateShoppingRecommendations() {
  try {
    const res = await fetch('/api/shopping/generate', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    await loadShoppingList();
    await fetchDashboardStats();
  } catch (err) {
    showToast('Failed to auto-generate recommendations', 'danger');
  }
}

async function quickAddToShoppingList(itemId) {
  const item = state.items.find(i => i.id === itemId);
  if (!item) return;

  const needed = Math.max(Math.round(item.optimal_quantity - item.current_quantity), Math.round(item.min_threshold));
  const payload = {
    item_id: item.id,
    item_name: item.name,
    category: item.category,
    quantity_needed: needed,
    unit: item.unit,
    estimated_cost: Math.round(needed * item.cost_per_unit * 100) / 100,
    urgency: item.current_quantity <= item.min_threshold ? 'URGENT' : 'RECOMMENDED',
    reason: `One-click refill recommendation based on AI forecast.`,
  };

  try {
    const res = await fetch('/api/shopping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || 'Could not add item', 'danger');
      return;
    }

    showToast(`Added ${item.name} to smart shopping list.`, 'success');
    await loadShoppingList();
  } catch (err) {
    showToast('Network error adding to shopping list', 'danger');
  }
}

async function markPurchased(shoppingId) {
  try {
    const res = await fetch(`/api/shopping/${shoppingId}/purchase`, { method: 'PUT' });
    if (!res.ok) throw new Error('Purchase action failed');
    const data = await res.json();
    showToast(data.message, 'success');
    await loadShoppingList();
    await loadInventory();
    await fetchDashboardStats();
  } catch (err) {
    showToast('Failed to complete purchase', 'danger');
  }
}

async function deleteShoppingItem(shoppingId) {
  try {
    const res = await fetch(`/api/shopping/${shoppingId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete');
    showToast('Removed item from shopping list', 'info');
    await loadShoppingList();
  } catch (err) {
    showToast('Failed to delete shopping item', 'danger');
  }
}

// ==========================================================================
// 6. Budget & Analytics Logic
// ==========================================================================

async function loadBudgetAnalytics() {
  try {
    const [statsRes, spendRes] = await Promise.all([
      fetch('/api/analytics/dashboard'),
      fetch('/api/analytics/spending'),
    ]);
    const stats = await statsRes.json();
    const spend = await spendRes.json();

    document.getElementById('budget-mtd-spend').textContent = `$${stats.monthly_spending.toFixed(2)}`;
    document.getElementById('budget-waste-prevented').textContent = `$${stats.waste_prevented_cost.toFixed(2)}`;
    document.getElementById('budget-waste-units').textContent = `~${stats.waste_prevented_units} units preserved`;
    document.getElementById('budget-smart-orders').textContent = Math.round(stats.waste_prevented_units / 1.8);

    // Monthly Trend Bar Chart
    const ctxTrend = document.getElementById('chart-monthly-trend').getContext('2d');
    if (state.charts.monthlyTrend) state.charts.monthlyTrend.destroy();

    state.charts.monthlyTrend = new Chart(ctxTrend, {
      type: 'bar',
      data: {
        labels: spend.months,
        datasets: [{
          label: 'Total Monthly Expenditure ($)',
          data: spend.monthly_costs,
          backgroundColor: '#10B981',
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#64748B' }, grid: { display: false } },
          y: { ticks: { color: '#64748B' }, grid: { color: '#1E293B' } },
        },
      },
    });

    // Category Breakdown Doughnut Chart
    const ctxCat = document.getElementById('chart-budget-category').getContext('2d');
    if (state.charts.budgetCategory) state.charts.budgetCategory.destroy();

    state.charts.budgetCategory = new Chart(ctxCat, {
      type: 'doughnut',
      data: {
        labels: spend.categories,
        datasets: [{
          data: spend.category_costs,
          backgroundColor: ['#6366F1', '#06B6D4', '#10B981', '#F59E0B', '#EC4899', '#8B5CF6'],
          borderWidth: 2,
          borderColor: '#131B2B',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: '#94A3B8', font: { size: 10 } } },
        },
      },
    });
  } catch (err) {
    console.error('Error loading budget analytics:', err);
  }
}

// ==========================================================================
// 7. Modals and Forms
// ==========================================================================

function setupModals() {
  document.getElementById('btn-open-add-item').addEventListener('click', openAddItemModal);
  document.getElementById('btn-open-log-consumption').addEventListener('click', () => openLogConsumptionModal());
  document.getElementById('btn-reset-demo').addEventListener('click', resetDemoData);
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

function openAddItemModal() {
  document.getElementById('modal-item-title').textContent = 'Add Inventory Item';
  document.getElementById('item-form-id').value = '';
  document.getElementById('form-item').reset();
  document.getElementById('item-purchase-date').value = new Date().toISOString().split('T')[0];
  openModal('modal-item');
}

function openEditItemModal(itemId) {
  const item = state.items.find(i => i.id === itemId);
  if (!item) return;

  document.getElementById('modal-item-title').textContent = `Edit ${item.name}`;
  document.getElementById('item-form-id').value = item.id;
  document.getElementById('item-name').value = item.name;
  document.getElementById('item-category').value = item.category;
  document.getElementById('item-unit').value = item.unit;
  document.getElementById('item-current-qty').value = item.current_quantity;
  document.getElementById('item-min-threshold').value = item.min_threshold;
  document.getElementById('item-optimal-qty').value = item.optimal_quantity;
  document.getElementById('item-cost').value = item.cost_per_unit;
  document.getElementById('item-purchase-date').value = item.purchase_date;
  document.getElementById('item-expiry-date').value = item.expiry_date || '';
  document.getElementById('item-notes').value = item.notes || '';

  openModal('modal-item');
}

function openLogConsumptionModal(itemId = null) {
  const select = document.getElementById('consume-item-id');
  select.innerHTML = '';

  state.items.forEach(item => {
    const opt = document.createElement('option');
    opt.value = item.id;
    opt.textContent = `${item.name} (${item.current_quantity} ${item.unit} available)`;
    opt.setAttribute('data-unit', item.unit);
    if (itemId && item.id === itemId) opt.selected = true;
    select.appendChild(opt);
  });

  document.getElementById('consume-date').value = new Date().toISOString().split('T')[0];
  document.getElementById('consume-qty').value = '';
  document.getElementById('consume-is-waste').checked = false;
  handleConsumeItemSelect();
  openModal('modal-consumption');
}

function handleConsumeItemSelect() {
  const select = document.getElementById('consume-item-id');
  const opt = select.options[select.selectedIndex];
  if (opt) {
    document.getElementById('consume-unit-addon').textContent = opt.getAttribute('data-unit') || 'units';
  }
}

function openAddShoppingModal() {
  document.getElementById('form-shopping').reset();
  openModal('modal-shopping');
}

// Quick consume helper
async function quickConsume(itemId, qty) {
  try {
    const res = await fetch('/api/consumption/quick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_id: itemId, quantity: qty }),
    });

    if (!res.ok) throw new Error('Consumption logging failed');
    const data = await res.json();
    showToast(`Consumed ${qty} ${data.unit || 'units'} of ${data.item_name}.`, 'info');

    // Refresh UI
    await loadInventory();
    await fetchDashboardStats();
    if (state.activeView === 'dashboard') {
      renderRecentActivity();
      renderQuickConsumeFavorites();
    }
  } catch (err) {
    showToast('Failed to log consumption', 'danger');
  }
}

async function quickRestockItem(itemId, amount) {
  const item = state.items.find(i => i.id === itemId);
  if (!item) return;

  const newQty = Math.round((item.current_quantity + amount) * 100) / 100;
  const payload = {
    name: item.name,
    category: item.category,
    unit: item.unit,
    current_quantity: newQty,
    min_threshold: item.min_threshold,
    optimal_quantity: item.optimal_quantity,
    cost_per_unit: item.cost_per_unit,
    purchase_date: item.purchase_date,
    expiry_date: item.expiry_date || null,
    notes: item.notes || ''
  };

  try {
    const res = await fetch(`/api/items/${itemId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Restock failed');
    showToast(`Restocked +${amount} ${item.unit} to ${item.name} (${newQty} in stock).`, 'success');
    await loadInventory();
    await fetchDashboardStats();
    if (state.activeView === 'dashboard') {
      renderQuickConsumeFavorites();
    }
  } catch (err) {
    showToast('Failed to restock item', 'danger');
  }
}

async function clearPurchasedItems() {
  const purchased = state.shoppingList.filter(i => i.is_purchased);
  if (purchased.length === 0) {
    showToast('No purchased items to clear.', 'info');
    return;
  }
  if (!confirm(`Clear ${purchased.length} purchased item(s) from history?`)) return;

  try {
    await Promise.all(purchased.map(item => fetch(`/api/shopping/${item.id}`, { method: 'DELETE' })));
    showToast(`Cleared ${purchased.length} completed purchases.`, 'success');
    await loadShoppingList();
    await fetchDashboardStats();
  } catch (err) {
    showToast('Failed to clear items', 'danger');
  }
}

async function deleteItem(itemId) {
  if (!confirm('Are you sure you want to delete this inventory item and its logs?')) return;

  try {
    const res = await fetch(`/api/items/${itemId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
    showToast('Item deleted successfully', 'info');
    await refreshAllData();
  } catch (err) {
    showToast('Could not delete item', 'danger');
  }
}

async function resetDemoData() {
  if (!confirm('Reset database to realistic sample household dataset? Any custom items will be cleared.')) return;

  try {
    const res = await fetch('/api/analytics/reset-demo', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    await refreshAllData();
  } catch (err) {
    showToast('Failed to reset demo dataset', 'danger');
  }
}

function setupFormHandlers() {
  // Form submission handled via onsubmit in HTML
}

async function handleItemFormSubmit(e) {
  e.preventDefault();
  const id = document.getElementById('item-form-id').value;

  const payload = {
    name: document.getElementById('item-name').value.trim(),
    category: document.getElementById('item-category').value,
    unit: document.getElementById('item-unit').value.trim(),
    current_quantity: parseFloat(document.getElementById('item-current-qty').value),
    min_threshold: parseFloat(document.getElementById('item-min-threshold').value),
    optimal_quantity: parseFloat(document.getElementById('item-optimal-qty').value),
    cost_per_unit: parseFloat(document.getElementById('item-cost').value),
    purchase_date: document.getElementById('item-purchase-date').value,
    expiry_date: document.getElementById('item-expiry-date').value || null,
    notes: document.getElementById('item-notes').value.trim(),
  };

  try {
    const url = id ? `/api/items/${id}` : '/api/items';
    const method = id ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to save item');
    }

    closeModal('modal-item');
    showToast(id ? 'Item updated successfully' : 'Item added to inventory', 'success');
    await refreshAllData();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function handleConsumptionSubmit(e) {
  e.preventDefault();
  const itemId = parseInt(document.getElementById('consume-item-id').value);
  const qty = parseFloat(document.getElementById('consume-qty').value);
  const date = document.getElementById('consume-date').value;
  const reason = document.getElementById('consume-reason').value;
  const isWaste = document.getElementById('consume-is-waste').checked;

  const payload = {
    item_id: itemId,
    quantity_consumed: qty,
    consumption_date: date,
    reason: reason,
    is_waste: isWaste,
  };

  try {
    const res = await fetch('/api/consumption', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not record usage');
    }

    closeModal('modal-consumption');
    showToast(`Logged usage: ${qty} units recorded.`, 'info');
    await refreshAllData();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function handleShoppingSubmit(e) {
  e.preventDefault();

  const payload = {
    item_name: document.getElementById('shop-item-name').value.trim(),
    category: document.getElementById('shop-category').value,
    unit: document.getElementById('shop-unit').value.trim(),
    quantity_needed: parseFloat(document.getElementById('shop-qty').value),
    estimated_cost: parseFloat(document.getElementById('shop-cost').value),
    urgency: document.getElementById('shop-urgency').value,
    reason: document.getElementById('shop-reason').value.trim() || 'Manual Household Request',
  };

  try {
    const res = await fetch('/api/shopping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not add shopping item');
    }

    closeModal('modal-shopping');
    showToast('Added item to shopping list', 'success');
    await loadShoppingList();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// ==========================================================================
// Toasts & Utility Functions
// ==========================================================================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
