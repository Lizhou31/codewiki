/* Optional enhancements. Navigation, prose, and source disclosures are native HTML. */
(() => {
  const panel = document.querySelector('.nav-panel');
  if (panel && window.matchMedia('(max-width: 760px)').matches) panel.open = false;

  document.querySelectorAll('.mobile-outline a').forEach(link => link.addEventListener('click', () => {
    link.closest('details').open = false;
  }));

  const input = document.querySelector('#page-search');
  const links = [...document.querySelectorAll('.project-nav a')];
  if (input) {
    input.closest('.page-search').hidden = false;
    input.addEventListener('input', () => {
      const words = input.value.trim().toLocaleLowerCase().split(/\s+/);
      links.forEach(link => { link.hidden = !words.every(word => link.textContent.toLocaleLowerCase().includes(word)); });
      document.querySelector('.search-empty').hidden = links.some(link => !link.hidden);
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
