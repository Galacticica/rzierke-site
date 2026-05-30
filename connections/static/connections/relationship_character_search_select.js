const initRelationshipCharacterSearchSelect = () => {
  document.querySelectorAll('[data-relationship-character-search-select]').forEach((root) => {
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
        filterOptions();
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
    filterOptions();
  });
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initRelationshipCharacterSearchSelect, { once: true });
} else {
  initRelationshipCharacterSearchSelect();
}