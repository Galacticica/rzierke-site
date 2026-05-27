import cytoscape from 'cytoscape';
import * as d3 from 'd3';

const graphRoot = document.getElementById('mcu-graph');

if (graphRoot) {
  const loadState    = document.getElementById('graph-load-state');
  const graphViewer  = document.getElementById('graph-viewer');
  const summary      = document.getElementById('graph-summary');
  const statusBanner = document.getElementById('path-status');
  const nodePopup    = document.getElementById('character-node-popup');
  const popupName    = nodePopup?.querySelector('[data-node-popup-name]');
  const popupStatus  = nodePopup?.querySelector('[data-node-popup-status]');
  const popupAliases = nodePopup?.querySelector('[data-node-popup-aliases]');
  const popupTeams   = nodePopup?.querySelector('[data-node-popup-teams]');
  const popupMovies  = nodePopup?.querySelector('[data-node-popup-movies]');
  const popupHandle  = nodePopup?.querySelector('[data-node-popup-handle]');
  const popupClose   = nodePopup?.querySelector('[data-node-popup-close]');
  const fromInput    = document.getElementById('path-from');
  const toInput      = document.getElementById('path-to');
  const searchButton = document.getElementById('path-search-btn');
  const clearButton  = document.getElementById('path-clear-btn');
  const resetGraphButton = document.getElementById('reset-graph-btn');
  const fullscreenButton = document.getElementById('fullscreen-btn');
  const filterInputs = Array.from(document.querySelectorAll('[data-graph-filter]'));
  const characterOptions = JSON.parse(document.getElementById('character-options').textContent);
  const nameToId = new Map(
    characterOptions.map((c) => [c.name.toLowerCase(), String(c.id)])
  );
  let activePayload = { nodes: [], edges: [] };
  let fullGraphPayload = null;
  let popupDragState = null;
  let popupPosition = { left: 0, top: 0 };

  if (nodePopup && nodePopup.parentElement !== document.body) {
    document.body.appendChild(nodePopup);
  }

  const alignmentColors = {
    hero:     '#38BDF8',
    villain:  '#FB7185',
    neutral:  '#E5E7EB',
    reformed: '#34D399',
    fallen:   '#FBBF24',
  };

  const relationshipColors = {
    Variant:      '#FACC15',
    Ally:         '#7DD3FC',
    Enemy:        '#FB7185',
    Romantic:     '#F472B6',
    Mentor:       '#FB923C',
    Family:       '#16A34A',
    Acquaintance: '#E5E7EB',
    Creation:     '#A78BFA',
  };

  graphRoot.style.cursor = 'grab';
  graphRoot.addEventListener('mousedown', () => {
    graphRoot.style.cursor = 'grabbing';
  });
  graphRoot.addEventListener('mouseup', () => {
    graphRoot.style.cursor = 'grab';
  });
  graphRoot.addEventListener('mouseleave', () => {
    graphRoot.style.cursor = 'grab';
  });
  graphRoot.addEventListener('touchstart', () => {
    graphRoot.style.cursor = 'grabbing';
  }, { passive: true });
  graphRoot.addEventListener('touchend', () => {
    graphRoot.style.cursor = 'grab';
  }, { passive: true });

  // ─── Cytoscape instance ────────────────────────────────────────────────────
  const cy = cytoscape({
    container: graphRoot,
    elements: [],
    wheelSensitivity: 0.75,
    boxSelectionEnabled: false,
    layout: { name: 'preset' },
    style: [
      {
        selector: 'core',
        style: {
          'active-bg-opacity': 0,
          'active-bg-color': 'transparent',
          'selection-box-opacity': 0,
          'selection-box-color': 'transparent',
          'selection-box-border-width': 0,
        },
      },
      {
        selector: 'node',
        style: {
          width: 92, height: 92,
          'background-fit': 'cover',
          'background-clip': 'node',
          'background-image': 'data(photo_url)',
          'background-color': '#2A1841',
          'border-width': 4,
          'border-color': '#8B5CF6',
          label: 'data(label)',
          color: '#E9E0F5',
          'font-size': 11,
          'font-weight': 700,
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 10,
          'text-outline-color': '#12061F',
          'text-outline-width': 2,
        },
      },
      { selector: 'node.hero',     style: { 'border-color': alignmentColors.hero } },
      { selector: 'node.villain',  style: { 'border-color': alignmentColors.villain } },
      { selector: 'node.neutral',  style: { 'border-color': alignmentColors.neutral } },
      { selector: 'node.reformed', style: { 'border-color': alignmentColors.reformed } },
      { selector: 'node.fallen',   style: { 'border-color': alignmentColors.fallen } },
      { selector: 'node.alive',    style: { shape: 'ellipse' } },
      { selector: 'node.deceased', style: { 'border-style': 'dashed' } },
      {
        selector: 'node:selected, node:active, node:grabbed',
        style: {
          'overlay-opacity': 0,
          'overlay-padding': 0,
        },
      },
      {
        selector: 'edge',
        style: {
          width: 3,
          'line-color': 'rgba(233, 224, 245, 0.45)',
          'target-arrow-color': 'rgba(233, 224, 245, 0.55)',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          label: '',
          'font-size': 9,
          color: '#D8D5DD',
        },
      },
      { selector: 'edge[relationship_type = "Variant"]',  style: { 'line-color': relationshipColors.Variant, 'target-arrow-color': relationshipColors.Variant } },
      { selector: 'edge[relationship_type = "Ally"]',     style: { 'line-color': relationshipColors.Ally, 'target-arrow-color': relationshipColors.Ally } },
      { selector: 'edge[relationship_type = "Enemy"]',    style: { 'line-color': relationshipColors.Enemy, 'target-arrow-color': relationshipColors.Enemy } },
      { selector: 'edge[relationship_type = "Romantic"]', style: { 'line-color': relationshipColors.Romantic, 'target-arrow-color': relationshipColors.Romantic } },
      { selector: 'edge[relationship_type = "Mentor"]',   style: { 'line-color': relationshipColors.Mentor, 'target-arrow-color': relationshipColors.Mentor } },
      { selector: 'edge[relationship_type = "Family"]',   style: { 'line-color': relationshipColors.Family, 'target-arrow-color': relationshipColors.Family } },
      { selector: 'edge[relationship_type = "Acquaintance"]', style: { 'line-color': relationshipColors.Acquaintance, 'target-arrow-color': relationshipColors.Acquaintance } },
      { selector: 'edge[relationship_type = "Creation"]', style: { 'line-color': relationshipColors.Creation, 'target-arrow-color': relationshipColors.Creation } },
      { selector: 'edge.undirected', style: { 'target-arrow-shape': 'none' } },
      {
        selector: '.highlighted',
        style: {
          'overlay-opacity': 0.18,
          'overlay-color': '#22D3EE',
          'border-color': '#22D3EE',
          'line-color': '#22D3EE',
          'target-arrow-color': '#22D3EE',
          'z-index': 999,
        },
      },
    ],
  });

  const hideNodePopup = () => {
    if (!nodePopup) return;
    nodePopup.hidden = true;
    nodePopup.dataset.characterId = '';
    popupDragState = null;
  };

  const setNodePopupPosition = (left, top) => {
    if (!nodePopup || nodePopup.hidden) return;

    const margin = 12;
    const rect = nodePopup.getBoundingClientRect();
    const width = rect.width || nodePopup.offsetWidth || 0;
    const height = rect.height || nodePopup.offsetHeight || 0;
    const maxLeft = Math.max(margin, window.innerWidth - width - margin);
    const maxTop = Math.max(margin, window.innerHeight - height - margin);
    const clampedLeft = Math.max(margin, Math.min(left, maxLeft));
    const clampedTop = Math.max(margin, Math.min(top, maxTop));

    popupPosition = { left: clampedLeft, top: clampedTop };
    nodePopup.style.left = `${clampedLeft}px`;
    nodePopup.style.top = `${clampedTop}px`;
    nodePopup.dataset.left = String(clampedLeft);
    nodePopup.dataset.top = String(clampedTop);
  };

  const renderPopupSection = (container, items, renderItem, emptyLabel) => {
    if (!container) return;
    container.replaceChildren();

    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'graph-node-popup__empty';
      empty.textContent = emptyLabel;
      container.appendChild(empty);
      return;
    }

    const list = document.createElement('ul');
    list.className = 'graph-node-popup__list';

    items.forEach((item) => {
      const listItem = document.createElement('li');
      listItem.className = 'graph-node-popup__list-item';
      renderItem(listItem, item);
      list.appendChild(listItem);
    });

    container.appendChild(list);
  };

  const showNodePopup = (node) => {
    if (!nodePopup) return;

    const data = node.data() || {};
    const details = data.details || {};
    const statusLabel = details.status_label || details.status || data.status || 'Unknown';

    if (popupName) popupName.textContent = data.label || data.name || 'Character';
    if (popupStatus) popupStatus.textContent = `Status: ${statusLabel}`;

    renderPopupSection(
      popupAliases,
      details.aliases || [],
      (listItem, alias) => {
        listItem.textContent = alias;
      },
      'No aliases listed.'
    );

    renderPopupSection(
      popupTeams,
      details.teams || [],
      (listItem, team) => {
        const title = document.createElement('div');
        title.className = 'graph-node-popup__list-title';
        title.textContent = team.name;

        const meta = document.createElement('div');
        meta.className = 'graph-node-popup__list-meta';
        meta.textContent = team.status;

        listItem.append(title, meta);
      },
      'No team memberships listed.'
    );

    renderPopupSection(
      popupMovies,
      details.movies || [],
      (listItem, movie) => {
        const title = document.createElement('div');
        title.className = 'graph-node-popup__list-title';
        title.textContent = movie.title;

        const meta = document.createElement('div');
        meta.className = 'graph-node-popup__list-meta';
        meta.textContent = movie.year ? `Released ${movie.year}` : 'Release year unavailable';

        listItem.append(title, meta);
      },
      'No movies listed.'
    );

    nodePopup.hidden = false;
    nodePopup.dataset.characterId = String(data.id || '');

    const renderedPosition = node.renderedPosition();
    const viewerRect = graphRoot.getBoundingClientRect();
    requestAnimationFrame(() => {
      setNodePopupPosition(viewerRect.left + renderedPosition.x + 24, viewerRect.top + renderedPosition.y + 24);
    });
  };

  nodePopup?.addEventListener('click', (event) => {
    const closeButton = event.target.closest('[data-node-popup-close]');
    if (closeButton) {
      hideNodePopup();
    }
  });

  popupHandle?.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || !nodePopup || nodePopup.hidden) return;
    if (event.target.closest('button, a, input, textarea, select, option, [data-no-popup-drag]')) return;

    const rect = nodePopup.getBoundingClientRect();
    popupDragState = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    popupHandle.setPointerCapture(event.pointerId);
    event.stopPropagation();
    event.preventDefault();
  });

  const stopPopupDrag = (event) => {
    if (!popupDragState || event.pointerId !== popupDragState.pointerId) return;
    popupDragState = null;
    try {
      popupHandle?.releasePointerCapture(event.pointerId);
    } catch {
      // Ignore pointer-capture errors when the drag ends abruptly.
    }
  };

  window.addEventListener('pointermove', (event) => {
    if (!popupDragState || event.pointerId !== popupDragState.pointerId) return;
    setNodePopupPosition(event.clientX - popupDragState.offsetX, event.clientY - popupDragState.offsetY);
  });
  window.addEventListener('pointerup', stopPopupDrag);
  window.addEventListener('pointercancel', stopPopupDrag);

  cy.on('tap', 'node', (event) => {
    showNodePopup(event.target);
  });

  const syncGraphSize = () => {
    cy.resize();
  };

  const updateFullscreenButton = () => {
    if (!fullscreenButton || !graphViewer) return;
    const isFullscreen = document.fullscreenElement === graphViewer;
    fullscreenButton.title = isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen';
  };

  const toggleFullscreen = async () => {
    if (!graphViewer) return;
    if (document.fullscreenElement === graphViewer) {
      await document.exitFullscreen();
      return;
    }
    await graphViewer.requestFullscreen();
  };

  if (typeof ResizeObserver !== 'undefined') {
    const resizeObserver = new ResizeObserver(() => {
      syncGraphSize();
    });
    resizeObserver.observe(graphRoot);
  }

  window.addEventListener('resize', syncGraphSize);
  document.addEventListener('fullscreenchange', () => {
    updateFullscreenButton();
    requestAnimationFrame(syncGraphSize);
  });

  // ─── D3 force simulation ────────────────────────────────────────────────────

  const GRAPH_NODE_R = 46;
  const ALPHA_START  = 1.0;
  const ALPHA_REHEAT = 0.55;

  let d3Sim   = null;
  let d3Nodes = null;
  let d3IdMap = {};
  let pinnedId = null;

  function getD3Node(id) { return d3IdMap[id] || null; }

  function initD3Sim(alpha = 1.0) {
    if (d3Sim) { d3Sim.stop(); d3Sim = null; }

    d3Nodes = cy.nodes().map(n => ({ id: n.id(), x: n.position('x'), y: n.position('y') }));
    d3IdMap = {};
    d3Nodes.forEach(d => { d3IdMap[d.id] = d; });

    const edgeData = cy.edges().map(e => ({ source: e.data('source'), target: e.data('target') }));

    const n = d3Nodes.length;
    const isHuge  = n > 300;
    const isLarge = n > 100;
    const BASE_CHARGE    = -2500;
    const BASE_LINK_DIST = 350;
    const chargeStrength = isHuge ? BASE_CHARGE * 0.15 : isLarge ? BASE_CHARGE * 0.5 : BASE_CHARGE;
    const linkDist       = isHuge ? BASE_LINK_DIST * 0.3 : isLarge ? BASE_LINK_DIST * 0.7 : BASE_LINK_DIST;
    const alphaDecay     = isHuge ? 0.06 : isLarge ? 0.04 : 0.02;

    d3Sim = d3.forceSimulation(d3Nodes)
      .force('link',      d3.forceLink(edgeData).id(d => d.id).distance(linkDist))
      .force('charge',    d3.forceManyBody().strength(chargeStrength).distanceMax(isHuge ? 1200 : 4000))
      .force('center',    d3.forceCenter(0, 0))
      .force('collision', d3.forceCollide().radius(isHuge ? 2 : GRAPH_NODE_R + 6))
      .force('x',         d3.forceX(0).strength(isHuge ? 0.08 : 0.04))
      .force('y',         d3.forceY(0).strength(isHuge ? 0.08 : 0.04))
      .alphaDecay(alphaDecay)
      .alphaTarget(0)
      .alpha(alpha)
      .on('tick', () => {
        cy.nodes().forEach(node => {
          const d = d3IdMap[node.id()];
          if (d) node.position({ x: d.x, y: d.y });
        });
      });
  }

  function reheatSim(amount = ALPHA_REHEAT) {
    if (!d3Sim) return;
    d3Sim.alpha(Math.max(d3Sim.alpha(), amount)).restart();
  }

  // ─── Drag: pin grabbed node so sim doesn't fight the cursor ──────────────────
  cy.on('grab', 'node', evt => {
    const id = evt.target.id();
    pinnedId = id;
    const simNode = getD3Node(id);
    if (simNode) { simNode.fx = simNode.x; simNode.fy = simNode.y; }
    if (d3Sim) d3Sim.alphaTarget(0.3).restart();
  });
  cy.on('drag', 'node', evt => {
    if (evt.target.id() === pinnedId) {
      const simNode = getD3Node(pinnedId);
      if (simNode) {
        const pos = evt.target.position();
        simNode.fx = pos.x; simNode.fy = pos.y;
        simNode.x  = pos.x; simNode.y  = pos.y;
      }
    }
  });
  cy.on('free', 'node', () => {
    if (d3Nodes) d3Nodes.forEach(d => { d.vx = 0; d.vy = 0; });
    pinnedId = null;
    if (d3Sim) d3Sim.alphaTarget(0);
  });

  // ─── Helpers ───────────────────────────────────────────────────────────────
  const setStatus = (message, kind = 'info') => {
    if (!statusBanner) return;
    statusBanner.className = `alert alert-${kind} text-sm`;
    statusBanner.textContent = message;
    statusBanner.classList.remove('hidden');
  };
  const clearStatus = () => {
    if (!statusBanner) return;
    statusBanner.className = 'alert hidden text-sm';
    statusBanner.textContent = '';
  };
  const setLoadState = (msg) => { if (loadState) loadState.textContent = msg; };
  const buildParams = () => {
    const params = new URLSearchParams();
    filterInputs.forEach(input => {
      if (input.type === 'checkbox') {
        if (input.checked && input.value) params.append(input.dataset.graphFilter, input.value);
        return;
      }

      if (input.value) params.set(input.dataset.graphFilter, input.value);
    });
    return params;
  };

  // ─── Element loading ───────────────────────────────────────────────────────
  const PHI = (1 + Math.sqrt(5)) / 2;

  const applyElements = (payload, label) => {
    activePayload = payload;
    if (d3Sim) { d3Sim.stop(); d3Sim = null; }
    d3Nodes = null; d3IdMap = {}; pinnedId = null;
    hideNodePopup();

    cy.json({ elements: payload });

    const n = payload.nodes.length;
    const baseRadius = Math.max(300, Math.sqrt(n) * 130);

    cy.nodes().forEach((node, i) => {
      const r     = baseRadius * Math.sqrt((i + 0.5) / n);
      const theta = 2 * Math.PI * i / (PHI * PHI);
      node.position({ x: r * Math.cos(theta), y: r * Math.sin(theta) });
    });

    cy.fit(cy.elements(), 60);
    initD3Sim(ALPHA_START);

    setLoadState(`${payload.nodes.length} nodes, ${payload.edges.length} edges`);
    if (summary) summary.textContent = label;
  };

  const fetchGraph = async (url, label) => {
    setLoadState('Loading...');
    const payload = await fetchGraphPayload(url);
    applyElements(payload, label);
    clearStatus();
  };

  const fetchGraphPayload = async (url) => {
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`Graph request failed with status ${response.status}`);
    return response.json();
  };

  const getFullGraphPayload = async () => {
    if (fullGraphPayload) return fullGraphPayload;
    fullGraphPayload = await fetchGraphPayload('/api/graph/');
    return fullGraphPayload;
  };

  const cloneNode = (node) => ({
    data: { ...node.data },
    classes: node.classes || '',
  });

  const cloneEdge = (edge) => ({
    data: {
      ...edge.data,
      relationship_types: [...(edge.data.relationship_types || [])],
      relationship_ids: [...(edge.data.relationship_ids || [])],
    },
    classes: edge.classes || '',
  });

  const relationshipKey = (ids = []) => ids.map(String).sort().join('|');

  const buildPathOnlyPayload = (sourcePayload, pathData) => {
    const nodeMap = new Map(sourcePayload.nodes.map(node => [String(node.data.id), node]));
    const edgeMap = new Map(
      sourcePayload.edges.map(edge => {
        const edgeKey = `${edge.data.source}->${edge.data.target}|${relationshipKey(edge.data.relationship_ids)}`;
        return [edgeKey, edge];
      })
    );

    const nodes = pathData.character_ids
      .map(id => nodeMap.get(String(id)))
      .filter(Boolean)
      .map(cloneNode);

    const edges = pathData.highlighted_edges
      .map(edge => {
        const preciseKey = `${String(edge.source)}->${String(edge.target)}|${relationshipKey(edge.relationship_ids)}`;
        const fallbackKey = `${String(edge.source)}->${String(edge.target)}|`;
        const edgeCandidate = edgeMap.get(preciseKey)
          || sourcePayload.edges.find(candidate =>
            candidate.data.source === String(edge.source)
            && candidate.data.target === String(edge.target)
          )
          || edgeMap.get(fallbackKey);
        return edgeCandidate ? cloneEdge(edgeCandidate) : null;
      })
      .filter(Boolean);

    return { nodes, edges };
  };

  // ─── Path search ───────────────────────────────────────────────────────────
  const getCharacterId = (input) => {
    if (!input) return '';
    const trimmed = input.trim();
    if (/^\d+$/.test(trimmed)) return trimmed;
    const direct = characterOptions.find(
      c => c.name.toLowerCase() === trimmed.toLowerCase()
    );
    if (direct) return String(direct.id);
    return nameToId.get(trimmed.toLowerCase()) || '';
  };

  const runPathSearch = async () => {
    const fromId = getCharacterId(fromInput.value);
    const toId   = getCharacterId(toInput.value);
    if (!fromId || !toId) {
      setStatus('Select two valid character names from the suggestions.', 'warning');
      return;
    }
    setStatus('Searching for the shortest path...', 'info');
    const response = await fetch(
      `/api/graph/path/?${new URLSearchParams({ from: fromId, to: toId })}`,
      { headers: { Accept: 'application/json' } }
    );
    const payload = await response.json();
    if (!response.ok) {
      setStatus(payload.error || 'No path could be found.', 'warning');
      return;
    }

    const needsFullGraph = payload.character_ids.some(id =>
      !activePayload.nodes.some(node => String(node.data.id) === String(id))
    );

    const sourcePayload = needsFullGraph ? await getFullGraphPayload() : activePayload;
    const pathOnlyPayload = buildPathOnlyPayload(sourcePayload, payload);

    if (!pathOnlyPayload.nodes.length) {
      setStatus('Path was found, but path nodes could not be rendered.', 'warning');
      return;
    }

    applyElements(
      pathOnlyPayload,
      `Showing path view with ${pathOnlyPayload.nodes.length} nodes and ${pathOnlyPayload.edges.length} edges.`
    );
    setStatus(`Path found with total traversal cost ${payload.total_cost}.`, 'success');
  };

  // ─── Zoom controls ─────────────────────────────────────────────────────────
  const ZOOM_FACTOR = 1.2;
  document.getElementById('zoom-fit-btn')?.addEventListener('click', () => cy.fit(cy.elements(), 60));
  document.getElementById('zoom-in-btn')?.addEventListener('click', () => {
    const c = { x: cy.width() / 2, y: cy.height() / 2 };
    cy.zoom({ level: Math.min(cy.maxZoom(), cy.zoom() * ZOOM_FACTOR), renderedPosition: c });
  });
  document.getElementById('zoom-out-btn')?.addEventListener('click', () => {
    const c = { x: cy.width() / 2, y: cy.height() / 2 };
    cy.zoom({ level: Math.max(cy.minZoom(), cy.zoom() / ZOOM_FACTOR), renderedPosition: c });
  });
  fullscreenButton?.addEventListener('click', () => {
    toggleFullscreen().catch(err => {
      console.error(err);
      setStatus('Fullscreen is not available in this browser.', 'warning');
    });
  });
  updateFullscreenButton();

  // ─── Movie filter search ───────────────────────────────────────────────────
