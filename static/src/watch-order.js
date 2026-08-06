/**
 * Marvel watch-order chart.
 *
 * The server sends nodes and edges; rows are computed here so that toggling a
 * track re-lays-out instantly instead of round-tripping. Edges always point
 * from "watch this first" to "watch this after", and come in two kinds:
 * `track` edges chain a lane in order, `prerequisite` edges are the merges
 * between lanes.
 */

const STORAGE_KEY = 'mcu-watch-order:watched';
const SVG_NS = 'http://www.w3.org/2000/svg';

const chart = document.getElementById('watch-order-chart');
const dataElement = document.getElementById('watch-order-data');

if (chart && dataElement) {
	init(JSON.parse(dataElement.textContent));
}

function init(payload) {
	const entries = payload.entries || [];
	const edges = payload.edges || [];
	if (!entries.length) {
		return;
	}

	const grid = chart.querySelector('.watch-grid');
	const canvas = chart.querySelector('.watch-canvas');
	const svg = chart.querySelector('.watch-arrows');
	const entryBySlug = new Map(entries.map((entry) => [entry.slug, entry]));
	const tiles = new Map();
	chart.querySelectorAll('[data-watch-entry]').forEach((tile) => {
		tiles.set(tile.dataset.watchEntry, tile);
	});

	const authenticated = chart.dataset.authenticated === 'true';
	const hiddenTracks = new Set();
	const watched = new Set(readInitialWatched());
	let activeCollection = '';
	let visibleEdges = [];

	buildMarkers(svg, payload.tracks || []);

	// ---------------------------------------------------------------- layout

	function layout() {
		// `entries` arrives in track then position order, and filtering preserves
		// it, which is what lets the lane chains below be rebuilt by a single pass.
		const visible = entries.filter(
			(entry) =>
				!hiddenTracks.has(entry.track) &&
				(!activeCollection || entry.collections.includes(activeCollection))
		);
		const visibleSlugs = new Set(visible.map((entry) => entry.slug));

		// Lanes are re-indexed over what is still showing, so hiding a track
		// closes its column instead of leaving a gap.
		const lanes = [...new Set(visible.map((entry) => entry.lane))].sort((a, b) => a - b);
		const laneColumn = new Map(lanes.map((lane, index) => [lane, index]));

		// Chain each lane over what is actually on screen. A collection can leave
		// holes in a track, and reusing a stored chain would leave the entries
		// either side of a hole unconnected - and therefore stacked on one row.
		//
		// Keyed by lane rather than track: tracks that continue one another share
		// a lane, so the chain runs straight on from the last entry of one into
		// the first of the next without needing a prerequisite between them.
		const chainEdges = [];
		const previousInLane = new Map();
		visible.forEach((entry) => {
			const previous = previousInLane.get(entry.lane);
			if (previous) {
				chainEdges.push({ source: previous.slug, target: entry.slug, kind: 'track' });
			}
			previousInLane.set(entry.lane, entry);
		});

		visibleEdges = chainEdges.concat(
			edges.filter((edge) => visibleSlugs.has(edge.source) && visibleSlugs.has(edge.target))
		);

		const rows = assignRows(visible, visibleEdges);

		tiles.forEach((tile, slug) => {
			const entry = entryBySlug.get(slug);
			const isVisible = visibleSlugs.has(slug);
			tile.hidden = !isVisible;
			if (!isVisible) {
				return;
			}
			tile.style.gridRow = String(rows.get(slug) + 1);
			tile.style.gridColumn = String(laneColumn.get(entry.lane) + 1);
		});

		grid.style.gridTemplateColumns = `repeat(${Math.max(lanes.length, 1)}, var(--tile-width))`;
		grid.dataset.laidOut = 'true';

		// Positions are only final once the browser has reflowed the grid.
		requestAnimationFrame(draw);
	}

	/**
	 * Longest-path row assignment over the DAG (Kahn's algorithm).
	 *
	 * Because every lane is fully chained by its `track` edges, rows strictly
	 * increase down a lane, so two entries in one track can never share a row.
	 * Cross-lane prerequisites only ever push a merge target further down.
	 */
	function assignRows(visible, activeEdges) {
		const rows = new Map(visible.map((entry) => [entry.slug, 0]));
		const successors = new Map(visible.map((entry) => [entry.slug, []]));
		const indegree = new Map(visible.map((entry) => [entry.slug, 0]));

		activeEdges.forEach((edge) => {
			successors.get(edge.source).push(edge.target);
			indegree.set(edge.target, indegree.get(edge.target) + 1);
		});

		const queue = [];
		indegree.forEach((degree, slug) => {
			if (degree === 0) {
				queue.push(slug);
			}
		});

		let settled = 0;
		while (queue.length) {
			const slug = queue.shift();
			settled += 1;
			successors.get(slug).forEach((next) => {
				rows.set(next, Math.max(rows.get(next), rows.get(slug) + 1));
				indegree.set(next, indegree.get(next) - 1);
				if (indegree.get(next) === 0) {
					queue.push(next);
				}
			});
		}

		if (settled !== visible.length) {
			// The admin rejects prerequisites that close a loop, so this should be
			// unreachable. Fall back to lane order rather than rendering nothing.
			console.warn('[watch-order] cycle detected; falling back to track order');
			let fallbackRow = 0;
			visible.forEach((entry) => {
				if (indegree.get(entry.slug) > 0) {
					rows.set(entry.slug, fallbackRow += 1);
				}
			});
		}

		return rows;
	}

	// ---------------------------------------------------------------- arrows

	function draw() {
		clearPaths(svg);
		if (!visibleEdges.length) {
			return;
		}

		const canvasRect = canvas.getBoundingClientRect();
		const columnGap = parseFloat(getComputedStyle(grid).columnGap) || 32;
		const boxes = new Map();
		tiles.forEach((tile, slug) => {
			if (tile.hidden) {
				return;
			}
			const rect = tile.getBoundingClientRect();
			boxes.set(slug, {
				top: rect.top - canvasRect.top,
				bottom: rect.bottom - canvasRect.top,
				width: rect.width,
				centerX: rect.left + rect.width / 2 - canvasRect.left,
			});
		});

		// Several lanes merging into one film would otherwise stack their
		// horizontal runs into a single thick line.
		const arrivals = new Map();
		visibleEdges.forEach((edge) => {
			arrivals.set(edge.target, (arrivals.get(edge.target) || 0) + 1);
		});
		const seen = new Map();

		const fragment = document.createDocumentFragment();
		visibleEdges.forEach((edge) => {
			const from = boxes.get(edge.source);
			const to = boxes.get(edge.target);
			if (!from || !to || to.top <= from.bottom - 1) {
				return;
			}

			const index = seen.get(edge.target) || 0;
			seen.set(edge.target, index + 1);

			const color = entryBySlug.get(edge.source).track_color;
			const path = document.createElementNS(SVG_NS, 'path');
			path.setAttribute('class', 'watch-arrow');
			path.setAttribute('d', buildPath(from, to, index, arrivals.get(edge.target), columnGap));
			path.setAttribute('fill', 'none');
			path.setAttribute('stroke', color);
			path.setAttribute('stroke-width', edge.kind === 'prerequisite' ? '2.5' : '2');
			path.setAttribute('stroke-linecap', 'round');
			path.setAttribute('opacity', edge.kind === 'prerequisite' ? '0.95' : '0.7');
			path.setAttribute('marker-end', `url(#${markerId(color)})`);
			fragment.appendChild(path);
		});
		svg.appendChild(fragment);
	}

	/**
	 * Orthogonal route from one tile to another, staying out of every other tile.
	 *
	 * A merge can span several rows, so a naive diagonal or mid-span corridor
	 * would cut straight through whatever sits between the two lanes. Instead the
	 * path only ever travels through empty space: the row gaps directly below the
	 * source and above the target, and the column gap beside the source.
	 */
	function buildPath(from, to, index, arrivalCount, columnGap) {
		// Leave room for the arrowhead so its tip lands on the tile, not inside it.
		const endY = to.top - 4;

		if (Math.abs(to.centerX - from.centerX) < 1) {
			return roundedPath([
				{ x: from.centerX, y: from.bottom },
				{ x: from.centerX, y: endY },
			]);
		}

		// Fan the approach corridors apart when several lanes land on one tile.
		const spread = arrivalCount > 1 ? index * 8 : 0;
		let exitY = from.bottom + 24;
		let approachY = endY - 24 - spread;
		if (approachY <= exitY) {
			// Adjacent rows: there is only one gap, so both turns share it.
			exitY = approachY = (from.bottom + endY) / 2;
		}

		const direction = to.centerX > from.centerX ? 1 : -1;
		const channelX = from.centerX + direction * (from.width / 2 + columnGap / 2);

		return roundedPath([
			{ x: from.centerX, y: from.bottom },
			{ x: from.centerX, y: exitY },
			{ x: channelX, y: exitY },
			{ x: channelX, y: approachY },
			{ x: to.centerX, y: approachY },
			{ x: to.centerX, y: endY },
		]);
	}

	// ------------------------------------------------------------- watched

	function readInitialWatched() {
		const serverElement = document.getElementById('watch-order-watched');
		if (authenticated && serverElement) {
			return JSON.parse(serverElement.textContent) || [];
		}
		try {
			return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
		} catch {
			return [];
		}
	}

	function persistLocally() {
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify([...watched]));
		} catch {
			// Private browsing or a full quota. Progress just won't survive a reload.
		}
	}

	function setWatched(slug, isWatched) {
		if (isWatched) {
			watched.add(slug);
		} else {
			watched.delete(slug);
		}
		paintWatched();

		if (!authenticated) {
			persistLocally();
			return;
		}
		post(chart.dataset.watchedUrl, { slug, watched: isWatched }).catch(() => {
			// Roll back so the tile never claims something the server rejected.
			if (isWatched) {
				watched.delete(slug);
			} else {
				watched.add(slug);
			}
			paintWatched();
		});
	}

	function paintWatched() {
		tiles.forEach((tile, slug) => {
			const isWatched = watched.has(slug);
			tile.classList.toggle('is-watched', isWatched);
			const toggle = tile.querySelector('[data-watch-toggle]');
			if (toggle) {
				toggle.setAttribute('aria-pressed', String(isWatched));
			}
		});
		paintProgress();
		paintPopupToggle();
	}

	function paintProgress() {
		const countElement = chart.ownerDocument.querySelector('[data-watch-progress-count]');
		const remainingElement = chart.ownerDocument.querySelector('[data-watch-progress-remaining]');
		const bar = chart.ownerDocument.querySelector('[data-watch-progress-bar]');
		if (!countElement) {
			return;
		}

		// Progress follows the selected collection, not the track chips: hiding a
		// lane to declutter the view should not change what you have watched.
		const counted = activeCollection
			? entries.filter((entry) => entry.collections.includes(activeCollection))
			: entries;

		const total = counted.length;
		const done = counted.filter((entry) => watched.has(entry.slug)).length;
		const minutesLeft = counted
			.filter((entry) => !watched.has(entry.slug))
			.reduce((sum, entry) => sum + (entry.total_minutes || 0), 0);

		countElement.textContent = `${done} / ${total} watched`;
		if (remainingElement) {
			remainingElement.textContent = minutesLeft
				? `${Math.round(minutesLeft / 60)} hrs left`
				: 'all caught up';
		}
		if (bar) {
			bar.value = total ? Math.round((done / total) * 100) : 0;
		}
	}

	/** Fold progress ticked while signed out into the account, then drop the local copy. */
	function syncLocalProgress() {
		let local = [];
		try {
			local = JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
		} catch {
			return;
		}
		if (!local.length) {
			return;
		}

		post(chart.dataset.syncUrl, { slugs: local })
			.then((response) => response.json())
			.then((body) => {
				(body.watched || []).forEach((slug) => watched.add(slug));
				localStorage.removeItem(STORAGE_KEY);
				paintWatched();
			})
			.catch(() => {
				// Keep the local list so the merge can be retried on the next visit.
			});
	}

	// --------------------------------------------------------------- popup

	const popup = document.querySelector('[data-watch-popup]');
	let popupSlug = null;

	function openPopup(slug, anchor) {
		const entry = entryBySlug.get(slug);
		if (!entry || !popup) {
			return;
		}
		popupSlug = slug;

		popup.querySelector('[data-watch-popup-title]').textContent = entry.title;
		const trackElement = popup.querySelector('[data-watch-popup-track]');
		trackElement.textContent = entry.track_name;
		trackElement.style.color = entry.track_color;

		popup.querySelector('[data-watch-popup-meta]').textContent = describe(entry);

		const noteElement = popup.querySelector('[data-watch-popup-note]');
		noteElement.textContent = entry.note || '';
		noteElement.hidden = !entry.note;

		// The graph reads ?movie=<id> on load and opens filtered to that cast.
		const graphLink = popup.querySelector('[data-watch-popup-graph]');
		graphLink.hidden = !entry.movie_id;
		if (entry.movie_id) {
			graphLink.href = `${chart.dataset.graphUrl}?movie=${entry.movie_id}`;
		}

		paintPopupToggle();
		popup.hidden = false;
		positionPopup(anchor);
	}

	function describe(entry) {
		const parts = [];
		if (entry.year) {
			parts.push(entry.year);
		}
		parts.push(entry.media_type);
		if (entry.episode_count) {
			parts.push(`${entry.episode_count} episodes`);
		}
		if (entry.total_minutes) {
			const hours = Math.floor(entry.total_minutes / 60);
			const minutes = entry.total_minutes % 60;
			parts.push(hours ? `${hours}h ${minutes}m` : `${minutes}m`);
		}
		return parts.join(' · ');
	}

	function paintPopupToggle() {
		if (!popup || popup.hidden || !popupSlug) {
			return;
		}
		const button = popup.querySelector('[data-watch-popup-toggle]');
		button.textContent = watched.has(popupSlug) ? 'Mark unwatched' : 'Mark watched';
	}

	function positionPopup(anchor) {
		const rect = anchor.getBoundingClientRect();
		const box = popup.getBoundingClientRect();
		const margin = 12;

		let left = rect.right + margin;
		if (left + box.width > window.innerWidth - margin) {
			left = rect.left - box.width - margin;
		}
		if (left < margin) {
			left = Math.max(margin, (window.innerWidth - box.width) / 2);
		}

		let top = rect.top;
		if (top + box.height > window.innerHeight - margin) {
			top = window.innerHeight - box.height - margin;
		}

		popup.style.left = `${Math.max(margin, left)}px`;
		popup.style.top = `${Math.max(margin, top)}px`;
	}

	function closePopup() {
		if (popup) {
			popup.hidden = true;
		}
		popupSlug = null;
	}

	// --------------------------------------------------------------- events

	chart.addEventListener('click', (event) => {
		const toggle = event.target.closest('[data-watch-toggle]');
		if (toggle) {
			const slug = toggle.closest('[data-watch-entry]').dataset.watchEntry;
			setWatched(slug, !watched.has(slug));
			return;
		}

		const opener = event.target.closest('[data-watch-open]');
		if (opener) {
			const tile = opener.closest('[data-watch-entry]');
			openPopup(tile.dataset.watchEntry, opener);
		}
	});

	document.querySelectorAll('[data-watch-track]').forEach((chip) => {
		chip.addEventListener('click', () => {
			const slug = chip.dataset.watchTrack;
			const nowHidden = !hiddenTracks.has(slug);
			if (nowHidden) {
				hiddenTracks.add(slug);
			} else {
				hiddenTracks.delete(slug);
			}
			chip.setAttribute('aria-pressed', String(!nowHidden));
			closePopup();
			layout();
		});
	});

	const collectionSelect = document.querySelector('[data-watch-collection]');
	if (collectionSelect) {
		const descriptions = new Map(
			(payload.collections || []).map((collection) => [collection.slug, collection.description])
		);
		const note = document.querySelector('[data-watch-collection-note]');

		collectionSelect.addEventListener('change', () => {
			activeCollection = collectionSelect.value;
			if (note) {
				note.textContent = descriptions.get(activeCollection) || '';
				note.hidden = !note.textContent;
			}
			closePopup();
			layout();
			paintProgress();
		});
	}

	const resetButton = document.querySelector('[data-watch-reset]');
	if (resetButton) {
		resetButton.addEventListener('click', () => {
			const previous = [...watched];
			watched.clear();
			paintWatched();
			if (authenticated) {
				previous.forEach((slug) => post(chart.dataset.watchedUrl, { slug, watched: false }));
			} else {
				persistLocally();
			}
		});
	}

	if (popup) {
		popup.querySelector('[data-watch-popup-close]').addEventListener('click', closePopup);
		popup.querySelector('[data-watch-popup-toggle]').addEventListener('click', () => {
			if (popupSlug) {
				setWatched(popupSlug, !watched.has(popupSlug));
			}
		});
		document.addEventListener('keydown', (event) => {
			if (event.key === 'Escape') {
				closePopup();
			}
		});
		document.addEventListener('click', (event) => {
			if (!popup.hidden && !popup.contains(event.target) && !event.target.closest('[data-watch-open]')) {
				closePopup();
			}
		});
	}

	// Geometry shifts on resize even though the row assignment does not.
	let frame = null;
	new ResizeObserver(() => {
		if (frame) {
			cancelAnimationFrame(frame);
		}
		frame = requestAnimationFrame(() => {
			frame = null;
			draw();
		});
	}).observe(canvas);

	// Late-loading posters change tile heights under the arrows.
	chart.querySelectorAll('.watch-tile img').forEach((image) => {
		if (!image.complete) {
			image.addEventListener('load', () => requestAnimationFrame(draw), { once: true });
			image.addEventListener('error', () => requestAnimationFrame(draw), { once: true });
		}
	});

	layout();
	paintWatched();
	if (authenticated) {
		syncLocalProgress();
	}
}

