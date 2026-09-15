import { loadPyodide, type PyodideInterface } from 'pyodide';

declare global {
	interface Window {
		stdout: string | null;
		stderr: string | null;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		result: any;
		pyodide: PyodideInterface;
		packages: string[];
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		[key: string]: any;
	}
}

// ---------------------------------------------------------------------------
// Pyodide bootstrap
// ---------------------------------------------------------------------------

let pyodideReady: Promise<void> | null = null;

async function loadPyodideAndPackages(packages: string[] = []) {
	self.stdout = null;
	self.stderr = null;
	self.result = null;

	self.pyodide = await loadPyodide({
		indexURL: '/pyodide/',
		stdout: (text) => {
			console.log('Python output:', text);

			if (self.stdout) {
				self.stdout += `${text}\n`;
			} else {
				self.stdout = `${text}\n`;
			}
		},
		stderr: (text) => {
			console.log('An error occurred:', text);
			if (self.stderr) {
				self.stderr += `${text}\n`;
			} else {
				self.stderr = `${text}\n`;
			}
		},
		packages: ['micropip']
	});

	// Create the upload directory and mount IDBFS for persistence
	const uploadDir = '/mnt/uploads';
	self.pyodide.FS.mkdirTree(uploadDir);
	self.pyodide.FS.mount(self.pyodide.FS.filesystems.IDBFS, {}, '/mnt');

	// Load persisted files from IndexedDB
	await new Promise<void>((resolve) => {
		(self.pyodide.FS as any).syncfs(true, (err: Error | null) => {
			if (err) {
				console.error('Error syncing from IndexedDB:', err);
			}
			// Always resolve — missing data is fine on first run
			resolve();
		});
	});

	// Ensure /mnt/uploads still exists after sync (first-time init)
	try {
		self.pyodide.FS.stat(uploadDir);
	} catch {
		self.pyodide.FS.mkdirTree(uploadDir);
	}

	const micropip = self.pyodide.pyimport('micropip');
	await micropip.install(packages);
}

/**
 * Ensure Pyodide is loaded. On the first call, loads and installs packages.
 * Subsequent calls reuse the already-loaded instance (persistent worker).
 */
async function ensurePyodide(packages: string[] = []) {
	if (!pyodideReady) {
		pyodideReady = loadPyodideAndPackages(packages);
	}
	await pyodideReady;

	// Install any additional packages not loaded on init
	if (packages.length > 0 && self.pyodide) {
		const micropip = self.pyodide.pyimport('micropip');
		await micropip.install(packages);
	}
}

/**
 * Persist the in-memory FS to IndexedDB (fire-and-forget with logging).
 */
function persistFS() {
	if (!self.pyodide) return;
	(self.pyodide.FS as any).syncfs(false, (err: Error | null) => {
		if (err) {
			console.error('Error syncing to IndexedDB:', err);
		} else {
			console.log('Successfully synced to IndexedDB.');
		}
	});
}

// ---------------------------------------------------------------------------
// FS operations
// ---------------------------------------------------------------------------

function fsUploadFiles(files: { name: string; data: ArrayBuffer }[], dir = '/mnt/uploads') {
	try {
		self.pyodide.FS.stat(dir);
	} catch {
		self.pyodide.FS.mkdirTree(dir);
	}

	for (const file of files) {
		self.pyodide.FS.writeFile(`${dir}/${file.name}`, new Uint8Array(file.data));
	}
}

type FsEntry = { name: string; type: 'file' | 'directory'; size: number; mtime: number };
type ImageOutput = { name: string; mimeType: string; data: ArrayBuffer };

