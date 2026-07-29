import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

import { viteStaticCopy } from 'vite-plugin-static-copy';

const devProxyTarget = process.env.OWUI_DEV_PROXY_TARGET?.trim();
const devHost = process.env.OWUI_DEV_HOST?.trim() || '127.0.0.1';
const devPort = Number.parseInt(process.env.OWUI_DEV_PORT || '5173', 10);
const devAllowedHosts = (process.env.OWUI_DEV_ALLOWED_HOSTS || 'localhost')
	.split(',')
	.map((host) => host.trim())
	.filter(Boolean);

export default defineConfig({
	plugins: [
		sveltekit(),
		viteStaticCopy({
			targets: [
				{
					src: 'node_modules/onnxruntime-web/dist/*.jsep.*',

					dest: 'wasm'
				}
			]
		})
	],
	define: {
		APP_VERSION: JSON.stringify(process.env.npm_package_version),
		APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
	},
	build: {
		sourcemap: true
	},
	server: devProxyTarget
		? {
				host: devHost,
				port: devPort,
				strictPort: true,
				allowedHosts: devAllowedHosts,
				proxy: {
					'/api': { target: devProxyTarget, changeOrigin: true, ws: true },
					'/openai': { target: devProxyTarget, changeOrigin: true, ws: true },
					'/ollama': { target: devProxyTarget, changeOrigin: true, ws: true },
					'/ws': { target: devProxyTarget, changeOrigin: true, ws: true },
					'/static': { target: devProxyTarget, changeOrigin: true },
					'/oauth': { target: devProxyTarget, changeOrigin: true },
					'/health': { target: devProxyTarget, changeOrigin: true },
					'/ready': { target: devProxyTarget, changeOrigin: true },
					'/cache': { target: devProxyTarget, changeOrigin: true },
					'/manifest.json': { target: devProxyTarget, changeOrigin: true },
					'/opensearch.xml': { target: devProxyTarget, changeOrigin: true }
				}
			}
		: undefined,
	worker: {
		format: 'es'
	},
	esbuild: {
		pure: process.env.ENV === 'dev' ? [] : ['console.log', 'console.debug', 'console.error']
	}
});
