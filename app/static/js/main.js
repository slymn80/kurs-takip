const toggleSidebar = () => {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (!sidebar) return;
  sidebar.classList.toggle('-translate-x-full');
  overlay?.classList.toggle('hidden');
};

const setupToggles = () => {
  document.querySelectorAll('[data-toggle-sidebar]').forEach((btn) => {
    btn.addEventListener('click', toggleSidebar);
  });
  document.querySelectorAll('[data-close-sidebar]').forEach((btn) => {
    btn.addEventListener('click', toggleSidebar);
  });

  document.querySelectorAll('[data-modal-target]').forEach((btn) => {
    const targetId = btn.getAttribute('data-modal-target');
    const modal = document.getElementById(targetId);
    if (!modal) return;
    btn.addEventListener('click', () => modal.classList.remove('hidden'));
  });

  document.querySelectorAll('[data-modal-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal');
      modal?.classList.add('hidden');
    });
  });
};

const setupToast = () => {
  const toast = document.querySelector('[data-toast]');
  if (!toast) return;
  setTimeout(() => toast.classList.add('hidden'), 3200);
};

const setupLocalTimes = () => {
  const formatter = new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
  document.querySelectorAll('[data-local-time]').forEach((el) => {
    const value = el.getAttribute('data-local-time');
    if (!value) return;
    const date = new Date(value);
    if (isNaN(date.getTime())) return;
    el.textContent = formatter.format(date);
  });
};

document.addEventListener('DOMContentLoaded', () => {
  setupToggles();
  setupToast();
  setupLocalTimes();
});
