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
  const pad = (value) => String(value).padStart(2, '0');
  const format = (date) => {
    const day = pad(date.getDate());
    const month = pad(date.getMonth() + 1);
    const year = date.getFullYear();
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    return `${day}.${month}.${year} ${hours}:${minutes}`;
  };
  document.querySelectorAll('[data-local-time]').forEach((el) => {
    const value = el.getAttribute('data-local-time');
    if (!value) return;
    const date = new Date(value);
    if (isNaN(date.getTime())) return;
    el.textContent = format(date);
  });
};

const formatClock = (date) => {
  const pad = (value) => String(value).padStart(2, '0');
  const day = pad(date.getDate());
  const month = pad(date.getMonth() + 1);
  const year = date.getFullYear();
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  const seconds = pad(date.getSeconds());
  return `${day}.${month}.${year} ${hours}:${minutes}:${seconds}`;
};

const setupClock = () => {
  const clock = document.getElementById('app-clock');
  if (!clock) return;
  const tick = () => {
    clock.textContent = formatClock(new Date());
  };
  tick();
  setInterval(tick, 1000);
};

document.addEventListener('DOMContentLoaded', () => {
  setupToggles();
  setupToast();
  setupLocalTimes();
  setupClock();
  const attendanceLinks = document.querySelectorAll('.js-attendance-link');
  if (attendanceLinks.length) {
    const toggleAttendance = () => {
      const now = new Date();
      attendanceLinks.forEach((link) => {
        const dateStr = link.getAttribute('data-session-date');
        const timeStr = link.getAttribute('data-session-start');
        if (!dateStr || !timeStr || timeStr === 'None' || timeStr === 'null') {
          link.classList.add('opacity-50', 'pointer-events-none');
          link.setAttribute('aria-disabled', 'true');
          return;
        }
        const target = new Date(`${dateStr}T${timeStr}`);
        if (isNaN(target.getTime())) {
          link.classList.add('opacity-50', 'pointer-events-none');
          link.setAttribute('aria-disabled', 'true');
          return;
        }
        if (now >= target) {
          link.classList.remove('opacity-50', 'pointer-events-none');
          link.removeAttribute('aria-disabled');
        } else {
          link.classList.add('opacity-50', 'pointer-events-none');
          link.setAttribute('aria-disabled', 'true');
        }
      });
    };
    toggleAttendance();
    setInterval(toggleAttendance, 30000);
  }
});
