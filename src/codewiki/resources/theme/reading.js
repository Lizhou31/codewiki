/* Optional enhancements. Navigation, prose, and source disclosures are native HTML. */
(() => {
  const panel = document.querySelector('.nav-panel');
  if (panel && window.matchMedia('(max-width: 760px)').matches) panel.open = false;

  document.querySelectorAll('.mobile-outline a').forEach(link => link.addEventListener('click', () => {
    link.closest('details').open = false;
  }));

  const input = document.querySelector('#page-search');
  const links = [...document.querySelectorAll('.project-nav a')];
  const branches = [...document.querySelectorAll('.nav-branch')];
  const items = [...document.querySelectorAll('.nav-item')];
  const actions = document.querySelector('.nav-actions');
  const buttons = [...document.querySelectorAll('[data-nav-expand]')];
  let beforeSearch;
  if (actions && branches.length) {
    actions.hidden = false;
    buttons.forEach(button => button.addEventListener('click', () => {
      branches.forEach(branch => { branch.open = button.dataset.navExpand === 'true'; });
    }));
  }
  if (input) {
    input.closest('.page-search').hidden = false;
    input.addEventListener('input', () => {
      const query = input.value.trim().toLocaleLowerCase();
      const words = query.split(/\s+/);
      const matches = new Set(links.filter(link => words.every(word => link.textContent.toLocaleLowerCase().includes(word))));
      if (query && !beforeSearch) beforeSearch = new Map(branches.map(branch => [branch, branch.open]));
      if (items.length) {
        // Keep ancestors of matches visible so results retain their page hierarchy.
        items.forEach(item => { item.hidden = ![...item.querySelectorAll('a')].some(link => matches.has(link)); });
        branches.forEach(branch => {
          if (query) branch.open = [...branch.querySelectorAll('ul a')].some(link => matches.has(link));
          else if (beforeSearch) branch.open = beforeSearch.get(branch);
        });
      } else {
        // Project template overrides may still supply a flat navigation list.
        links.forEach(link => { link.hidden = !matches.has(link); });
      }
      if (!query) beforeSearch = undefined;
      buttons.forEach(button => { button.disabled = Boolean(query); });
      document.querySelector('.search-empty').hidden = matches.size > 0;
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') { input.value = ''; input.dispatchEvent(new Event('input')); }
    });
  }

  const tocLinks = [...document.querySelectorAll('.page-toc nav a')];
  const sections = tocLinks.map(link => document.getElementById(decodeURIComponent(link.hash.slice(1)))).filter(Boolean);
  let queued = false;
  function updateToc() {
    const active = sections.filter(section => section.getBoundingClientRect().top <= 160).at(-1) || sections[0];
    tocLinks.forEach(link => {
      if (active && link.hash === '#' + active.id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
    queued = false;
  }
  window.addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(updateToc); } }, {passive: true});
  updateToc();

  // Fetch highlighting only when source or a Markdown code block is visible.
  let highlighting;
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src; script.onload = resolve; script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  async function highlightVisible() {
    const visible = [...document.querySelectorAll('pre code:not([data-highlighted])')].filter(code => code.getClientRects().length);
    if (!visible.length) return;
    try {
      highlighting ||= loadScript('vendor/highlight.min.js').then(() => loadScript('vendor/hljs-extra.js'));
      await highlighting;
      visible.forEach(code => { if (!code.dataset.highlighted) window.hljs.highlightElement(code); });
    } catch (_) { /* Plain code remains readable when enhancement assets are unavailable. */ }
  }
  document.querySelectorAll('details').forEach(details => details.addEventListener('toggle', highlightVisible));
  highlightVisible();
})();