document.querySelectorAll('[data-graph-filter-search]').forEach(searchInput => {
  const filterName = searchInput.dataset.graphFilterSearch;
  const panel = searchInput.closest('.graph-filter-dropdown-panel');
  searchInput.addEventListener('input', () => {
    const query = searchInput.value.toLowerCase();
    panel.querySelectorAll('.graph-filter-option').forEach(option => {
      const text = option.textContent.trim().toLowerCase();
      option.style.display = text.includes(query) ? '' : 'none';
    });
  });
  // Prevent the dropdown from closing when clicking the search input
  searchInput.addEventListener('click', e => e.stopPropagation());
});

// ─── Character path searchable dropdowns ──────────────────────────────────
['from', 'to'].forEach(side => {
  const dropdown  = document.getElementById(`path-${side}-dropdown`);
  const hidden    = document.getElementById(`path-${side}`);
  const labelEl   = document.getElementById(`path-${side}-label`);
  const searchEl  = dropdown.querySelector(`[data-character-search="${side}"]`);

  searchEl.addEventListener('click', e => e.stopPropagation());

  searchEl.addEventListener('input', () => {
    const query = searchEl.value.toLowerCase();
    dropdown.querySelectorAll(`[data-character-optgroup="${side}"]`).forEach(group => {
      let anyVisible = false;
      group.querySelectorAll(`[data-character-select="${side}"]`).forEach(opt => {
        const match = opt.dataset.characterName.toLowerCase().includes(query);
        opt.style.display = match ? '' : 'none';
        if (match) anyVisible = true;
      });
      group.style.display = anyVisible ? '' : 'none';
    });
  });

  dropdown.querySelectorAll(`[data-character-select="${side}"]`).forEach(opt => {
    opt.addEventListener('click', () => {
      hidden.value = opt.dataset.characterId;
      labelEl.textContent = opt.dataset.characterName;
      labelEl.classList.remove('placeholder');
      searchEl.value = '';
      // Reset visibility
      dropdown.querySelectorAll(`[data-character-select="${side}"]`).forEach(o => o.style.display = '');
      dropdown.querySelectorAll(`[data-character-optgroup="${side}"]`).forEach(g => g.style.display = '');
      dropdown.removeAttribute('open');
    });
  });
});

  const resetPathSelectors = () => {
  ['from', 'to'].forEach(side => {
    document.getElementById(`path-${side}`).value = '';
    document.getElementById(`path-${side}-label`).textContent = 'Select a character';
    document.getElementById(`path-${side}-label`).classList.add('placeholder');
    const dd = document.getElementById(`path-${side}-dropdown`);
    dd.querySelector(`[data-character-search="${side}"]`).value = '';
    dd.querySelectorAll(`[data-character-select="${side}"]`).forEach(o => o.style.display = '');
    dd.querySelectorAll(`[data-character-optgroup="${side}"]`).forEach(g => g.style.display = '');
    dd.open = false;
  });
  };

  // ─── Filter controls ───────────────────────────────────────────────────────
  const loadFilteredGraph = async () => {
    const params = buildParams();
    const labelParts = [];
    filterInputs.forEach(input => {
      if (!input.value) return;
      const labelValue = input.dataset.graphFilterLabel || input.value;
      labelParts.push(`${input.dataset.graphFilter}: ${labelValue}`);
    });
    const label = labelParts.length
      ? `Filtered by ${labelParts.join(', ')}.`
      : 'Showing the full graph.';
    const query = params.toString();
    await fetchGraph(query ? `/api/graph/filter/?${query}` : '/api/graph/filter/', label);
  };

  filterInputs.forEach(input => {
    input.addEventListener('change', () => {
      loadFilteredGraph().catch(err => {
        console.error(err);
        setStatus('Failed to load the filtered graph.', 'error');
      });
    });
  });

  searchButton.addEventListener('click', () => {
    runPathSearch().catch(err => {
      console.error(err);
      setStatus('Path search failed.', 'error');
    });
  });

  clearButton.addEventListener('click', () => {
    resetPathSelectors();
    clearStatus();
    loadFilteredGraph().catch(err => {
      console.error(err);
      setStatus('Failed to restore the graph.', 'error');
    });
  });

  resetGraphButton?.addEventListener('click', () => {
    filterInputs.forEach((input) => {
      if (input.type === 'checkbox') {
        input.checked = false;
      } else {
        input.value = '';
      }
    });

    resetPathSelectors();
    hideNodePopup();
    clearStatus();
    loadFilteredGraph().catch(err => {
      console.error(err);
      setStatus('Failed to reset the graph.', 'error');
    });
  });

  // ─── Initial load ──────────────────────────────────────────────────────────
  loadFilteredGraph()
    .then(() => setLoadState('Ready'))
    .catch(err => {
      console.error(err);
      setLoadState('Failed to load graph');
      setStatus('Could not load the graph data.', 'error');
    });
}