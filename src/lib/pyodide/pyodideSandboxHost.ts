type MessageListener = (event: MessageEvent) => void;
type ErrorListener = (event: Event) => void;
type QueuedMessage = { message: unknown; transfer: Transferable[] };

const sandboxScript = String.raw`
(function () {
	let pyodide = null;
	let pyodideReady = null;
	let stdout = null;
	let stderr = null;

	function post(message, transfer) {
		parent.postMessage(message, '*', transfer || []);
	}

	async function loadRuntime(packages) {
		stdout = null;
		stderr = null;
		pyodide = await loadPyodide({
			indexURL: self.__PYODIDE_INDEX_URL__ || '/pyodide/',
			stdout: function (text) {
				stdout = stdout ? stdout + text + '\n' : text + '\n';
			},
			stderr: function (text) {
				stderr = stderr ? stderr + text + '\n' : text + '\n';
			},
			packages: ['micropip']
		});
		pyodide.FS.mkdirTree('/mnt/uploads');
		await pyodide.pyimport('micropip').install(packages || []);
	}

	async function ensureRuntime(packages) {
		if (!pyodideReady) pyodideReady = loadRuntime(packages || []);
		await pyodideReady;
		if (packages && packages.length > 0) {
			await pyodide.pyimport('micropip').install(packages);
		}
	}

	function ensureDir(dir) {
		try {
			pyodide.FS.stat(dir);
		} catch {
			pyodide.FS.mkdirTree(dir);
		}
	}

	function upload(files, dir) {
		dir = dir || '/mnt/uploads';
		ensureDir(dir);
		for (const file of files || []) {
			pyodide.FS.writeFile(dir + '/' + file.name, new Uint8Array(file.data));
		}
	}

	function list(path) {
		const entries = [];
		try {
			const names = pyodide.FS.readdir(path).filter(function (name) {
				return name !== '.' && name !== '..';
			});
			for (const name of names) {
				try {
					const stat = pyodide.FS.stat(path + '/' + name);
					const isDir = pyodide.FS.isDir(stat.mode);
					entries.push({
						name: name,
						type: isDir ? 'directory' : 'file',
						size: isDir ? 0 : stat.size,
						mtime: isDir ? 0 : Number(stat.mtimeMs || stat.mtime || 0)
					});
				} catch {}
			}
		} catch {}
		return entries;
	}

	const imageMimeTypes = {
		'.png': 'image/png',
		'.jpg': 'image/jpeg',
		'.jpeg': 'image/jpeg',
		'.gif': 'image/gif',
		'.webp': 'image/webp',
		'.avif': 'image/avif',
		'.bmp': 'image/bmp',
		'.tif': 'image/tiff',
		'.tiff': 'image/tiff'
	};

	function imageMimeType(name) {
		const dot = name.lastIndexOf('.');
		return imageMimeTypes[dot >= 0 ? name.slice(dot).toLowerCase() : ''] || null;
	}

	function snapshotImageFiles(path) {
		const snapshot = new Map();
		for (const entry of list(path || '/mnt/uploads')) {
			if (entry.type === 'file' && imageMimeType(entry.name)) {
				snapshot.set(entry.name, entry.size + ':' + entry.mtime);
			}
		}
		return snapshot;
	}

	function collectImageOutputs(before, path) {
		const outputs = [];
		path = path || '/mnt/uploads';
		for (const entry of list(path)) {
			const mimeType = imageMimeType(entry.name);
			const signature = entry.size + ':' + entry.mtime;
			if (entry.type !== 'file' || !mimeType || before.get(entry.name) === signature) continue;

			try {
				const bytes = pyodide.FS.readFile(path + '/' + entry.name).slice();
				outputs.push({ name: entry.name, mimeType: mimeType, data: bytes.buffer });
			} catch (error) {
				console.warn('Unable to read generated image ' + entry.name + ':', error);
			}
		}
		return outputs;
	}

	function remove(path) {
		try {
			const stat = pyodide.FS.stat(path);
			if (!pyodide.FS.isDir(stat.mode)) {
				pyodide.FS.unlink(path);
				return;
			}
			const names = pyodide.FS.readdir(path).filter(function (name) {
				return name !== '.' && name !== '..';
			});
			for (const name of names) remove(path + '/' + name);
			pyodide.FS.rmdir(path);
		} catch {}
	}

	function clean(value) {
		try {
			if (value == null) return null;
			if (['string', 'number', 'boolean'].includes(typeof value)) return value;
			if (typeof value === 'bigint') return value.toString();
			if (Array.isArray(value)) return value.map(clean);
			if (typeof value.toJs === 'function') return clean(value.toJs());
			if (typeof value === 'object') {
				const out = {};
				for (const key in value) {
					if (Object.prototype.hasOwnProperty.call(value, key)) out[key] = clean(value[key]);
				}
				return out;
			}
			return JSON.stringify(value);
		} catch (error) {
			return '[processResult error]: ' + (error && error.message ? error.message : String(error));
		}
	}

	async function patchMatplotlib() {
		await pyodide.runPythonAsync([
			'import os',
			'import uuid',
			'os.environ["MPLBACKEND"] = "AGG"',
			'import matplotlib.pyplot',
			'_old_show = matplotlib.pyplot.show',
			'assert _old_show, "matplotlib.pyplot.show"',
			'def show(*, block=None):',
			// String.raw keeps \t as-is; the sandbox's JS parser turns it into a real tab
			'\toutput_path = f"/mnt/uploads/pyodide-matplotlib-{uuid.uuid4().hex}.png"',
			'\tmatplotlib.pyplot.savefig(output_path, format="png")',
			'\tmatplotlib.pyplot.clf()',
			'\tprint("[Open WebUI image generated]")',
			'matplotlib.pyplot.show = show'
		].join('\n'));
	}

	async function execute(id, code, files) {
		stdout = null;
		stderr = null;
		let result = null;
		if (files && files.length > 0) upload(files);
		const beforeImages = snapshotImageFiles('/mnt/uploads');
		try {
			if (code.includes('matplotlib')) await patchMatplotlib();
			result = clean(await pyodide.runPythonAsync(code));
		} catch (error) {
			stderr = error && error.message ? error.message : String(error);
		}
		const images = collectImageOutputs(beforeImages, '/mnt/uploads');
		const transfer = images.map(function (image) { return image.data; });
		post({ id: id, result: result, stdout: stdout, stderr: stderr, images: images }, transfer);
	}

	window.addEventListener('message', async function (event) {
		if (event.source !== parent) return;
		const data = event.data || {};
		const id = data.id;
		try {
			if (!data.type || data.type === 'execute') {
				await ensureRuntime(data.packages || []);
				await execute(id, data.code, data.files);
				return;
			}
			await ensureRuntime();
			switch (data.type) {
				case 'fs:upload':
					upload(data.files, data.dir);
					post({ id: id, type: data.type, success: true });
					break;
				case 'fs:list':
					post({ id: id, type: data.type, entries: list(data.path) });
					break;
				case 'fs:read':
					try {
						const buffer = pyodide.FS.readFile(data.path).slice().buffer;
						post({ id: id, type: data.type, data: buffer }, [buffer]);
					} catch (error) {
						post({ id: id, type: data.type, error: error && error.message ? error.message : String(error) });
					}
					break;
				case 'fs:delete':
					remove(data.path);
					post({ id: id, type: data.type, success: true });
					break;
				case 'fs:mkdir':
					pyodide.FS.mkdirTree(data.path);
					post({ id: id, type: data.type, success: true });
					break;
				case 'fs:sync':
					post({ id: id, type: data.type, success: true });
					break;
			}
		} catch (error) {
			post({ id: id, stderr: error && error.message ? error.message : String(error) });
		}
	});
})();
`;

