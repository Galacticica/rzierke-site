// Bulk Delete Relationships page: select-all, live count on the submit button, and
// a confirm() guard before the (irreversible) delete.

const initBulkDelete = () => {
  const form = document.getElementById('delete-form');
  if (!form) return;

  const selectAll = document.getElementById('delete-select-all');
  const checkboxes = Array.from(form.querySelectorAll('.delete-checkbox'));
  const submit = document.getElementById('delete-submit');
  const characterName = submit ? submit.dataset.characterName || 'this character' : 'this character';

  const checkedCount = () => checkboxes.filter((cb) => cb.checked).length;

  const refresh = () => {
    const count = checkedCount();
    if (submit) {
      submit.value = `Delete selected (${count})`;
      submit.disabled = count === 0;
    }
    if (selectAll) {
      selectAll.checked = count > 0 && count === checkboxes.length;
      selectAll.indeterminate = count > 0 && count < checkboxes.length;
    }
  };

  selectAll?.addEventListener('change', () => {
    checkboxes.forEach((cb) => { cb.checked = selectAll.checked; });
    refresh();
  });

  checkboxes.forEach((cb) => cb.addEventListener('change', refresh));

  form.addEventListener('submit', (event) => {
    const count = checkedCount();
    if (count === 0) {
      event.preventDefault();
      return;
    }
    const message = `Delete ${count} relationship(s) for ${characterName}? This cannot be undone.`;
    if (!window.confirm(message)) {
      event.preventDefault();
    }
  });

  refresh();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initBulkDelete, { once: true });
} else {
  initBulkDelete();
}
