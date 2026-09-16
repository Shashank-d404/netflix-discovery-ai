/**
 * NETFLIX — The Discovery Problem: AI-Powered Content Discovery
 * Frontend Application Controller (Vanilla JavaScript)
 *
 * Interacts exclusively with Flask REST endpoints:
 *   - GET  /api/health
 *   - GET  /api/catalog/filters
 *   - POST /api/recommend/natural
 *   - POST /api/recommend
 */

document.addEventListener('DOMContentLoaded', () => {
  // --------------------------------------------------------------------------
  // Application State
  // --------------------------------------------------------------------------
  const State = {
    activeTab: 'natural', // 'natural' | 'structured'
    filters: null,
    currentRecommendations: [],
    isLoading: false,
  };

  // --------------------------------------------------------------------------
  // DOM Elements
  // --------------------------------------------------------------------------
  const Elements = {
    // Header & Status
    aiStatusPill: document.getElementById('aiStatusPill'),
    aiStatusText: document.getElementById('aiStatusText'),

    // Tabs
    tabNatural: document.getElementById('tabNatural'),
    tabStructured: document.getElementById('tabStructured'),
    panelNatural: document.getElementById('panelNatural'),
    panelStructured: document.getElementById('panelStructured'),

    // Natural Form
    naturalForm: document.getElementById('naturalForm'),
    naturalQueryInput: document.getElementById('naturalQueryInput'),
    naturalTopN: document.getElementById('naturalTopN'),
    btnDiscoverNatural: document.getElementById('btnDiscoverNatural'),
    promptChips: document.querySelectorAll('.chip-btn'),

    // Structured Form
    structuredForm: document.getElementById('structuredForm'),
    filterContentType: document.getElementById('filterContentType'),
    filterLanguage: document.getElementById('filterLanguage'),
    filterDuration: document.getElementById('filterDuration'),
    structuredTopN: document.getElementById('structuredTopN'),
    genresContainer: document.getElementById('genresContainer'),
    moodsContainer: document.getElementById('moodsContainer'),
    btnResetFilters: document.getElementById('btnResetFilters'),
    btnDiscoverStructured: document.getElementById('btnDiscoverStructured'),

    // Alert Banner
    alertBanner: document.getElementById('alertBanner'),
    alertMessage: document.getElementById('alertMessage'),
    alertClose: document.getElementById('alertClose'),

    // Extraction Audit Section
    extractionAuditSection: document.getElementById('extractionAuditSection'),
    auditModeBadge: document.getElementById('auditModeBadge'),
    auditModeText: document.getElementById('auditModeText'),
    auditQueryEcho: document.getElementById('auditQueryEcho'),
    auditEntitiesContainer: document.getElementById('auditEntitiesContainer'),
    auditFallbackNotice: document.getElementById('auditFallbackNotice'),
    auditFallbackReasonText: document.getElementById('auditFallbackReasonText'),

    // Results Section
    resultsHeading: document.getElementById('resultsHeading'),
    resultsCountBadge: document.getElementById('resultsCountBadge'),
    initialState: document.getElementById('initialState'),
    loadingState: document.getElementById('loadingState'),
    noResultsState: document.getElementById('noResultsState'),
    recommendationsGrid: document.getElementById('recommendationsGrid'),

    // Modal
    scoreModal: document.getElementById('scoreModal'),
    modalTitle: document.getElementById('modalTitle'),
    modalTypeBadge: document.getElementById('modalTypeBadge'),
    modalTotalScore: document.getElementById('modalTotalScore'),
    modalMatchSummary: document.getElementById('modalMatchSummary'),
    modalBreakdownList: document.getElementById('modalBreakdownList'),
    modalMatchedReasons: document.getElementById('modalMatchedReasons'),
    modalCloseBtn: document.getElementById('modalCloseBtn'),
    modalDismissBtn: document.getElementById('modalDismissBtn'),
  };

  // --------------------------------------------------------------------------
  // Initialization
  // --------------------------------------------------------------------------
  async function init() {
    setupEventListeners();
    await checkSystemHealth();
    await loadCatalogFilters();
  }

  // --------------------------------------------------------------------------
  // Event Listeners
  // --------------------------------------------------------------------------
  function setupEventListeners() {
    // Tabs
    Elements.tabNatural.addEventListener('click', () => switchTab('natural'));
    Elements.tabStructured.addEventListener('click', () => switchTab('structured'));

    // Natural Form Submit
    Elements.naturalForm.addEventListener('submit', handleNaturalSubmit);

    // Prompt Chips
    Elements.promptChips.forEach(chip => {
      chip.addEventListener('click', () => {
        const query = chip.getAttribute('data-query');
        if (query) {
          Elements.naturalQueryInput.value = query;
          Elements.naturalQueryInput.focus();
          handleNaturalSubmit(new Event('submit'));
        }
      });
    });

    // Structured Form Submit
    Elements.structuredForm.addEventListener('submit', handleStructuredSubmit);

    // Reset Filters
    Elements.btnResetFilters.addEventListener('click', resetStructuredFilters);

    // Alert Dismiss
    Elements.alertClose.addEventListener('click', hideAlert);

    // Modal Close
    Elements.modalCloseBtn.addEventListener('click', closeModal);
    Elements.modalDismissBtn.addEventListener('click', closeModal);
    Elements.scoreModal.addEventListener('click', (e) => {
      if (e.target === Elements.scoreModal) closeModal();
    });

    // Keyboard navigation (Esc to close modal)
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !Elements.scoreModal.hidden) {
        closeModal();
      }
    });
  }

  // --------------------------------------------------------------------------
  // Tab Switching
  // --------------------------------------------------------------------------
  function switchTab(tabName) {
    State.activeTab = tabName;
    if (tabName === 'natural') {
      Elements.tabNatural.classList.add('active');
      Elements.tabNatural.setAttribute('aria-selected', 'true');
      Elements.tabStructured.classList.remove('active');
      Elements.tabStructured.setAttribute('aria-selected', 'false');

      Elements.panelNatural.classList.add('active');
      Elements.panelNatural.hidden = false;
      Elements.panelStructured.classList.remove('active');
      Elements.panelStructured.hidden = true;
    } else {
      Elements.tabStructured.classList.add('active');
      Elements.tabStructured.setAttribute('aria-selected', 'true');
      Elements.tabNatural.classList.remove('active');
      Elements.tabNatural.setAttribute('aria-selected', 'false');

      Elements.panelStructured.classList.add('active');
      Elements.panelStructured.hidden = false;
      Elements.panelNatural.classList.remove('active');
      Elements.panelNatural.hidden = true;
    }
  }

  // --------------------------------------------------------------------------
  // API Calls & Health Check
  // --------------------------------------------------------------------------
  async function checkSystemHealth() {
    try {
      const res = await fetch('/api/health');
      if (!res.ok) throw new Error('Health check failed');
      const data = await res.json();

      if (data.ai_engine_configured) {
        setAiStatus('active', 'Gemini AI Ready');
      } else {
        setAiStatus('fallback', 'Offline Heuristic Mode');
      }
    } catch (err) {
      setAiStatus('fallback', 'Local Heuristic Mode');
    }
  }

  function setAiStatus(type, label) {
    Elements.aiStatusPill.className = `status-pill status-${type}`;
    Elements.aiStatusText.textContent = label;
  }

  async function loadCatalogFilters() {
    try {
      const res = await fetch('/api/catalog/filters');
      if (!res.ok) throw new Error('Could not load filters');
      const data = await res.json();
      if (!data.success) throw new Error('Failed to retrieve catalog filters');

      State.filters = data.filters;
      renderFilterControls(data.filters);
    } catch (err) {
      showAlert('Unable to load catalog filter taxonomies. Operating with defaults.');
    }
  }

  function renderFilterControls(filters) {
    // Populate Languages Dropdown
    if (filters.languages && filters.languages.length > 0) {
      filters.languages.forEach(lang => {
        const opt = document.createElement('option');
        opt.value = lang;
        opt.textContent = lang;
        Elements.filterLanguage.appendChild(opt);
      });
    }

    // Populate Genres Checkboxes
    Elements.genresContainer.innerHTML = '';
    if (filters.genres && filters.genres.length > 0) {
      filters.genres.forEach(genre => {
        const label = document.createElement('label');
        label.className = 'checkbox-chip';
        label.innerHTML = `
          <input type="checkbox" name="genre" value="${escapeHtml(genre)}">
          <span>${escapeHtml(genre)}</span>
        `;
        Elements.genresContainer.appendChild(label);
      });
    }

    // Populate Moods Checkboxes
    Elements.moodsContainer.innerHTML = '';
    if (filters.moods && filters.moods.length > 0) {
      filters.moods.forEach(mood => {
        const label = document.createElement('label');
        label.className = 'checkbox-chip';
        label.innerHTML = `
          <input type="checkbox" name="mood" value="${escapeHtml(mood)}">
          <span>${escapeHtml(mood)}</span>
        `;
        Elements.moodsContainer.appendChild(label);
      });
    }
  }

  function resetStructuredFilters() {
    Elements.structuredForm.reset();
  }

  // --------------------------------------------------------------------------
  // Form Submission Handlers
  // --------------------------------------------------------------------------
  async function handleNaturalSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();
    hideAlert();

    const query = Elements.naturalQueryInput.value.trim();
    if (!query) {
      showAlert('Please enter a description of what you want to watch.');
      Elements.naturalQueryInput.focus();
      return;
    }

    const topN = parseInt(Elements.naturalTopN.value, 10) || 5;

    setLoading(true);
    try {
      const res = await fetch('/api/recommend/natural', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_n: topN }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error((data.error && data.error.message) || 'Error generating recommendations');
      }

      // Render Extraction Summary
      renderExtractionAudit(data);

      // Render Recommendations
      renderRecommendations(data.recommendations);
    } catch (err) {
      showAlert(err.message || 'An unexpected error occurred while searching.');
      showEmptyState();
    } finally {
      setLoading(false);
    }
  }

  async function handleStructuredSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();
    hideAlert();

    // Hide audit card when running structured search
    Elements.extractionAuditSection.hidden = true;

    // Collect selected genres
    const checkedGenres = Array.from(
      Elements.genresContainer.querySelectorAll('input[type="checkbox"]:checked')
    ).map(cb => cb.value);

    // Collect selected moods
    const checkedMoods = Array.from(
      Elements.moodsContainer.querySelectorAll('input[type="checkbox"]:checked')
    ).map(cb => cb.value);

    const payload = {
      content_type: Elements.filterContentType.value !== 'Any' ? Elements.filterContentType.value : null,
      language: Elements.filterLanguage.value !== 'Any' ? Elements.filterLanguage.value : null,
      max_duration_minutes: Elements.filterDuration.value ? parseInt(Elements.filterDuration.value, 10) : null,
      genres: checkedGenres,
      moods: checkedMoods,
      top_n: parseInt(Elements.structuredTopN.value, 10) || 5,
    };

    setLoading(true);
    try {
      const res = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error((data.error && data.error.message) || 'Error generating recommendations');
      }

      renderRecommendations(data.recommendations);
    } catch (err) {
      showAlert(err.message || 'An unexpected error occurred while searching.');
      showEmptyState();
    } finally {
      setLoading(false);
    }
  }

  // --------------------------------------------------------------------------
  // Render Extraction Audit (Explainability of NL parsing)
  // --------------------------------------------------------------------------
  function renderExtractionAudit(data) {
    Elements.extractionAuditSection.hidden = false;
    Elements.auditQueryEcho.textContent = `"${data.query}"`;

    const isGemini = data.extraction_mode === 'gemini';
    Elements.auditModeBadge.className = isGemini ? 'audit-badge badge-gemini' : 'audit-badge badge-fallback';
    Elements.auditModeText.textContent = isGemini ? 'Gemini AI Extracted' : 'Offline Heuristic Extracted';

    if (data.fallback_used && data.fallback_reason) {
      Elements.auditFallbackNotice.hidden = false;
      Elements.auditFallbackReasonText.textContent = data.fallback_reason;
    } else {
      Elements.auditFallbackNotice.hidden = true;
    }

    // Render Entity Pills
    const prefs = data.extracted_preferences || {};
    Elements.auditEntitiesContainer.innerHTML = '';

    const addEntity = (key, val) => {
      if (!val || (Array.isArray(val) && val.length === 0)) return;
      const pill = document.createElement('div');
      pill.className = 'entity-pill';
      pill.innerHTML = `
        <span class="entity-key">${escapeHtml(key)}:</span>
        <span class="entity-val">${escapeHtml(Array.isArray(val) ? val.join(', ') : String(val))}</span>
      `;
      Elements.auditEntitiesContainer.appendChild(pill);
    };

    addEntity('Genres', prefs.genres);
    addEntity('Language', prefs.language);
    addEntity('Type', prefs.content_type);
    addEntity('Moods', prefs.moods);
    addEntity('Max Runtime', prefs.max_duration_minutes ? `≤ ${prefs.max_duration_minutes}m` : null);
    addEntity('Tags', prefs.tags);
  }

  // --------------------------------------------------------------------------
  // Render Recommendations Cards
  // --------------------------------------------------------------------------
  function renderRecommendations(items) {
    State.currentRecommendations = items || [];
    Elements.initialState.hidden = true;

    if (!items || items.length === 0) {
      Elements.noResultsState.hidden = false;
      Elements.recommendationsGrid.hidden = true;
      Elements.resultsCountBadge.hidden = true;
      return;
    }

    Elements.noResultsState.hidden = true;
    Elements.recommendationsGrid.hidden = false;
    Elements.resultsCountBadge.hidden = false;
    Elements.resultsCountBadge.textContent = `${items.length} ${items.length === 1 ? 'title' : 'titles'} found`;

    Elements.recommendationsGrid.innerHTML = '';

    items.forEach((item, index) => {
      const card = createRecommendationCard(item, index);
      Elements.recommendationsGrid.appendChild(card);
    });

    // Smooth scroll down to results
    Elements.resultsHeading.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function createRecommendationCard(item, index) {
    const card = document.createElement('article');
    card.className = 'content-card';
    card.setAttribute('aria-label', `${item.title} (${item.type})`);

    const score = Math.round(item.total_score || 0);
    const scoreClass = score >= 80 ? '' : (score >= 60 ? 'score-mid' : 'score-low');
    const gradient = item.poster_gradient || 'linear-gradient(135deg, #1e1e28 0%, #2e2e3e 100%)';

    card.innerHTML = `
      <div class="card-poster" style="background: ${gradient};">
        <div class="card-poster-top">
          <span class="card-type-badge">${escapeHtml(item.type || 'Title')}</span>
          <span class="card-score-pill ${scoreClass}">${score}% Match</span>
        </div>
        <div class="card-rating-tag">★ ${Number(item.rating || 0).toFixed(1)}</div>
      </div>

      <div class="card-body">
        <div class="card-title-group">
          <h4 class="card-title">${escapeHtml(item.title)}</h4>
          <span class="card-year">${escapeHtml(String(item.release_year || ''))}</span>
        </div>

        <div class="card-meta-line">
          <span>${escapeHtml(item.duration_display || `${item.duration_minutes}m`)}</span>
          <span class="meta-bullet">•</span>
          <span>${escapeHtml(item.language || 'English')}</span>
        </div>

        <p class="card-synopsis">${escapeHtml(item.synopsis || 'No summary available.')}</p>

        <div class="card-tags">
          ${(item.genres || []).map(g => `<span class="tag-genre">${escapeHtml(g)}</span>`).join('')}
          ${(item.moods || []).map(m => `<span class="tag-mood">${escapeHtml(m)}</span>`).join('')}
        </div>
      </div>

      <div class="card-footer">
        <button type="button" class="btn-inspect" data-index="${index}">
          <span>📊 Inspect Score Breakdown</span>
        </button>
      </div>
    `;

    const inspectBtn = card.querySelector('.btn-inspect');
    inspectBtn.addEventListener('click', () => openModal(item));

    return card;
  }

  // --------------------------------------------------------------------------
  // Score Breakdown Modal
  // --------------------------------------------------------------------------
  function openModal(item) {
    Elements.modalTitle.textContent = item.title;
    Elements.modalTypeBadge.textContent = `${item.type} (${item.release_year})`;
    Elements.modalTotalScore.textContent = Number(item.total_score || 0).toFixed(1);

    const breakdown = item.score_breakdown || {};
    const reasons = item.match_reasons || {};

    // Summary line
    const matchedParts = [];
    if (reasons.matched_genres && reasons.matched_genres.length > 0) {
      matchedParts.push(`Genre (${reasons.matched_genres.join(', ')})`);
    }
    if (reasons.matched_moods && reasons.matched_moods.length > 0) {
      matchedParts.push(`Mood (${reasons.matched_moods.join(', ')})`);
    }
    if (reasons.language_matched) matchedParts.push('Language');
    if (reasons.duration_compatible) matchedParts.push('Runtime');

    Elements.modalMatchSummary.textContent = matchedParts.length > 0
      ? `Strong alignment on: ${matchedParts.join(', ')}.`
      : 'Evaluated against multi-factor compatibility criteria.';

    // Populate Factor Breakdown Progress Bars
    const factors = [
      { name: 'Genre Match', score: breakdown.genre_match || 0, max: 35.0 },
      { name: 'Mood & Thematic Tags', score: breakdown.mood_match || 0, max: 25.0 },
      { name: 'Audio Language Match', score: breakdown.language_match || 0, max: 15.0 },
      { name: 'Content Type Alignment', score: breakdown.content_type_match || 0, max: 10.0 },
      { name: 'Duration Compatibility', score: breakdown.duration_match || 0, max: 10.0 },
      { name: 'Quality Rating Boost', score: breakdown.rating_boost || 0, max: 5.0 },
    ];

    Elements.modalBreakdownList.innerHTML = '';
    factors.forEach(f => {
      const pct = Math.min(100, Math.round((f.score / f.max) * 100));
      const fillClass = pct >= 80 ? 'fill-green' : '';
      const itemEl = document.createElement('div');
      itemEl.className = 'factor-item';
      itemEl.innerHTML = `
        <div class="factor-top">
          <span class="factor-name">${escapeHtml(f.name)}</span>
          <span class="factor-score">${Number(f.score).toFixed(1)} / ${f.max.toFixed(1)} pts</span>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill ${fillClass}" style="width: ${pct}%;"></div>
        </div>
      `;
      Elements.modalBreakdownList.appendChild(itemEl);
    });

    // Populate Matched Attribute Chips
    Elements.modalMatchedReasons.innerHTML = '';
    const addReason = (label) => {
      const chip = document.createElement('span');
      chip.className = 'reason-tag';
      chip.textContent = label;
      Elements.modalMatchedReasons.appendChild(chip);
    };

    (reasons.matched_genres || []).forEach(g => addReason(`✓ Genre: ${g}`));
    (reasons.matched_moods || []).forEach(m => addReason(`✓ Mood: ${m}`));
    (reasons.matched_tags || []).forEach(t => addReason(`✓ Tag: #${t}`));
    if (reasons.language_matched) addReason(`✓ Language: ${item.language}`);
    if (reasons.type_matched) addReason(`✓ Format: ${item.type}`);
    if (reasons.duration_compatible) addReason(`✓ Runtime: ${item.duration_display || `${item.duration_minutes}m`}`);

    Elements.scoreModal.hidden = false;
    Elements.modalCloseBtn.focus();
  }

  function closeModal() {
    Elements.scoreModal.hidden = true;
  }

  // --------------------------------------------------------------------------
  // UI Helpers (Loading, Alerts, Sanitization)
  // --------------------------------------------------------------------------
  function setLoading(isLoading) {
    State.isLoading = isLoading;
    Elements.loadingState.hidden = !isLoading;
    Elements.btnDiscoverNatural.disabled = isLoading;
    Elements.btnDiscoverStructured.disabled = isLoading;

    if (isLoading) {
      Elements.initialState.hidden = true;
      Elements.noResultsState.hidden = true;
      Elements.recommendationsGrid.hidden = true;
    }
  }

  function showEmptyState() {
    Elements.initialState.hidden = false;
    Elements.loadingState.hidden = true;
    Elements.noResultsState.hidden = true;
    Elements.recommendationsGrid.hidden = true;
    Elements.resultsCountBadge.hidden = true;
  }

  function showAlert(msg) {
    Elements.alertMessage.textContent = msg;
    Elements.alertBanner.hidden = false;
  }

  function hideAlert() {
    Elements.alertBanner.hidden = true;
  }

  function escapeHtml(str) {
    if (!str) return '';
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    };
    return String(str).replace(/[&<>"']/g, (m) => map[m]);
  }

  // Start app
  init();
});
