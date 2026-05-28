document.querySelectorAll('[data-movie-search-select]').forEach((root) => {
  const dropdown = root.querySelector('.movie-search-select__dropdown');
  const searchInput = root.querySelector('[data-movie-search-input]');
  const label = root.querySelector('[data-movie-search-label]');
  const nativeSelect = root.querySelector('.movie-search-select__native');
  const optionButtons = Array.from(root.querySelectorAll('[data-movie-search-option]'));
  const groups = Array.from(root.querySelectorAll('[data-movie-search-group]'));

  const setSelectedLabel = () => {
    if (!nativeSelect || !label) return;
    const selectedOption = nativeSelect.selectedOptions?.[0];
    if (selectedOption) {
      label.textContent = selectedOption.textContent;
      label.classList.remove('placeholder');
    } else {
      label.textContent = 'Select a movie';
      label.classList.add('placeholder');
    }
  };

  const filterOptions = () => {
    if (!searchInput) return;
    const query = searchInput.value.trim().toLowerCase();
    groups.forEach((group) => {
      let hasVisibleOptions = false;
      group.querySelectorAll('[data-movie-search-option]').forEach((option) => {
        const optionLabel = (option.dataset.label || option.textContent || '').toLowerCase();
        const isVisible = optionLabel.includes(query);
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
        label.textContent = button.dataset.label || button.textContent || 'Select a movie';
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
  dropdown?.addEventListener('toggle', () => {
    if (dropdown.open) {
      filterOptions();
      searchInput?.focus();
    }
  });

  setSelectedLabel();
  filterOptions();
});
