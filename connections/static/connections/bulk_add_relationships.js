let bulkRowCount = 0;

// Character ids that already have a relationship with the chosen source.
// Updated whenever the source character changes; applied to every target row.
let currentExcluded = new Set();
const rowControls = [];

function getAdjacency() {
  const el = document.getElementById('relationship-adjacency-data');
  if (!el) return {};
  try {
    return JSON.parse(el.textContent || '{}');
  } catch (error) {
    return {};
  }
}

// { characterId: [variantCharacterId, ...] } — variants (same name/alias) of each
// character, used to surface the selected source's variants in the target picker.
let variantAdjacencyCache = null;
function getVariantAdjacency() {
  if (variantAdjacencyCache) return variantAdjacencyCache;
  const el = document.getElementById('bulk-variant-adjacency-data');
  try {
    variantAdjacencyCache = el ? JSON.parse(el.textContent || '{}') : {};
  } catch (error) {
    variantAdjacencyCache = {};
  }
  return variantAdjacencyCache;
}

// { characterId: "alias1 alias2 ..." } — aliases per character, so the picker can
// match a search query against a character's aliases (like the public graph search).
let characterAliasesCache = null;
function getCharacterAliases() {
  if (characterAliasesCache) return characterAliasesCache;
  const el = document.getElementById('bulk-character-aliases-data');
  try {
    characterAliasesCache = el ? JSON.parse(el.textContent || '{}') : {};
  } catch (error) {
    characterAliasesCache = {};
  }
  return characterAliasesCache;
}

// { movieTitle: [characterId, ...] } — cast of each movie, so variants already in
// the filtered movie aren't duplicated in the Variants section.
let movieMembersCache = null;
const movieMemberIdSets = {};
function getMovieMemberIds(movieTitle) {
  if (!(movieTitle in movieMemberIdSets)) {
    let map = {};
    const el = document.getElementById('bulk-movie-members-data');
    if (movieMembersCache) {
      map = movieMembersCache;
    } else {
      try { movieMembersCache = el ? JSON.parse(el.textContent || '{}') : {}; }
      catch (error) { movieMembersCache = {}; }
      map = movieMembersCache;
    }
    movieMemberIdSets[movieTitle] = new Set((map[movieTitle] || []).map(String));
  }
  return movieMemberIdSets[movieTitle];
}

// The variants of the currently selected source character (or null if none).
function getSourceVariantIds() {
  const sourceSelect = document.getElementById('id_source_character');
  const sourceId = sourceSelect ? sourceSelect.value : '';
  if (!sourceId) return null;
  return new Set((getVariantAdjacency()[sourceId] || []).map(String));
}