// -------------------------------------------------------------------- utils

/** Render an orthogonal polyline with rounded corners, dropping repeated points. */
function roundedPath(points, radius = 10) {
	const corners = points.filter(
		(point, index) =>
			index === 0 ||
			Math.abs(point.x - points[index - 1].x) > 0.5 ||
			Math.abs(point.y - points[index - 1].y) > 0.5
	);
	if (corners.length < 2) {
		return '';
	}

	const distance = (a, b) => Math.hypot(b.x - a.x, b.y - a.y);
	const towards = (origin, target, length) => {
		const span = distance(origin, target);
		const ratio = span === 0 ? 0 : length / span;
		return {
			x: origin.x + (target.x - origin.x) * ratio,
			y: origin.y + (target.y - origin.y) * ratio,
		};
	};

	let d = `M ${corners[0].x} ${corners[0].y}`;
	for (let index = 1; index < corners.length - 1; index += 1) {
		const previous = corners[index - 1];
		const corner = corners[index];
		const next = corners[index + 1];
		const cut = Math.min(radius, distance(previous, corner) / 2, distance(corner, next) / 2);
		const start = towards(corner, previous, cut);
		const end = towards(corner, next, cut);
		d += ` L ${start.x} ${start.y} Q ${corner.x} ${corner.y} ${end.x} ${end.y}`;
	}

	const last = corners[corners.length - 1];
	return `${d} L ${last.x} ${last.y}`;
}

