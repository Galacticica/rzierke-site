import cytoscape from 'cytoscape';

const graphRoot = document.getElementById('mcu-graph');

if (graphRoot) {
  const loadState    = document.getElementById('graph-load-state');
  const graphViewer  = document.getElementById('graph-viewer');
  const summary      = document.getElementById('graph-summary');
  const statusBanner = document.getElementById('path-status');
  const fromInput    = document.getElementById('path-from');
  const toInput      = document.getElementById('path-to');
  const searchButton = document.getElementById('path-search-btn');
  const clearButton  = document.getElementById('path-clear-btn');
  const fullscreenButton = document.getElementById('fullscreen-btn');
  const filterInputs = Array.from(document.querySelectorAll('[data-graph-filter]'));
  const characterOptions = JSON.parse(document.getElementById('character-options').textContent);
  const nameToId = new Map(
    characterOptions.map((c) => [c.name.toLowerCase(), String(c.id)])
  );
  let activePayload = { nodes: [], edges: [] };
  let fullGraphPayload = null;

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

  // ─── Force simulation ──────────────────────────────────────────────────────
  //
  // Velocity-Verlet integration with a single pinned-node concept for dragging.
  //
  // DRAG BEHAVIOUR (Neo4j-like):
  //   - The sim keeps running the whole time a node is dragged.
  //   - The dragged node is "pinned": the sim reads its position from Cytoscape
  //     (which Cytoscape keeps at the cursor) but never writes back to it.
  //   - Because the dragged node moves, the spring forces to its neighbors
  //     increase, and the sim naturally pulls them along — no manual nudging.
  //   - On release, we reheat so the graph settles from its new configuration.

  const NODE_RADIUS   = 46;
  const MIN_DIST      = NODE_RADIUS * 2 + 20; // hard floor: ~112 px

  const REPULSION     = 90000;
  const LINK_DIST     = 220;
  const LINK_STRENGTH = 0.018;   // weak springs — repulsion dominates at close range
  const GRAVITY       = 0.005;
  const FRICTION      = 0.78;   // lower = more damping, slower settle
  const MAX_VEL       = 14;

  const ALPHA_START   = 1.0;
  const ALPHA_REHEAT  = 0.55;
  const ALPHA_DECAY   = 0.007;  // slow decay → long, smooth settle
  const MIN_ALPHA     = 0.001;

  const vel    = {};  // { [nodeId]: { vx, vy } }
  let alpha    = 0;
  let simRaf   = null;
  let pinnedId = null; // id of node currently under the cursor — excluded from writes

  function getVel(id) {
    if (!vel[id]) vel[id] = { vx: 0, vy: 0 };
    return vel[id];
  }

  function simTick() {
    if (alpha < MIN_ALPHA) { simRaf = null; return; }

    const nodes = cy.nodes();
    const edges = cy.edges();

    // Read current positions (including pinned node at cursor position)
    const pos = {};
    nodes.forEach(n => {
      pos[n.id()] = { x: n.position('x'), y: n.position('y') };
      getVel(n.id());
    });

    const ids = Object.keys(pos);
    const len = ids.length;

    // 1. Pairwise repulsion + hard-floor separation
    for (let i = 0; i < len; i++) {
      const a  = ids[i];
      const pa = pos[a];
      for (let j = i + 1; j < len; j++) {
        const b  = ids[j];
        const pb = pos[b];

        let dx   = pb.x - pa.x;
        let dy   = pb.y - pa.y;
        let dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 0.5) {
          dx = (Math.random() - 0.5) * 2;
          dy = (Math.random() - 0.5) * 2;
          dist = Math.sqrt(dx * dx + dy * dy) || 0.5;
        }

        // Hard separation: push positions apart instantly, no spring needed
        if (dist < MIN_DIST) {
          const push = (MIN_DIST - dist) * 0.5;
          const nx = dx / dist;
          const ny = dy / dist;
          // Only push non-pinned nodes
          if (a !== pinnedId) { pa.x -= nx * push; pa.y -= ny * push; }
          if (b !== pinnedId) { pb.x += nx * push; pb.y += ny * push; }
          dist = MIN_DIST;
        }

        const force = REPULSION / (dist * dist);
        const nx = dx / dist;
        const ny = dy / dist;
        if (a !== pinnedId) { vel[a].vx -= nx * force * alpha; vel[a].vy -= ny * force * alpha; }
        if (b !== pinnedId) { vel[b].vx += nx * force * alpha; vel[b].vy += ny * force * alpha; }
      }
    }

    // 2. Spring attraction along edges
    edges.forEach(e => {
      const s  = String(e.data('source'));
      const t  = String(e.data('target'));
      const ps = pos[s];
      const pt = pos[t];
      if (!ps || !pt) return;

      const dx   = pt.x - ps.x;
      const dy   = pt.y - ps.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const delta = (dist - LINK_DIST) * LINK_STRENGTH;
      const fx = (dx / dist) * delta;
      const fy = (dy / dist) * delta;

      if (s !== pinnedId) { vel[s].vx += fx * alpha; vel[s].vy += fy * alpha; }
      if (t !== pinnedId) { vel[t].vx -= fx * alpha; vel[t].vy -= fy * alpha; }
    });

    // 3. Weak gravity toward origin
    ids.forEach(id => {
      if (id === pinnedId) return;
      vel[id].vx -= pos[id].x * GRAVITY * alpha;
      vel[id].vy -= pos[id].y * GRAVITY * alpha;
    });

    // 4. Integrate velocity → position, write back (skip pinned/locked)
    nodes.forEach(n => {
      const id = n.id();

      if (id === pinnedId) return;

      const v = vel[id];
      v.vx *= FRICTION;
      v.vy *= FRICTION;

      const speed = Math.sqrt(v.vx * v.vx + v.vy * v.vy);
      if (speed > MAX_VEL) { v.vx = v.vx / speed * MAX_VEL; v.vy = v.vy / speed * MAX_VEL; }

      const p = pos[id];
      n.position({ x: p.x + v.vx, y: p.y + v.vy });
    });

    alpha  *= (1 - ALPHA_DECAY);
    simRaf  = requestAnimationFrame(simTick);
  }

  function reheatSim(amount = ALPHA_REHEAT) {
    alpha = Math.max(alpha, amount);
    if (!simRaf) simRaf = requestAnimationFrame(simTick);
  }

  // ─── Drag: pin the grabbed node so the sim doesn't fight the cursor ─────────
  cy.on('grab', 'node', evt => {
    pinnedId = evt.target.id();
    vel[pinnedId] = { vx: 0, vy: 0 };
    reheatSim(ALPHA_REHEAT);
  });

  cy.on('free', 'node', evt => {
    const id = evt.target.id();
    // Keep pinnedId set for a further 12 frames after release so the sim
    // cannot move the node while spring forces are still hot. After that
    // the node becomes a normal participant and settles naturally.
    let framesLeft = 12;
    const holdPin = () => {
      framesLeft--;
      if (framesLeft > 0) {
        requestAnimationFrame(holdPin);
      } else {
        vel[id] = { vx: 0, vy: 0 };
        pinnedId = null;
      }
    };
    requestAnimationFrame(holdPin);
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
    Object.keys(vel).forEach(id => delete vel[id]);

    cy.json({ elements: payload });

    const n = payload.nodes.length;
    const baseRadius = Math.max(300, Math.sqrt(n) * 130);

    cy.nodes().forEach((node, i) => {
      const r     = baseRadius * Math.sqrt((i + 0.5) / n);
      const theta = 2 * Math.PI * i / (PHI * PHI);
      node.position({ x: r * Math.cos(theta), y: r * Math.sin(theta) });
      vel[node.id()] = { vx: 0, vy: 0 };
    });

    cy.fit(cy.elements(), 60);
    if (simRaf) { cancelAnimationFrame(simRaf); simRaf = null; }
    reheatSim(ALPHA_START);

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
    const direct = characterOptions.find(
      c => c.name.toLowerCase() === input.trim().toLowerCase()
    );
    if (direct) return String(direct.id);
    return nameToId.get(input.trim().toLowerCase()) || '';
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

  // ─── Filter controls ───────────────────────────────────────────────────────
  const loadFilteredGraph = async () => {
    const params = buildParams();
    const labelParts = [];
    filterInputs.forEach(input => {
      if (input.value) labelParts.push(`${input.dataset.graphFilter}: ${input.value}`);
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
    fromInput.value = '';
    toInput.value   = '';
    clearStatus();
    loadFilteredGraph().catch(err => {
      console.error(err);
      setStatus('Failed to restore the graph.', 'error');
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