import './app.css';

if (document.getElementById('mcu-graph')) {
	import('./graph');
}

if (document.getElementById('watch-order-chart')) {
	import('./watch-order');
}

if (document.getElementById('qr-canvas')) {
	import('./qr');
}
