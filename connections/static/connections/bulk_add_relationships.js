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
    groups.forEach((group) => {
      const groupLabel = (group.dataset.groupLabel || '').toLowerCase();
      const movieMatches = groupLabel.includes(query);
      let hasVisibleOptions = false;
      group.querySelectorAll('[data-relationship-character-search-option]').forEach((option) => {
        const optionValue = option.dataset.value || '';
        const optionLabel = (option.dataset.label || option.textContent || '').toLowerCase();
        const matchesSearch = movieMatches || optionLabel.includes(query);
        const isVisible = matchesSearch && !isExcluded(optionValue);
        option.hidden = !isVisible;
        if (isVisible) hasVisibleOptions = true;
      });
      group.hidden = !hasVisibleOptions;
    });
  };

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

  for (let i = 0; i < 3; i++) {
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

  addBtn?.addEventListener('click', () => {
    const row = createRow();
    container.appendChild(row);
    updateRemoveButtons();
    row.querySelector('[data-relationship-character-search-select] summary')?.focus();
  });
});