// indexURL must be absolute because about:srcdoc can't be a base URL
const pyodideIndexURL = `${globalThis.location?.origin ?? ''}/pyodide/`;

const sandboxHtml = `<!doctype html><html><head><meta charset="utf-8"><script>window.__PYODIDE_INDEX_URL__=${JSON.stringify(pyodideIndexURL)}</script></head><body><script src="${pyodideIndexURL}pyodide.js"></script><script>${sandboxScript}</script></body></html>`;

export class PyodideSandboxHost {
	onmessage: MessageListener | null = null;
	onerror: ErrorListener | null = null;

	private iframe: HTMLIFrameElement;
	private ready = false;
	private queue: QueuedMessage[] = [];
	private messageListeners = new Set<MessageListener>();
	private errorListeners = new Set<ErrorListener>();
	private onWindowMessage: (event: MessageEvent) => void;
	private onIframeLoad: () => void;
	private onIframeError: (event: Event) => void;

	constructor() {
		this.iframe = document.createElement('iframe');
		this.iframe.setAttribute('sandbox', 'allow-scripts');
		this.iframe.setAttribute('aria-hidden', 'true');
		this.iframe.setAttribute('title', 'pyodide-sandbox');
		this.iframe.style.display = 'none';
		this.iframe.srcdoc = sandboxHtml;

		this.onWindowMessage = (event: MessageEvent) => {
			if (event.source !== this.iframe.contentWindow) {
				return;
			}

			const messageEvent = { data: event.data } as MessageEvent;
			this.onmessage?.(messageEvent);
			for (const listener of this.messageListeners) {
				listener(messageEvent);
			}
		};

		this.onIframeLoad = () => {
			this.ready = true;
			for (const item of this.queue) {
				this.post(item.message, item.transfer);
			}
			this.queue = [];
		};

		this.onIframeError = (event: Event) => {
			this.onerror?.(event);
			for (const listener of this.errorListeners) {
				listener(event);
			}
		};

		window.addEventListener('message', this.onWindowMessage);
		this.iframe.addEventListener('load', this.onIframeLoad, { once: true });
		this.iframe.addEventListener('error', this.onIframeError);
		document.body.appendChild(this.iframe);
	}

	postMessage(message: unknown, transfer: Transferable[] = []) {
		if (this.ready) {
			this.post(message, transfer);
		} else {
			this.queue.push({ message, transfer });
		}
	}

	addEventListener(type: 'message' | 'error', listener: MessageListener | ErrorListener) {
		if (type === 'message') {
			this.messageListeners.add(listener as MessageListener);
		} else if (type === 'error') {
			this.errorListeners.add(listener as ErrorListener);
		}
	}

	removeEventListener(type: 'message' | 'error', listener: MessageListener | ErrorListener) {
		if (type === 'message') {
			this.messageListeners.delete(listener as MessageListener);
		} else if (type === 'error') {
			this.errorListeners.delete(listener as ErrorListener);
		}
	}

	terminate() {
		window.removeEventListener('message', this.onWindowMessage);
		this.iframe.removeEventListener('load', this.onIframeLoad);
		this.iframe.removeEventListener('error', this.onIframeError);
		this.messageListeners.clear();
		this.errorListeners.clear();
		this.onmessage = null;
		this.onerror = null;
		this.iframe.remove();
	}

	private post(message: unknown, transfer: Transferable[]) {
		this.iframe.contentWindow?.postMessage(message, '*', transfer);
	}
}
