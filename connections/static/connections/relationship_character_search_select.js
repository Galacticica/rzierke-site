const initRelationshipCharacterSearchSelect = () => {
  const controls = [];

  document.querySelectorAll('[data-relationship-character-search-select]').forEach((root) => {
    const dropdown = root.querySelector('.relationship-character-search-select__dropdown');
    const summary = root.querySelector('.relationship-character-search-select__summary');
    const panel = root.querySelector('.relationship-character-search-select__panel');
    const searchInput = root.querySelector('[data-relationship-character-search-input]');
    const label = root.querySelector('[data-relationship-character-search-label]');
    const nativeSelect = root.querySelector('.relationship-character-search-select__native');
    const optionButtons = Array.from(root.querySelectorAll('[data-relationship-character-search-option]'));
    const groups = Array.from(root.querySelectorAll('[data-relationship-character-search-group]'));

    // Characters that already have a relationship with the chosen source: kept
    // selectable but flagged in red.
    let relatedValues = new Set();
    // Characters that must not be selectable at all (e.g. the source itself, so a
    // character cannot be related to themself): hidden from the list.
    let excludedValues = new Set();

    const currentValue = () => (nativeSelect ? nativeSelect.value : '');
    // The currently selected value is never excluded, so editing keeps its target.
    const isExcluded = (value) => excludedValues.has(value) && value !== currentValue();

    const setSelectedLabel = () => {
      if (!nativeSelect || !label) return;
      const selectedOption = nativeSelect.selectedOptions?.[0];
      if (selectedOption && selectedOption.value) {
        label.textContent = selectedOption.textContent;
        label.classList.remove('placeholder');
      } else {
        label.textContent = 'Select a character';
        label.classList.add('placeholder');
      }
    };

    const filterOptions = () => {
      if (!searchInput) return;
      const query = searchInput.value.trim().toLowerCase();
      const movieFilterEl = document.getElementById('bulk-movie-filter');
      const movieFilter = movieFilterEl ? movieFilterEl.value : '';
      groups.forEach((group) => {
        const rawGroupLabel = group.dataset.groupLabel || '';
        const passesMovieFilter = !movieFilter || rawGroupLabel === movieFilter;
        const groupLabel = rawGroupLabel.toLowerCase();
        const movieMatches = groupLabel.includes(query);
        let hasVisibleOptions = false;
        group.querySelectorAll('[data-relationship-character-search-option]').forEach((option) => {
          const optionValue = option.dataset.value || '';
          const optionLabel = (option.dataset.label || option.textContent || '').toLowerCase();
          const matchesSearch = movieMatches || optionLabel.includes(query);
          const isVisible = passesMovieFilter && matchesSearch && !isExcluded(optionValue);
          option.hidden = !isVisible;
          if (isVisible) hasVisibleOptions = true;
        });
        group.hidden = !hasVisibleOptions;
      });
    };

    // Re-filter when the bulk page's movie filter changes (no-op elsewhere).
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

    // Flag (in red) every option whose character already has a relationship with
    // the selected source. The currently selected value is never flagged so that
    // editing an existing relationship does not paint its own target red.
    const applyRelatedStyling = () => {
      optionButtons.forEach((button) => {
        const value = button.dataset.value || '';
        const isRelated = relatedValues.has(value) && value !== currentValue() && !isExcluded(value);
        button.classList.toggle('is-related', isRelated);
        if (isRelated) {
          button.title = 'Already has a relationship with the selected character';
        } else {
          button.removeAttribute('title');
        }
      });
    };

    const refresh = () => {
      applyNativeExclusions();
      filterOptions();
      applyRelatedStyling();
    };

    const setRelated = (values) => {
      relatedValues = new Set(Array.from(values || [], String));
      applyRelatedStyling();
    };

    const setExcluded = (values) => {
      excludedValues = new Set(Array.from(values || [], String));
      refresh();
    };

    optionButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const value = button.dataset.value || '';
        if (nativeSelect) {
          nativeSelect.value = value;
          nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (label) {
          label.textContent = button.dataset.label || button.textContent || 'Select a character';
          label.classList.remove('placeholder');
        }
        if (searchInput) {
          searchInput.value = '';
        }
        refresh();
        dropdown?.removeAttribute('open');
      });
    });

    searchInput?.addEventListener('input', filterOptions);
    searchInput?.addEventListener('click', (event) => event.stopPropagation());
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

    dropdown?.addEventListener('toggle', () => {
      if (dropdown.open) {
        filterOptions();
        positionPanel();
        searchInput?.focus();
      }
    });

    setSelectedLabel();
    refresh();

    controls.push({ nativeSelect, setRelated, setExcluded });
  });

  // On the relationship admin form: flag every character that already has a
  // relationship with the selected source (character1) in red, and hide the
  // source itself so a character cannot be related to themself.
  const adjacencyEl = document.getElementById('relationship-adjacency-data');
  if (!adjacencyEl) return;

  let adjacency = {};
  try {
    adjacency = JSON.parse(adjacencyEl.textContent || '{}');
  } catch (error) {
    adjacency = {};
  }

  const sourceControl = controls.find((control) => control.nativeSelect?.name === 'character1');
  const targetControl = controls.find((control) => control.nativeSelect?.name === 'character2');
  if (!sourceControl || !targetControl) return;

  const applyFromSource = () => {
    const value = sourceControl.nativeSelect.value;
    targetControl.setRelated(value ? adjacency[value] || [] : []);
    targetControl.setExcluded(value ? [value] : []);
  };

  sourceControl.nativeSelect.addEventListener('change', applyFromSource);
  applyFromSource();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initRelationshipCharacterSearchSelect, { once: true });
} else {
  initRelationshipCharacterSearchSelect();
}
