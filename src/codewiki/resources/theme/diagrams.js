/* Diagram navigation uses validated document/section IDs emitted by the build. */
(async () => {
  const labels = {'Diagram could not render. Use the document links below.': '圖表無法渲染，請使用下方的文件連結。', 'Architecture explorer': '架構探索', 'Expand diagram': '展開圖表', 'Expanded architecture diagram': '已展開的架構圖', 'Close diagram · Esc': '關閉圖表 · Esc', 'Explore ': '探索 ', 'Open component': '開啟元件', 'Read implementation section': '閱讀實作章節', ' linked nodes · select to explore': ' 個連結節點 · 點選以探索'};
  const tr = text => document.documentElement.lang === 'zh-TW' ? (labels[text] || text) : text;
  Object.assign(labels, {
    'Zoom in': '放大', 'Zoom out': '縮小', 'Fit': '符合視窗',
    'Fit diagram': '圖表符合視窗', 'Diagram zoom': '圖表縮放比例',
    'Interactive diagram': '互動圖表',
    'Scroll to zoom · Drag to move · Focus diagram: + / − to zoom, arrows to move, 0 to fit':
      '滾動以縮放 · 拖曳以移動 · 聚焦圖表後：+ / − 縮放、方向鍵移動、0 符合視窗'
  });
  const enableZoom = (diagram, svg, toolbar) => {
    const box = svg.viewBox.baseVal;
    if (!box || box.width <= 0 || box.height <= 0) return;
    const initial = {x: box.x, y: box.y, width: box.width, height: box.height};
    let view = {...initial};
    let zoom = 1;
    const viewport = document.createElement('div');
    viewport.className = 'diagram-viewport';
    viewport.tabIndex = 0;
    viewport.setAttribute('role', 'group');
    viewport.setAttribute('aria-label', tr('Interactive diagram'));
    viewport.style.aspectRatio = `${initial.width} / ${initial.height}`;
    diagram.before(viewport);
    viewport.append(diagram);
    diagram.closest('.mermaid-wrap').classList.add('diagram-interactive');
    const hint = document.createElement('p');
    hint.className = 'diagram-gesture-hint';
    hint.id = `diagram-controls-${document.querySelectorAll('.diagram-viewport').length}`;
    hint.textContent = tr('Scroll to zoom · Drag to move · Focus diagram: + / − to zoom, arrows to move, 0 to fit');
    viewport.setAttribute('aria-describedby', hint.id);
    viewport.after(hint);
    const controls = document.createElement('div');
    controls.className = 'diagram-controls';
    const makeButton = (text, title, action) => {
      const control = document.createElement('button');
      control.type = 'button';
      control.textContent = text;
      control.title = tr(title);
      control.setAttribute('aria-label', tr(title));
      control.addEventListener('click', action);
      controls.append(control);
      return control;
    };
    const readout = document.createElement('output');
    readout.setAttribute('aria-label', tr('Diagram zoom'));
    const render = () => {
      svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.width} ${view.height}`);
      readout.textContent = `${Math.round(zoom * 100)}%`;
      smaller.disabled = zoom <= 0.25;
      larger.disabled = zoom >= 8;
    };
    const pointAt = (x, y) => {
      const point = svg.createSVGPoint();
      point.x = x;
      point.y = y;
      return point.matrixTransform(svg.getScreenCTM().inverse());
    };
    const zoomAt = (factor, point = {x: view.x + view.width / 2, y: view.y + view.height / 2}) => {
      const next = Math.max(0.25, Math.min(8, zoom * factor));
      const ratio = zoom / next;
      view = {x: point.x + (view.x - point.x) * ratio,
        y: point.y + (view.y - point.y) * ratio,
        width: view.width * ratio, height: view.height * ratio};
      zoom = next;
      render();
    };
    const fit = () => { view = {...initial}; zoom = 1; render(); };
    const smaller = makeButton('−', 'Zoom out', () => zoomAt(1 / 1.25));
    controls.append(readout);
    const larger = makeButton('+', 'Zoom in', () => zoomAt(1.25));
    makeButton(tr('Fit'), 'Fit diagram', fit);
    toolbar.insertBefore(controls, toolbar.lastElementChild);
    render();
    viewport.addEventListener('wheel', event => {
      event.preventDefault();
      const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1);
      zoomAt(Math.exp(-Math.max(-100, Math.min(100, pixels)) * 0.002), pointAt(event.clientX, event.clientY));
    }, {passive: false});
    // Capture only after movement so clicking a linked node keeps native link behavior.
    let drag = null;
    let suppressClick = false;
    viewport.addEventListener('pointerdown', event => {
      if (!event.isPrimary || event.button !== 0) return;
      suppressClick = false;
      drag = {id: event.pointerId, x: event.clientX, y: event.clientY, moved: false};
    });
    viewport.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      if (!drag.moved && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      if (!drag.moved) {
        viewport.setPointerCapture(event.pointerId);
        viewport.focus({preventScroll: true});
        viewport.classList.add('is-panning');
        drag.moved = true;
      }
      const before = pointAt(drag.x, drag.y);
      const after = pointAt(event.clientX, event.clientY);
      view.x += before.x - after.x;
      view.y += before.y - after.y;
      drag.x = event.clientX;
      drag.y = event.clientY;
      render();
    });
    const endDrag = event => {
      if (!drag || drag.id !== event.pointerId) return;
      suppressClick = drag.moved;
      drag = null;
      viewport.classList.remove('is-panning');
      if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    };
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) viewport.addEventListener(name, endDrag);
    viewport.addEventListener('pointerleave', event => { if (drag && !drag.moved) endDrag(event); });
    viewport.addEventListener('dragstart', event => event.preventDefault());
    viewport.addEventListener('click', event => {
      if (suppressClick && event.detail !== 0) {
        event.preventDefault();
        event.stopPropagation();
        suppressClick = false;
      }
    }, true);
    viewport.addEventListener('keydown', event => {
      if (event.target !== viewport || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === '+' || event.key === '=') zoomAt(1.25);
      else if (event.key === '-') zoomAt(1 / 1.25);
      else if (event.key === '0' || event.key === 'Home') fit();
      else if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
        const step = 40 * (event.shiftKey ? 3 : 1);
        const origin = pointAt(0, 0);
        const offset = pointAt(event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0,
          event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0);
        view.x += offset.x - origin.x;
        view.y += offset.y - origin.y;
        render();
      } else return;
      event.preventDefault();
    });
  };
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
      wrap.querySelector('.mermaid-hint').textContent = tr('Diagram could not render. Use the document links below.');
      continue;
    }
    const svg = diagram.querySelector('svg');
    if (!svg) continue;
    const toolbar = document.createElement('div');
    toolbar.className = 'diagram-toolbar';
    const label = document.createElement('span');
    label.textContent = tr('Architecture explorer');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = tr('Expand diagram');
    button.setAttribute('aria-expanded', 'false');
    const dialog = document.createElement('dialog');
    dialog.className = 'diagram-dialog';
    dialog.setAttribute('aria-label', tr('Expanded architecture diagram'));
    const placeholder = document.createComment('diagram position');
    dialog.addEventListener('close', () => {
      placeholder.replaceWith(wrap);
      wrap.classList.remove('diagram-expanded');
      button.textContent = tr('Expand diagram');
      button.setAttribute('aria-expanded', 'false');
      button.focus({preventScroll: true});
    });
    document.body.append(dialog);
    const toggle = () => {
      if (dialog.open) { dialog.close(); return; }
      wrap.before(placeholder);
      dialog.append(wrap);
      wrap.classList.add('diagram-expanded');
      button.textContent = tr('Close diagram · Esc');
      button.setAttribute('aria-expanded', 'true');
      dialog.showModal();
    };
    button.addEventListener('click', toggle);
    toolbar.append(label, button);
    wrap.prepend(toolbar);
    enableZoom(diagram, svg, toolbar);
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
      link.setAttribute('aria-label', tr('Explore ') + target.title);
      link.setAttribute('tabindex', '0');
      el.parentNode.insertBefore(link, el);
      link.append(el);
      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = target.title + ' · ' + (target.kind === 'component' ? tr('Open component') : tr('Read implementation section'));
      el.append(title);
      link.addEventListener('click', () => {
        if (dialog.open) dialog.close();
      });
    }
    label.textContent = linked + tr(' linked nodes · select to explore');
  }
})();
