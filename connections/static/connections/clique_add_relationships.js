// Drives the "Bulk Add Relationships by Type" admin page: the Clique/Single-source
// mode toggle, the accordion, per-box directional controls, the page-level movie
// filter (which narrows the source picker and surfaces variants), per-box search
// with a "pick a movie" empty state, the add-all-cast / clear helpers, and the
// already-related red flagging.

const parseJSON = (id) => {
  const el = document.getElementById(id);
  if (!el) return {};
  try {
    return JSON.parse(el.textContent || '{}');
  } catch (error) {
    return {};
  }
};

const initCliqueAdd = () => {
  const variantAdjacency = parseJSON('clique-variant-adjacency-data');
  const movieMembers = parseJSON('clique-movie-members-data');
  const characterAliases = parseJSON('clique-character-aliases-data');
  // { characterId: [relatedId, ...] } — any existing relationship (undirected),
  // used to flag already-related targets in red in single-source mode.
  const relationshipAdjacency = parseJSON('clique-relationship-adjacency-data');

  // Shared id the relationship-character search-select JS already filters against,
  // so naming our movie filter this lets the source picker narrow to the cast too.
  const movieFilter = document.getElementById('bulk-movie-filter');
  const sourceSelect = document.getElementById('id_source_character');
  const modeRadios = Array.from(document.querySelectorAll('input[name="mode"]'));

  const currentMovie = () => (movieFilter ? movieFilter.value : '');
  const isSourceMode = () => {
    const selected = modeRadios.find((radio) => radio.checked);
    return Boolean(selected && selected.value === 'source');
  };
  const currentSource = () => (isSourceMode() && sourceSelect ? sourceSelect.value : '');

  const castIdSet = (movieTitle) => new Set((movieMembers[movieTitle] || []).map(String));

  // Off-movie variants to surface in the Variants group, mode-aware:
  //  - source mode + source chosen → that source's variants (minus the movie cast)
  //  - clique mode               → the whole cast's variants (minus the cast)
  // Only meaningful when a movie is selected (otherwise the full list is shown).
  const variantIdSet = (movieTitle) => {
    if (!movieTitle) return new Set();
    const cast = castIdSet(movieTitle);
    const out = new Set();
    const add = (id) => {
      (variantAdjacency[id] || []).forEach((vId) => {
        const key = String(vId);
        if (!cast.has(key)) out.add(key);
      });
    };
    if (isSourceMode()) {
      const src = currentSource();
      if (!src) return new Set();
      add(src);
    } else {
      (movieMembers[movieTitle] || []).forEach((castId) => add(castId));
    }
    return out;
  };

  // ── One controller per relationship-type box ──
  const boxes = Array.from(document.querySelectorAll('[data-clique-character-select]'));

  const boxControllers = boxes.map((root) => {
    const searchInput = root.querySelector('[data-clique-search]');
    const grid = root.querySelector('[data-clique-grid]');
    const emptyEl = root.querySelector('[data-clique-empty]');
    const groups = Array.from(root.querySelectorAll('[data-clique-group]'));
    const options = Array.from(root.querySelectorAll('[data-clique-option]'));
    const addCastBtn = root.querySelector('[data-clique-add-cast]');
    const clearBtn = root.querySelector('[data-clique-clear]');
    const countEl = root.querySelector('[data-clique-count]');
    const badge = root.closest('[data-clique-type]')?.querySelector('[data-clique-count-badge]');

    const checkboxOf = (option) => option.querySelector('input[type="checkbox"]');

    const updateCount = () => {
      const checked = new Set();
      options.forEach((option) => {
        const box = checkboxOf(option);
        if (box && box.checked) checked.add(option.dataset.value || '');
      });
      if (countEl) countEl.textContent = `${checked.size} selected`;
      if (badge) {
        badge.textContent = String(checked.size);
        badge.classList.toggle('has-selection', checked.size > 0);
      }
    };

    const filter = () => {
      const query = (searchInput ? searchInput.value : '').trim().toLowerCase();
      const movie = currentMovie();
      const hasQuery = query.length > 0;

      // Empty state: nothing to scope by yet.
      const showPrompt = !movie && !hasQuery;
      if (emptyEl) emptyEl.hidden = !showPrompt;
      if (grid) grid.hidden = showPrompt;
      if (showPrompt) return;

      const variants = variantIdSet(movie);
      // In source mode the source can't be related to itself — hide it everywhere.
      const sourceId = currentSource();

      groups.forEach((group) => {
        const isVariants = group.hasAttribute('data-variants-group');
        const groupLabel = group.dataset.groupLabel || '';
        const groupLabelLower = groupLabel.toLowerCase();
        // Variants group only when a movie is set; normal groups restricted to the
        // chosen movie (or unrestricted when searching with no movie).
        const passesMovie = isVariants ? Boolean(movie) : (!movie || groupLabel === movie);

        let visibleCount = 0;
        group.querySelectorAll('[data-clique-option]').forEach((option) => {
          const value = option.dataset.value || '';
          const label = (option.dataset.label || '').toLowerCase();
          const aliases = (characterAliases[value] || '').toLowerCase();
          const matchesSearch =
            !hasQuery || groupLabelLower.includes(query) || label.includes(query) || aliases.includes(query);
          let visible = passesMovie && matchesSearch;
          if (isVariants) {
            visible = visible && variants.has(value);
          }
          if (sourceId && value === sourceId) visible = false;
          option.hidden = !visible;
          if (visible) visibleCount += 1;
        });
        group.hidden = visibleCount === 0;
      });
    };

    const refreshButtons = () => {
      if (addCastBtn) addCastBtn.hidden = !currentMovie();
    };

    addCastBtn?.addEventListener('click', () => {
      const movie = currentMovie();
      if (!movie) return;
      const cast = castIdSet(movie);
      options.forEach((option) => {
        if (cast.has(option.dataset.value || '')) {
          const box = checkboxOf(option);
          if (box) box.checked = true;
        }
      });
      updateCount();
    });

    clearBtn?.addEventListener('click', () => {
      options.forEach((option) => {
        const box = checkboxOf(option);
        if (box) box.checked = false;
      });
      updateCount();
    });

    searchInput?.addEventListener('input', filter);
    root.addEventListener('change', (event) => {
      if (event.target && event.target.matches('input[type="checkbox"]')) updateCount();
    });

    filter();
    refreshButtons();
    updateCount();

    return { filter, refreshButtons };
  });

  const refreshAllBoxes = () => {
    boxControllers.forEach((box) => {
      box.filter();
      box.refreshButtons();
    });
  };

  // ── Already-related red flagging (single-source mode) ──
  const allOptions = Array.from(document.querySelectorAll('[data-clique-option]'));
  const applyRelatedFlags = () => {
    const sourceId = currentSource();
    const related = sourceId ? new Set((relationshipAdjacency[sourceId] || []).map(String)) : null;
    allOptions.forEach((option) => {
      const value = option.dataset.value || '';
      const flag = Boolean(related) && related.has(value) && value !== sourceId;
      option.classList.toggle('is-related', flag);
      if (flag) {
        option.title = 'Already has a relationship with the selected source';
      } else {
        option.removeAttribute('title');
      }
    });
  };

  // ── Movie filter change → re-filter boxes + source picker ──
  movieFilter?.addEventListener('change', () => {
    refreshAllBoxes();
    // Let the shared relationship-character search-select re-filter the source picker.
    document.dispatchEvent(new CustomEvent('bulk-movie-filter-change'));
  });

  // ── Mode toggle: show source control + directional controls only in source mode ──
  const sourceControl = document.getElementById('clique-source-control');
  const directionalWraps = Array.from(document.querySelectorAll('[data-clique-directional-wrap]'));
  const applyMode = () => {
    const isSource = isSourceMode();
    if (sourceControl) sourceControl.hidden = !isSource;
    directionalWraps.forEach((wrap) => { wrap.hidden = !isSource; });
    refreshAllBoxes();      // variants depend on mode
    applyRelatedFlags();
  };
  modeRadios.forEach((radio) => radio.addEventListener('change', applyMode));

  // Source change → variants (source mode) + red flags both depend on it.
  sourceSelect?.addEventListener('change', () => {
    refreshAllBoxes();
    applyRelatedFlags();
  });

  applyMode();

  // ── Accordion open/close ──
  document.querySelectorAll('[data-clique-toggle]').forEach((btn) => {
    const body = btn.closest('[data-clique-type]')?.querySelector('[data-clique-body]');
    if (!body) return;
    btn.addEventListener('click', () => {
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!open));
      body.hidden = open;
    });
  });

  // ── Per-box directional checkbox → show/hide its direction select ──
  document.querySelectorAll('[data-clique-type]').forEach((fieldset) => {
    const directional = fieldset.querySelector('[data-clique-directional]');
    const directionSelect = fieldset.querySelector('[data-clique-direction-select]');
    if (!directional || !directionSelect) return;
    const sync = () => { directionSelect.hidden = !directional.checked; };
    directional.addEventListener('change', sync);
    sync();
  });
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCliqueAdd, { once: true });
} else {
  initCliqueAdd();
}
