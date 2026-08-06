/**
 * Seed the watch entry's "Movie" autocomplete with whatever is in Title.
 *
 * The link to the character graph is set by hand on purpose - nothing fills it
 * in on save - so the job here is just to save the retyping. Opening the picker
 * runs a search for the title already on the form, putting the matching film at
 * the top of the list; clearing the box browses everything as normal.
 */
(function () {
	'use strict';

	// Mirrors connections/title_parsing.py: a season or episode suffix is part of
	// the watch-order tile's name, never part of the film's name.
	const SUFFIX = /\s*[-–—:,]?\s*(?:(?:season|\bs)\s*\d+|(?:episodes?|eps?)\s*\d+(?:\s*(?:[-–—]|to)\s*\d+)?|\be\d+(?:\s*[-–—]\s*\d+)?)\s*$/gi;

	function searchTerm() {
		const title = document.getElementById('id_title');
		if (!title || !title.value.trim()) {
			return '';
		}
		let term = title.value.trim();
		// Strip repeatedly: "Daredevil Season 1 Ep 1-7" sheds both suffixes.
		let previous;
		do {
			previous = term;
			SUFFIX.lastIndex = 0;
			term = term.replace(SUFFIX, '').trim();
		} while (term !== previous && term);
		return term;
	}

	function onOpen($) {
		const term = searchTerm();
		if (!term) {
			return;
		}

		// The dropdown's search box is created as it opens, so wait a tick.
		window.setTimeout(function () {
			const field = document.querySelector(
				'.select2-container--open .select2-search__field'
			);
			if (!field || field.value) {
				return;
			}
			field.value = term;
			// Select2 listens on different events across versions; fire both.
			$(field).trigger('input').trigger('keyup');
		}, 0);
	}

	// Admin media can load this before django.jQuery exists, so registration
	// waits for the DOM rather than bailing out at parse time.
	function init() {
		if (typeof django === 'undefined' || !django.jQuery) {
			return;
		}
		const $ = django.jQuery;
		$(document).on('select2:open', 'select[name="movie"]', function () {
			onOpen($);
		});
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	} else {
		init();
	}
})();