const IMAGE_MIME_TYPES: Record<string, string> = {
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

function imageMimeType(name: string): string | null {
	const extension = name.slice(name.lastIndexOf('.')).toLowerCase();
	return IMAGE_MIME_TYPES[extension] ?? null;
}

function fsList(path: string): FsEntry[] {
	const entries: FsEntry[] = [];
	try {
		const items = self.pyodide.FS.readdir(path).filter((n: string) => n !== '.' && n !== '..');
		for (const name of items) {
			try {
				const stat = self.pyodide.FS.stat(`${path}/${name}`);
				const isDir = self.pyodide.FS.isDir(stat.mode);
				entries.push({
					name,
					type: isDir ? 'directory' : 'file',
					size: isDir ? 0 : stat.size,
					mtime: isDir ? 0 : Number((stat as any).mtimeMs ?? (stat as any).mtime ?? 0)
				});
			} catch {
				// skip inaccessible entries
			}
		}
	} catch {
		// directory doesn't exist
	}
	return entries;
}

function fsRead(path: string): ArrayBuffer {
	const data: Uint8Array = (self.pyodide.FS as any).readFile(path) as Uint8Array;
	return data.slice().buffer as ArrayBuffer;
}

function snapshotImageFiles(path = '/mnt/uploads') {
	return new Map(
		fsList(path)
			.filter((entry) => entry.type === 'file' && imageMimeType(entry.name))
			.map((entry) => [entry.name, `${entry.size}:${entry.mtime}`])
	);
}

function collectImageOutputs(before: Map<string, string>, path = '/mnt/uploads'): ImageOutput[] {
	const outputs: ImageOutput[] = [];
	for (const entry of fsList(path)) {
		const mimeType = imageMimeType(entry.name);
		const signature = `${entry.size}:${entry.mtime}`;
		if (entry.type !== 'file' || !mimeType || before.get(entry.name) === signature) continue;

		try {
			outputs.push({ name: entry.name, mimeType, data: fsRead(`${path}/${entry.name}`) });
		} catch (error) {
			console.warn(`Unable to read generated image ${entry.name}:`, error);
		}
	}
	return outputs;
}

function fsDelete(path: string) {
	try {
		const stat = self.pyodide.FS.stat(path);
		if (self.pyodide.FS.isDir(stat.mode)) {
			// Recursively delete directory contents
			const items = self.pyodide.FS.readdir(path).filter((n: string) => n !== '.' && n !== '..');
			for (const item of items) {
				fsDelete(`${path}/${item}`);
			}
			self.pyodide.FS.rmdir(path);
		} else {
			self.pyodide.FS.unlink(path);
		}
	} catch {
		// already gone
	}
}

function fsMkdir(path: string) {
	self.pyodide.FS.mkdirTree(path);
}

// ---------------------------------------------------------------------------
// Code execution
// ---------------------------------------------------------------------------

async function executeCode(
	id: string,
	code: string,
	files?: { name: string; data: ArrayBuffer }[]
) {
	self.stdout = null;
	self.stderr = null;
	self.result = null;

	// Upload any accompanying files before execution
	if (files && files.length > 0) {
		fsUploadFiles(files);
		persistFS();
	}
	const beforeImages = snapshotImageFiles();

	try {
		// check if matplotlib is imported in the code
		if (code.includes('matplotlib')) {
			// Override plt.show() to write a file. The browser uploads the bytes over
			// HTTP after execution, so a large base64 string never crosses Socket.IO.
			await self.pyodide.runPythonAsync(`import os
import uuid

# before importing matplotlib
# to avoid the wasm backend (which needs js.document', not available in worker)
os.environ["MPLBACKEND"] = "AGG"

import matplotlib.pyplot

_old_show = matplotlib.pyplot.show
assert _old_show, "matplotlib.pyplot.show"

def show(*, block=None):
	output_path = f"/mnt/uploads/pyodide-matplotlib-{uuid.uuid4().hex}.png"
	matplotlib.pyplot.savefig(output_path, format="png")
	matplotlib.pyplot.clf()
	print("[Open WebUI image generated]")

matplotlib.pyplot.show = show`);
		}

		self.result = await self.pyodide.runPythonAsync(code);

		// Safely process and recursively serialize the result
		self.result = processResult(self.result);

		console.log('Python result:', self.result);

		// Persist any files the code may have written
		persistFS();
	} catch (error: unknown) {
		self.stderr = error instanceof Error ? error.message : String(error);
	}

	const images = collectImageOutputs(beforeImages);
	persistFS();
	const transfer = images.map((image) => image.data);
	self.postMessage({ id, result: self.result, stdout: self.stdout, stderr: self.stderr, images }, { transfer });
}

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------

self.onmessage = async (event) => {
	const data = event.data;
	const { id, type } = data;

	// Backward compatibility: messages without a `type` field are execute requests
	if (!type || type === 'execute') {
		const { code, files, ...context } = data;

		// Copy context keys (packages, etc.) into worker scope
		for (const key of Object.keys(context)) {
			if (key !== 'id' && key !== 'type') {
				self[key] = context[key];
			}
		}

		await ensurePyodide(self.packages);
		await executeCode(id, code, files);
		return;
	}

	// FS operations require Pyodide to be loaded
	await ensurePyodide();

	switch (type) {
		case 'fs:upload': {
			const { files, dir } = data;
			fsUploadFiles(files, dir);
			persistFS();
			self.postMessage({ id, type: 'fs:upload', success: true });
			break;
		}

		case 'fs:list': {
			const entries = fsList(data.path);
			self.postMessage({ id, type: 'fs:list', entries });
			break;
		}

		case 'fs:read': {
			try {
				const buffer = fsRead(data.path);
				self.postMessage({ id, type: 'fs:read', data: buffer }, { transfer: [buffer] });
			} catch (err: unknown) {
				self.postMessage({
					id,
					type: 'fs:read',
					error: err instanceof Error ? err.message : String(err)
				});
			}
			break;
		}

		case 'fs:delete': {
			fsDelete(data.path);
			persistFS();
			self.postMessage({ id, type: 'fs:delete', success: true });
			break;
		}

		case 'fs:mkdir': {
			fsMkdir(data.path);
			persistFS();
			self.postMessage({ id, type: 'fs:mkdir', success: true });
			break;
		}

		case 'fs:sync': {
			// Re-read from IndexedDB into memory to pick up externally written files
			(self.pyodide.FS as any).syncfs(true, (err: Error | null) => {
				if (err) {
					console.error('Error syncing from IndexedDB:', err);
				}
				self.postMessage({ id, type: 'fs:sync', success: !err });
			});
			break;
		}

		default:
			console.warn('Unknown message type:', type);
	}
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function processResult(result: any): any {
	// Catch and always return JSON-safe string representations
	try {
		if (result == null) {
			// Handle null and undefined
			return null;
		}
		if (typeof result === 'string' || typeof result === 'number' || typeof result === 'boolean') {
			// Handle primitive types directly
			return result;
		}
		if (typeof result === 'bigint') {
			// Convert BigInt to a string for JSON-safe representation
			return result.toString();
		}
		if (Array.isArray(result)) {
			// If it's an array, recursively process items
			return result.map((item) => processResult(item));
		}
		if (typeof result.toJs === 'function') {
			// If it's a Pyodide proxy object (e.g., Pandas DF, Numpy Array), convert to JS and process recursively
			return processResult(result.toJs());
		}
		if (typeof result === 'object') {
			// Convert JS objects to a recursively serialized representation
			const processedObject: { [key: string]: any } = {};
			for (const key in result) {
				if (Object.prototype.hasOwnProperty.call(result, key)) {
					processedObject[key] = processResult(result[key]);
				}
			}
			return processedObject;
		}
		// Stringify anything that's left (e.g., Proxy objects that cannot be directly processed)
		return JSON.stringify(result);
	} catch (err: unknown) {
		// In case something unexpected happens, we return a stringified fallback
		return `[processResult error]: ${err instanceof Error ? err.message : String(err)}`;
	}
}

export default {};
