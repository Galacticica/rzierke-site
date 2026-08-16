/**
 * QR code generator.
 *
 * Everything happens in the browser: the canvas is rendered at download
 * resolution and scaled down for display via CSS, so the PNG the user saves is
 * the full-size one with no second render. Nothing is sent to the server.
 */

import QRCode from 'qrcode';

const CANVAS_SIZE = 1024;
const DISPLAY_SIZE = 320;
const DEBOUNCE_MS = 200;

const input = document.getElementById('qr-input');
const canvas = document.getElementById('qr-canvas');
const placeholder = document.getElementById('qr-placeholder');
const errorText = document.getElementById('qr-error');
const downloadButton = document.getElementById('qr-download');

let debounceTimer = null;
let renderToken = 0;

function showEmpty() {
	const ctx = canvas.getContext('2d');
	ctx.clearRect(0, 0, canvas.width, canvas.height);
	canvas.hidden = true;
	placeholder.hidden = false;
	errorText.textContent = '';
	downloadButton.disabled = true;
}

function showError(message) {
	canvas.hidden = true;
	placeholder.hidden = false;
	errorText.textContent = message;
	downloadButton.disabled = true;
}

async function render() {
	const value = input.value.trim();
	if (!value) {
		showEmpty();
		return;
	}

	// Renders are async, so a slow one must not overwrite a newer keystroke.
	const token = ++renderToken;
	try {
		await QRCode.toCanvas(canvas, value, {
			width: CANVAS_SIZE,
			margin: 2,
			errorCorrectionLevel: 'M',
		});
		if (token !== renderToken) return;
		// QRCode.toCanvas writes the full render size as an inline style, which
		// beats the stylesheet — scale the element down here so the canvas keeps
		// its download resolution while displaying at a sane size.
		canvas.style.width = DISPLAY_SIZE + 'px';
		canvas.style.height = 'auto';
		canvas.hidden = false;
		placeholder.hidden = true;
		errorText.textContent = '';
		downloadButton.disabled = false;
	} catch (err) {
		if (token !== renderToken) return;
		// Thrown when the text is too long to fit in any QR symbol version.
		showError(err.message || 'Could not generate a QR code for that value.');
	}
}

function download() {
	canvas.toBlob(function (blob) {
		if (!blob) return;
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = 'qrcode.png';
		link.click();
		URL.revokeObjectURL(url);
	}, 'image/png');
}

input.addEventListener('input', function () {
	clearTimeout(debounceTimer);
	debounceTimer = setTimeout(render, DEBOUNCE_MS);
});
downloadButton.addEventListener('click', download);

// Handle a value restored by the browser on reload.
render();
