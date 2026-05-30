let bulkRowCount = 0;

function initSingleSearchSelect(root) {
  const dropdown = root.querySelector('.relationship-character-search-select__dropdown');
  const summary = root.querySelector('.relationship-character-search-select__summary');
  const panel = root.querySelector('.relationship-character-search-select__panel');
  const searchInput = root.querySelector('[data-relationship-character-search-input]');
  const label = root.querySelector('[data-relationship-character-search-label]');
  const nativeSelect = root.querySelector('.relationship-character-search-select__native');
  const optionButtons = Array.from(root.querySelectorAll('[data-relationship-character-search-option]'));
  const groups = Array.from(root.querySelectorAll('[data-relationship-character-search-group]'));

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

  const filterOptions = () => {
    if (!searchInput) return;
    const query = searchInput.value.trim().toLowerCase();
    groups.forEach((group) => {
      const groupLabel = (group.dataset.groupLabel || '').toLowerCase();
      const movieMatches = groupLabel.includes(query);
      let hasVisibleOptions = false;
      group.querySelectorAll('[data-relationship-character-search-option]').forEach((option) => {
        const optionLabel = (option.dataset.label || option.textContent || '').toLowerCase();
        const isVisible = movieMatches || optionLabel.includes(query);
        option.hidden = !isVisible;
        if (isVisible) hasVisibleOptions = true;
      });
      group.hidden = !hasVisibleOptions;
    });
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
  if (searchSelectRoot) initSingleSearchSelect(searchSelectRoot);

  const directionalCheckbox = row.querySelector('.bulk-row-directional');
  const directionWrapper = row.querySelector('.bulk-row-direction-wrapper');
  const removeBtn = row.querySelector('.bulk-row-remove');

  directionalCheckbox?.addEventListener('change', () => {
    directionWrapper.hidden = !directionalCheckbox.checked;
  });

  removeBtn?.addEventListener('click', () => {
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

  addBtn?.addEventListener('click', () => {
    const row = createRow();
    container.appendChild(row);
    updateRemoveButtons();
    row.querySelector('[data-relationship-character-search-select] summary')?.focus();
  });
});
