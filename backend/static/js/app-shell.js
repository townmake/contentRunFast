(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    var sidebar = document.getElementById('sidebar');
    var main = document.querySelector('.main-content');
    var collapseBtn = document.getElementById('sidebarCollapse');
    var toggleBtn = document.getElementById('sidebarToggle');
    if (!sidebar || !main) return;

    function applyCollapsed(collapsed) {
      sidebar.classList.toggle('collapsed', collapsed);
      main.classList.toggle('expanded', collapsed);
      if (toggleBtn) toggleBtn.classList.toggle('is-visible', collapsed);
      if (collapseBtn) collapseBtn.textContent = collapsed ? '›' : '‹';
      try { localStorage.setItem('runfast_sidebar_collapsed', collapsed ? 'true' : 'false'); } catch (e) {}
    }

    var saved = false;
    try { saved = localStorage.getItem('runfast_sidebar_collapsed') === 'true'; } catch (e) {}
    if (window.innerWidth <= 768) saved = true;
    applyCollapsed(saved);

    if (collapseBtn) {
      collapseBtn.addEventListener('click', function () {
        applyCollapsed(!sidebar.classList.contains('collapsed'));
      });
    }
    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        applyCollapsed(false);
      });
    }

    document.querySelectorAll('.sidebar-group-toggle').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var group = btn.closest('.sidebar-nav-group');
        if (group) group.classList.toggle('collapsed');
      });
    });
  });
})();