function initSingleSearchSelect(root) {
  const dropdown = root.querySelector('.relationship-character-search-select__dropdown');
  const summary = root.querySelector('.relationship-character-search-select__summary');
  const panel = root.querySelector('.relationship-character-search-select__panel');
  const searchInput = root.querySelector('[data-relationship-character-search-input]');
  const label = root.querySelector('[data-relationship-character-search-label]');
  const nativeSelect = root.querySelector('.relationship-character-search-select__native');
  const optionButtons = Array.from(root.querySelectorAll('[data-relationship-character-search-option]'));
  const groups = Array.from(root.querySelectorAll('[data-relationship-character-search-group]'));

  let excludedValues = new Set();

  const setSelectedLabel = () => {
    if (!nativeSelect || !label) return;
    const selected = nativeSelect.selectedOptions?.[0];
    if (selected && selected.value) {
      label.textContent = selected.textContent;
      label.classList.remove('placeholder');
    } else {
      label.textContent = 'Select a character';
      label.classList.add('placeholder');
    }
  };

  // The currently selected value is never excluded, so a target already chosen
  // before the source changed is kept rather than silently dropped.
  const isExcluded = (value) =>
    excludedValues.has(value) && value !== (nativeSelect ? nativeSelect.value : '');

  const filterOptions = () => {
    if (!searchInput) return;
    const query = searchInput.value.trim().toLowerCase();
    const movieFilterEl = document.getElementById('bulk-movie-filter');
    const movieFilter = movieFilterEl ? movieFilterEl.value : '';
    // The Variants section surfaces the selected source's variants (same
    // name/alias) when a movie filter is active — so the filter doesn't hide
    // them — excluding any that are already part of the filtered movie's cast.
    const sourceVariantIds = movieFilter ? getSourceVariantIds() : null;
    const movieMemberIds = movieFilter ? getMovieMemberIds(movieFilter) : null;
    const aliasMap = getCharacterAliases();
    groups.forEach((group) => {
      const isVariantsGroup = group.hasAttribute('data-variants-group');
      const rawGroupLabel = group.dataset.groupLabel || '';
      const passesMovieFilter = isVariantsGroup
        ? Boolean(movieFilter && sourceVariantIds)
        : (!movieFilter || rawGroupLabel === movieFilter);
      const groupLabel = rawGroupLabel.toLowerCase();
      const movieMatches = groupLabel.includes(query);
      let hasVisibleOptions = false;
      group.querySelectorAll('[data-relationship-character-search-option]').forEach((option) => {
        const optionValue = option.dataset.value || '';
        const optionLabel = (option.dataset.label || option.textContent || '').toLowerCase();
        const optionAliases = (aliasMap[optionValue] || '').toLowerCase();
        const matchesSearch = movieMatches || optionLabel.includes(query) || optionAliases.includes(query);
        let isVisible = passesMovieFilter && matchesSearch && !isExcluded(optionValue);
        if (isVariantsGroup) {
          isVisible = isVisible
            && Boolean(sourceVariantIds) && sourceVariantIds.has(optionValue)
            && !(movieMemberIds && movieMemberIds.has(optionValue));
        }
        option.hidden = !isVisible;
        if (isVisible) hasVisibleOptions = true;
      });
      group.hidden = !hasVisibleOptions;
    });
  };

  // Re-filter when the page-level movie filter changes.
  document.addEventListener('bulk-movie-filter-change', filterOptions);

  const applyNativeExclusions = () => {
    if (!nativeSelect) return;
    Array.from(nativeSelect.options).forEach((option) => {
      if (!option.value) return;
      const excluded = isExcluded(option.value);
      option.disabled = excluded;
      option.hidden = excluded;
    });
  };

  const setExcluded = (values) => {
    excludedValues = new Set(Array.from(values || [], String));
    applyNativeExclusions();
    filterOptions();
  };

  optionButtons.forEach((button) => {
    button.addEventListener('click', () => {
      if (nativeSelect) {
        nativeSelect.value = button.dataset.value || '';
        nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (label) {
        label.textContent = button.dataset.label || button.textContent || 'Select a character';
        label.classList.remove('placeholder');
      }
      if (searchInput) searchInput.value = '';
      filterOptions();
      dropdown?.removeAttribute('open');
    });
  });

  const positionPanel = () => {
    if (!summary || !panel) return;
    panel.classList.remove('relationship-character-search-select__panel--up');
    const summaryRect = summary.getBoundingClientRect();
    const panelHeight = panel.offsetHeight;
    const spaceBelow = window.innerHeight - summaryRect.bottom;
    const spaceAbove = summaryRect.top;
    if (spaceBelow < panelHeight && spaceAbove > spaceBelow) {
      panel.classList.add('relationship-character-search-select__panel--up');
    }
  };

  searchInput?.addEventListener('input', filterOptions);
  searchInput?.addEventListener('click', (e) => e.stopPropagation());
  dropdown?.addEventListener('toggle', () => {
    if (dropdown.open) {
      filterOptions();
      positionPanel();
      searchInput?.focus();
    }
  });

  setSelectedLabel();
  filterOptions();

  return { setExcluded };
}

function createRow() {
  const template = document.getElementById('bulk-row-template');
  const idx = bulkRowCount++;
  const html = template.innerHTML.replace(/__INDEX__/g, idx);
  const wrapper = document.createElement('div');
  wrapper.innerHTML = html.trim();
  const row = wrapper.firstElementChild;
  initRow(row);
  return row;
}

function initRow(row) {
  const searchSelectRoot = row.querySelector('[data-relationship-character-search-select]');
  if (searchSelectRoot) {
    const control = initSingleSearchSelect(searchSelectRoot);
    control.row = row;
    control.setExcluded(currentExcluded);
    rowControls.push(control);
  }

  const directionalCheckbox = row.querySelector('.bulk-row-directional');
  const directionWrapper = row.querySelector('.bulk-row-direction-wrapper');
  const removeBtn = row.querySelector('.bulk-row-remove');

  directionalCheckbox?.addEventListener('change', () => {
    directionWrapper.hidden = !directionalCheckbox.checked;
  });

  removeBtn?.addEventListener('click', () => {
    const index = rowControls.findIndex((control) => control.row === row);
    if (index !== -1) rowControls.splice(index, 1);
    row.remove();
    updateRemoveButtons();
  });
}

function updateRemoveButtons() {
  const rows = document.querySelectorAll('#bulk-rows-container [data-row]');
  rows.forEach((row) => {
    const btn = row.querySelector('.bulk-row-remove');
    if (btn) btn.disabled = rows.length <= 1;
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('bulk-rows-container');
  const addBtn = document.getElementById('add-row-btn');

  const initialRows = (() => {
    try {
      const val = parseInt(container?.dataset?.initialRows, 10);
      return Number.isFinite(val) && val > 0 ? val : 15;
    } catch (e) {
      return 15;
    }
  })();

  for (let i = 0; i < initialRows; i++) {
    container.appendChild(createRow());
  }
  updateRemoveButtons();

  // When the source character changes, hide every character it already has a
  // relationship with from all target dropdowns (existing and future rows).
  const adjacency = getAdjacency();
  const sourceSelect = document.getElementById('id_source_character');
  const applyExclusions = () => {
    const value = sourceSelect ? sourceSelect.value : '';
    const related = value && adjacency[value] ? adjacency[value] : [];
    currentExcluded = new Set(related.map(String));
    // Hide the source itself so a character cannot be related to themself.
    if (value) currentExcluded.add(String(value));
    rowControls.forEach((control) => control.setExcluded(currentExcluded));
  };
  sourceSelect?.addEventListener('change', applyExclusions);
  applyExclusions();

  // When the movie filter changes, ask every character picker to re-filter.
  const movieFilter = document.getElementById('bulk-movie-filter');
  movieFilter?.addEventListener('change', () => {
    document.dispatchEvent(new CustomEvent('bulk-movie-filter-change'));
  });

  addBtn?.addEventListener('click', () => {
    const row = createRow();
    container.appendChild(row);
    updateRemoveButtons();
    row.querySelector('[data-relationship-character-search-select] summary')?.focus();
  });
});