function markerId(color) {
	return `watch-arrow-${color.replace(/[^a-zA-Z0-9]/g, '')}`;
}

function buildMarkers(svg, tracks) {
	const defs = document.createElementNS(SVG_NS, 'defs');
	const colors = [...new Set(tracks.map((track) => track.color))];

	colors.forEach((color) => {
		const marker = document.createElementNS(SVG_NS, 'marker');
		marker.setAttribute('id', markerId(color));
		marker.setAttribute('viewBox', '0 0 10 10');
		marker.setAttribute('refX', '9');
		marker.setAttribute('refY', '5');
		marker.setAttribute('markerWidth', '5');
		marker.setAttribute('markerHeight', '5');
		marker.setAttribute('orient', 'auto-start-reverse');

		const head = document.createElementNS(SVG_NS, 'path');
		head.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
		// Per-track markers rather than context-stroke, which Safari ignores.
		head.setAttribute('fill', color);
		marker.appendChild(head);
		defs.appendChild(marker);
	});

	svg.appendChild(defs);
}

function clearPaths(svg) {
	// Scoped to .watch-arrow so the arrowhead paths inside <defs> survive.
	svg.querySelectorAll('path.watch-arrow').forEach((path) => path.remove());
}

function getCookie(name) {
	const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`));
	return match ? decodeURIComponent(match[2]) : '';
}

function post(url, body) {
	return fetch(url, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'X-CSRFToken': getCookie('csrftoken'),
		},
		body: JSON.stringify(body),
	}).then((response) => {
		if (!response.ok) {
			throw new Error(`Request failed: ${response.status}`);
		}
		return response;
	});
}
