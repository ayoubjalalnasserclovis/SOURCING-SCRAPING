/**
 * Mubawab Explorer - Application Logic
 * Fast, reactive client-side filtering, sorting, pagination, and modal view.
 */

(function () {
  'use strict';

  // State
  let allListings = [];
  let filteredListings = [];
  let currentPage = 1;
  const itemsPerPage = 24;

  const filters = {
    search: '',
    platform: 'all',
    trans: 'all',
    type: 'all',
    quartier: 'all',
    minPrice: null,
    maxPrice: null,
    minSurface: null,
    maxSurface: null,
    sortBy: 'default'
  };

  // DOM Elements
  const searchInput = document.getElementById('search-input');
  const clearSearchBtn = document.getElementById('clear-search');
  const transBtns = document.querySelectorAll('.trans-btn');
  const platformSelect = document.getElementById('filter-platform');
  const typeSelect = document.getElementById('filter-type');
  const quartierSelect = document.getElementById('filter-quartier');
  const priceMinInput = document.getElementById('price-min');
  const priceMaxInput = document.getElementById('price-max');
  const surfaceMinInput = document.getElementById('surface-min');
  const surfaceMaxInput = document.getElementById('surface-max');
  const sortSelect = document.getElementById('sort-select');
  const resetBtn = document.getElementById('reset-filters-btn');
  const emptyResetBtn = document.getElementById('empty-reset-btn');
  const resultsCountEl = document.getElementById('results-count');
  const gridEl = document.getElementById('listings-grid');
  const emptyStateEl = document.getElementById('empty-state');
  const paginationWrapper = document.getElementById('pagination-wrapper');
  const paginationNumbers = document.getElementById('pagination-numbers');
  const prevBtn = document.getElementById('prev-page-btn');
  const nextBtn = document.getElementById('next-page-btn');
  
  // Modal Elements
  const modal = document.getElementById('property-modal');
  const modalBackdrop = document.getElementById('modal-backdrop');
  const modalClose = document.getElementById('modal-close');
  const modalContent = document.getElementById('modal-content');

  // KPI Elements
  const kpiTotal = document.getElementById('kpi-total');
  const kpiAvgPrice = document.getElementById('kpi-avg-price');
  const kpiTopQuartier = document.getElementById('kpi-top-quartier');
  const kpiTopType = document.getElementById('kpi-top-type');

  // -------------------------------------------------------------------------
  // Initialization
  // -------------------------------------------------------------------------
  function init() {
    if (window.MUBAWAB_COMPACT_DATA && window.MUBAWAB_COMPACT_DATA.records) {
      const pList = window.MUBAWAB_COMPACT_DATA.platforms || [];
      const tList = window.MUBAWAB_COMPACT_DATA.transactions || [];
      const hList = window.MUBAWAB_COMPACT_DATA.house_types || [];
      allListings = window.MUBAWAB_COMPACT_DATA.records.map(r => ({
        id: r[0],
        platform: pList[r[1]] || 'Autre',
        title: r[2],
        url: r[3],
        transaction_type: tList[r[4]] || 'Vente',
        house_type: hList[r[5]] || 'Bien',
        quartier: r[6],
        price_raw: r[7],
        price_mad: r[8],
        surface_m2: r[9],
        bedrooms: r[10],
        bathrooms: r[11],
        main_image: r[12]
      }));
      setupKPIs();
      populateDropdowns();
      applyFilters();
      bindEvents();
    } else if (window.MUBAWAB_DATA && Array.isArray(window.MUBAWAB_DATA)) {
      allListings = window.MUBAWAB_DATA;
      setupKPIs();
      populateDropdowns();
      applyFilters();
      bindEvents();
    } else {
      // Fallback: try fetching JSON
      fetch('./mubawab_complete_listings.json')
        .then(res => res.json())
        .then(data => {
          allListings = data;
          setupKPIs();
          populateDropdowns();
          applyFilters();
          bindEvents();
        })
        .catch(err => {
          resultsCountEl.innerHTML = '<span style="color:red">Erreur de chargement des données.</span>';
          console.error(err);
        });
    }
  }

  function setupKPIs() {
    if (window.MUBAWAB_STATS) {
      const stats = window.MUBAWAB_STATS;
      kpiTotal.textContent = stats.total.toLocaleString();
      kpiAvgPrice.textContent = stats.avg_price.toLocaleString() + ' DH';
      const topQ = Object.entries(stats.quartiers)[0];
      if (topQ) kpiTopQuartier.textContent = `${topQ[0]} (${topQ[1].toLocaleString()})`;
      const topT = Object.entries(stats.house_types)[0];
      if (topT) {
        const pct = Math.round((topT[1] / stats.total) * 100);
        kpiTopType.textContent = `${topT[0]} (${pct}%)`;
      }
    }
  }

  function populateDropdowns() {
    if (window.MUBAWAB_STATS) {
      const stats = window.MUBAWAB_STATS;
      if (platformSelect && stats.platforms) {
        const cur = platformSelect.value || 'all';
        platformSelect.innerHTML = `<option value="all">Toutes les plateformes (${stats.total.toLocaleString()})</option>` +
          Object.entries(stats.platforms).map(([p, cnt]) => `<option value="${escapeHtml(p)}">${escapeHtml(p)} (${cnt.toLocaleString()})</option>`).join('');
        platformSelect.value = cur;
      }
      if (quartierSelect && stats.quartiers) {
        const cur = quartierSelect.value || 'all';
        quartierSelect.innerHTML = '<option value="all">Tous les quartiers de Marrakech</option>' +
          Object.entries(stats.quartiers).map(([q, cnt]) => `<option value="${escapeHtml(q)}">${escapeHtml(q)} (${cnt.toLocaleString()})</option>`).join('');
        quartierSelect.value = cur;
      }
    }
  }

  // -------------------------------------------------------------------------
  // Filtering & Sorting Engine
  // -------------------------------------------------------------------------
  function applyFilters() {
    const q = filters.search.toLowerCase().trim();
    const platform = filters.platform;
    const trans = filters.trans;
    const type = filters.type;
    const quartier = filters.quartier;
    const minP = filters.minPrice;
    const maxP = filters.maxPrice;
    const minS = filters.minSurface;
    const maxS = filters.maxSurface;

    filteredListings = allListings.filter(item => {
      // Platform
      if (platform !== 'all' && item.platform !== platform) return false;

      // Transaction Type
      if (trans !== 'all' && item.transaction_type !== trans) return false;

      // House Type
      if (type !== 'all' && item.house_type !== type) return false;

      // Quartier
      if (quartier !== 'all' && item.quartier !== quartier) return false;

      // Price Range (supports both price_mad and price_numeric)
      const p = item.price_mad !== undefined ? item.price_mad : item.price_numeric;
      if (minP !== null && p !== null && p < minP) return false;
      if (maxP !== null && p !== null && p > maxP) return false;

      // Surface Range
      const s = item.surface_m2;
      if (minS !== null && s !== null && s < minS) return false;
      if (maxS !== null && s !== null && s > maxS) return false;

      // Keyword Search
      if (q) {
        const haystack = `${item.title} ${item.platform} ${item.quartier} ${item.house_type} ${item.features} ${item.description}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }

      return true;
    });

    // Apply Sorting
    sortListings();

    currentPage = 1;
    render();
  }

  function sortListings() {
    switch (filters.sortBy) {
      case 'price-asc':
        filteredListings.sort((a, b) => ((a.price_mad !== undefined ? a.price_mad : a.price_numeric) || 0) - ((b.price_mad !== undefined ? b.price_mad : b.price_numeric) || 0));
        break;
      case 'price-desc':
        filteredListings.sort((a, b) => ((b.price_mad !== undefined ? b.price_mad : b.price_numeric) || 0) - ((a.price_mad !== undefined ? a.price_mad : a.price_numeric) || 0));
        break;
      case 'surface-desc':
        filteredListings.sort((a, b) => (b.surface_m2 || 0) - (a.surface_m2 || 0));
        break;
      case 'images-desc':
        filteredListings.sort((a, b) => (b.images_count || 0) - (a.images_count || 0));
        break;
      default:
        // Default: keep natural ranking
        break;
    }
  }

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------
  function render() {
    const total = filteredListings.length;
    resultsCountEl.innerHTML = `Affichage de <strong>${total.toLocaleString()}</strong> annonce${total > 1 ? 's' : ''} trouvée${total > 1 ? 's' : ''}`;

    if (total === 0) {
      gridEl.innerHTML = '';
      emptyStateEl.style.display = 'block';
      paginationWrapper.style.display = 'none';
      return;
    }

    emptyStateEl.style.display = 'none';
    paginationWrapper.style.display = 'flex';

    // Pagination slice
    const startIndex = (currentPage - 1) * itemsPerPage;
    const pageItems = filteredListings.slice(startIndex, startIndex + itemsPerPage);

    // Build Cards HTML
    const cardsHtml = pageItems.map(item => createCardHtml(item)).join('');
    gridEl.innerHTML = cardsHtml;

    // Attach card click handlers
    const cards = gridEl.querySelectorAll('.card');
    cards.forEach(card => {
      card.addEventListener('click', (e) => {
        // Prevent modal if user clicked directly on original link
        if (e.target.closest('.btn-mubawab')) return;
        const id = card.getAttribute('data-id');
        openModal(id);
      });
    });

    renderPagination();
  }

  function createCardHtml(item) {
    const transClass = item.transaction_type === 'Location' ? 'badge-trans-location' : 'badge-trans-vente';
    const fallbackImg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300' fill='%23e2e8f0'%3E%3Crect width='400' height='300'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='16' fill='%2394a3b8'%3EPhoto non disponible%3C/text%3E%3C/svg%3E";
    const imgUrl = item.main_image || fallbackImg;

    // Features preview (first 3)
    let featuresHtml = '';
    if (item.features) {
      const featArr = item.features.split(',').map(f => f.trim()).filter(Boolean);
      featuresHtml = featArr.slice(0, 3).map(f => `<span class="feature-tag">${escapeHtml(f)}</span>`).join('');
      if (featArr.length > 3) {
        featuresHtml += `<span class="feature-tag">+${featArr.length - 3}</span>`;
      }
    }

    return `
      <article class="card" data-id="${item.id}">
        <div class="card-img-wrap">
          <img class="card-img" src="${imgUrl}" alt="${escapeHtml(item.title)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='${fallbackImg}';">
          <div class="card-badges">
            <span class="badge ${transClass}">${item.transaction_type || 'Vente'}</span>
            <span class="badge badge-platform">${escapeHtml(item.platform || 'Mubawab')}</span>
            <span class="badge badge-type">${item.house_type || 'Bien'}</span>
          </div>
          ${item.images_count > 0 ? `<span class="badge-photos">📸 ${item.images_count}</span>` : ''}
        </div>

        <div class="card-body">
          <div class="card-price">${escapeHtml(item.price_raw || 'Prix sur demande')}</div>
          <h2 class="card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h2>
          <div class="card-location">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
            ${escapeHtml(item.quartier || 'Marrakech')}
          </div>

          <div class="card-specs">
            ${item.surface_raw ? `<div class="spec-item"><span class="spec-icon">📐</span> ${escapeHtml(item.surface_raw)}</div>` : ''}
            ${item.bedrooms ? `<div class="spec-item"><span class="spec-icon">🛏️</span> ${escapeHtml(item.bedrooms)}</div>` : ''}
            ${item.bathrooms ? `<div class="spec-item"><span class="spec-icon">🚿</span> ${escapeHtml(item.bathrooms)}</div>` : ''}
            ${!item.surface_raw && !item.bedrooms && item.rooms ? `<div class="spec-item"><span class="spec-icon">🚪</span> ${escapeHtml(item.rooms)}</div>` : ''}
          </div>

          ${featuresHtml ? `<div class="card-features">${featuresHtml}</div>` : ''}

          <div class="card-footer">
            <button class="btn-details">
              Voir détails &rarr;
            </button>
            <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn-mubawab">
              Mubawab ↗
            </a>
          </div>
        </div>
      </article>
    `;
  }

  function renderPagination() {
    const totalPages = Math.ceil(filteredListings.length / itemsPerPage);
    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = currentPage === totalPages || totalPages === 0;

    let pagesHtml = '';
    const maxButtons = 5;
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);

    if (endPage - startPage < maxButtons - 1) {
      startPage = Math.max(1, endPage - maxButtons + 1);
    }

    if (startPage > 1) {
      pagesHtml += `<button class="page-num" data-page="1">1</button>`;
      if (startPage > 2) pagesHtml += `<span class="page-dots">...</span>`;
    }

    for (let p = startPage; p <= endPage; p++) {
      pagesHtml += `<button class="page-num ${p === currentPage ? 'active' : ''}" data-page="${p}">${p}</button>`;
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) pagesHtml += `<span class="page-dots">...</span>`;
      pagesHtml += `<button class="page-num" data-page="${totalPages}">${totalPages}</button>`;
    }

    paginationNumbers.innerHTML = pagesHtml;

    // Attach click events
    paginationNumbers.querySelectorAll('.page-num').forEach(btn => {
      btn.addEventListener('click', () => {
        const page = parseInt(btn.getAttribute('data-page'), 10);
        goToPage(page);
      });
    });
  }

  function goToPage(page) {
    currentPage = page;
    render();
    document.getElementById('filters-section').scrollIntoView({ behavior: 'smooth' });
  }

  // -------------------------------------------------------------------------
  // Modal Details
  // -------------------------------------------------------------------------
  function openModal(id) {
    const item = allListings.find(l => l.id == id);
    if (!item) return;

    const fallbackImg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='400' viewBox='0 0 800 400' fill='%23e2e8f0'%3E%3Crect width='800' height='400'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='20' fill='%2394a3b8'%3EPhoto non disponible%3C/text%3E%3C/svg%3E";
    const imgUrl = item.main_image || fallbackImg;

    // Amenities list
    let amenitiesHtml = '<p style="color:#64748b;font-size:13px">Non spécifié</p>';
    if (item.features) {
      const feats = item.features.split(',').map(f => f.trim()).filter(Boolean);
      if (feats.length > 0) {
        amenitiesHtml = feats.map(f => `<span class="feature-tag" style="font-size:12px;padding:5px 10px">${escapeHtml(f)}</span>`).join('');
      }
    }

    modalContent.innerHTML = `
      <img class="modal-hero-img" src="${imgUrl}" alt="${escapeHtml(item.title)}" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='${fallbackImg}';">
      <div class="modal-body">
        <div class="modal-price">${escapeHtml(item.price_raw || 'Prix sur demande')}</div>
        <h2 class="modal-title">${escapeHtml(item.title)}</h2>
        
        <div class="modal-meta-row">
          <span class="badge ${item.transaction_type === 'Location' ? 'badge-trans-location' : 'badge-trans-vente'}">${item.transaction_type || 'Vente'}</span>
          <span class="badge badge-type">${item.house_type || 'Bien'}</span>
          <span style="font-weight:600;color:#475569;display:flex;align-items:center;gap:4px">
            📍 ${escapeHtml(item.quartier || 'Marrakech')}
          </span>
          <span style="color:#94a3b8;font-size:12px">ID: ${item.id}</span>
        </div>

        <div class="modal-specs-grid">
          <div class="modal-spec-box">
            <span class="modal-spec-label">Surface</span>
            <span class="modal-spec-value">${escapeHtml(item.surface_raw || 'N/A')}</span>
          </div>
          <div class="modal-spec-box">
            <span class="modal-spec-label">Chambres</span>
            <span class="modal-spec-value">${escapeHtml(item.bedrooms || 'N/A')}</span>
          </div>
          <div class="modal-spec-box">
            <span class="modal-spec-label">Salles de bain</span>
            <span class="modal-spec-value">${escapeHtml(item.bathrooms || 'N/A')}</span>
          </div>
          <div class="modal-spec-box">
            <span class="modal-spec-label">Pièces</span>
            <span class="modal-spec-value">${escapeHtml(item.rooms || 'N/A')}</span>
          </div>
        </div>

        <div style="margin-bottom:20px">
          <div class="modal-desc-heading">Équipements & Prestations</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">${amenitiesHtml}</div>
        </div>

        <div>
          <div class="modal-desc-heading">Description</div>
          <div class="modal-desc">${escapeHtml(item.description || 'Aucune description fournie.')}</div>
        </div>

        <div class="modal-actions">
          <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary" style="flex:1;justify-content:center">
            Consulter l'annonce originale (${escapeHtml(item.platform || 'Source')}) ↗
          </a>
        </div>
      </div>
    `;

    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  // -------------------------------------------------------------------------
  // Event Listeners
  // -------------------------------------------------------------------------
  function bindEvents() {
    // Search input
    let searchDebounce;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchDebounce);
      clearSearchBtn.style.display = e.target.value ? 'block' : 'none';
      searchDebounce = setTimeout(() => {
        filters.search = e.target.value;
        applyFilters();
      }, 200);
    });

    clearSearchBtn.addEventListener('click', () => {
      searchInput.value = '';
      clearSearchBtn.style.display = 'none';
      filters.search = '';
      applyFilters();
    });

    // Transaction Toggle buttons
    transBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        transBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filters.trans = btn.getAttribute('data-trans');
        applyFilters();
      });
    });

    // Platform select
    if (platformSelect) {
      platformSelect.addEventListener('change', (e) => {
        filters.platform = e.target.value;
        applyFilters();
      });
    }

    // Type select
    typeSelect.addEventListener('change', (e) => {
      filters.type = e.target.value;
      applyFilters();
    });

    // Quartier select
    quartierSelect.addEventListener('change', (e) => {
      filters.quartier = e.target.value;
      applyFilters();
    });

    // Price inputs
    let priceDebounce;
    const onPriceChange = () => {
      clearTimeout(priceDebounce);
      priceDebounce = setTimeout(() => {
        filters.minPrice = priceMinInput.value ? parseInt(priceMinInput.value, 10) : null;
        filters.maxPrice = priceMaxInput.value ? parseInt(priceMaxInput.value, 10) : null;
        applyFilters();
      }, 300);
    };
    priceMinInput.addEventListener('input', onPriceChange);
    priceMaxInput.addEventListener('input', onPriceChange);

    // Surface inputs
    let surfaceDebounce;
    const onSurfaceChange = () => {
      clearTimeout(surfaceDebounce);
      surfaceDebounce = setTimeout(() => {
        filters.minSurface = surfaceMinInput.value ? parseInt(surfaceMinInput.value, 10) : null;
        filters.maxSurface = surfaceMaxInput.value ? parseInt(surfaceMaxInput.value, 10) : null;
        applyFilters();
      }, 300);
    };
    surfaceMinInput.addEventListener('input', onSurfaceChange);
    surfaceMaxInput.addEventListener('input', onSurfaceChange);

    // Sort select
    sortSelect.addEventListener('change', (e) => {
      filters.sortBy = e.target.value;
      sortListings();
      render();
    });

    // Reset filters
    const resetAll = () => {
      searchInput.value = '';
      clearSearchBtn.style.display = 'none';
      if (platformSelect) platformSelect.value = 'all';
      typeSelect.value = 'all';
      quartierSelect.value = 'all';
      priceMinInput.value = '';
      priceMaxInput.value = '';
      surfaceMinInput.value = '';
      surfaceMaxInput.value = '';
      sortSelect.value = 'default';

      transBtns.forEach(b => b.classList.remove('active'));
      document.querySelector('.trans-btn[data-trans="all"]').classList.add('active');

      filters.search = '';
      filters.platform = 'all';
      filters.trans = 'all';
      filters.type = 'all';
      filters.quartier = 'all';
      filters.minPrice = null;
      filters.maxPrice = null;
      filters.minSurface = null;
      filters.maxSurface = null;
      filters.sortBy = 'default';

      applyFilters();
    };

    resetBtn.addEventListener('click', resetAll);
    emptyResetBtn.addEventListener('click', resetAll);

    // Prev / Next Page
    prevBtn.addEventListener('click', () => {
      if (currentPage > 1) goToPage(currentPage - 1);
    });
    nextBtn.addEventListener('click', () => {
      const totalPages = Math.ceil(filteredListings.length / itemsPerPage);
      if (currentPage < totalPages) goToPage(currentPage + 1);
    });

    // Modal close events
    modalClose.addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', closeModal);
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('active')) {
        closeModal();
      }
    });
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Start app
  document.addEventListener('DOMContentLoaded', init);

})();
