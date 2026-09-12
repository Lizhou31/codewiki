/* Diagram navigation uses validated document/section IDs emitted by the build. */
(async () => {
  const data = document.getElementById('diagram-targets');
  if (!data || !window.mermaid) return;
  const targets = JSON.parse(data.textContent);
  const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  mermaid.initialize({
    startOnLoad: false, securityLevel: 'loose', theme: 'base',
    flowchart: {curve: 'basis', padding: 18, useMaxWidth: false, nodeSpacing: 28, rankSpacing: 42},
    themeVariables: {
      primaryColor: dark ? '#202c46' : '#edf3ff',
      primaryBorderColor: dark ? '#829bd5' : '#7691c9',
      primaryTextColor: dark ? '#e2e7ef' : '#202b3b',
      lineColor: dark ? '#8895ac' : '#8190a9',
      clusterBkg: dark ? '#1b2028' : '#f7f9fc', clusterBorder: dark ? '#414b5d' : '#d9e1ee',
      edgeLabelBackground: dark ? '#1b2028' : '#ffffff',
      fontFamily: '-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif', fontSize: '14px'
    }
  });
  const keys = Object.keys(targets).sort((a, b) => b.length - a.length);
  const escapeRegex = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  for (const diagram of document.querySelectorAll('.mermaid')) {
    const wrap = diagram.closest('.mermaid-wrap');
    try {
      await mermaid.run({nodes: [diagram]});
    } catch (error) {
      wrap.querySelector('.mermaid-hint').textContent = 'Diagram could not render. Use the document links below.';
      continue;
    }
    const svg = diagram.querySelector('svg');
    if (!svg) continue;
    const toolbar = document.createElement('div');
    toolbar.className = 'diagram-toolbar';
    const label = document.createElement('span');
    label.textContent = 'Architecture explorer';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Expand diagram';
    button.setAttribute('aria-expanded', 'false');
    const dialog = document.createElement('dialog');
    dialog.className = 'diagram-dialog';
    dialog.setAttribute('aria-label', 'Expanded architecture diagram');
    const placeholder = document.createComment('diagram position');
    dialog.addEventListener('close', () => {
      placeholder.replaceWith(wrap);
      wrap.classList.remove('diagram-expanded');
      button.textContent = 'Expand diagram';
      button.setAttribute('aria-expanded', 'false');
      button.focus({preventScroll: true});
    });
    document.body.append(dialog);
    const toggle = () => {
      if (dialog.open) { dialog.close(); return; }
      wrap.before(placeholder);
      dialog.append(wrap);
      wrap.classList.add('diagram-expanded');
      button.textContent = 'Close diagram · Esc';
      button.setAttribute('aria-expanded', 'true');
      dialog.showModal();
    };
    button.addEventListener('click', toggle);
    toolbar.append(label, button);
    wrap.prepend(toolbar);
    const nodes = svg.querySelectorAll('.node');
    let linked = 0;
    for (const el of nodes) {
      const key = keys.find(k => el.id === k || new RegExp('-' + escapeRegex(k) + '-\\d+$').test(el.id));
      if (!key) continue;
      const target = targets[key];
      linked++;
      el.classList.add('mm-link', 'mm-' + target.kind);
      // A real SVG link supports keyboard navigation, copy-link, and opening a tab.
      const link = document.createElementNS('http://www.w3.org/2000/svg', 'a');
      link.setAttribute('href', target.href);
      link.setAttribute('aria-label', 'Explore ' + target.title);
      link.setAttribute('tabindex', '0');
      el.parentNode.insertBefore(link, el);
      link.append(el);
      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = target.title + ' · ' + (target.kind === 'component' ? 'Open component' : 'Read implementation section');
      el.append(title);
      link.addEventListener('click', () => {
        if (dialog.open) dialog.close();
      });
    }
    label.textContent = linked + ' linked nodes · select to explore';
  }
})();
