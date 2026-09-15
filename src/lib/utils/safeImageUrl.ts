import { WEBUI_BASE_URL } from '$lib/constants';

// LICENSE covers this Open WebUI fallback logo.
// Do not alter, remove, obscure, or replace it except as LICENSE permits:
// https://docs.openwebui.com/license.
const PLACEHOLDER_IMAGE = '/favicon.png';

/**
 * Validates an image URL against an allowlist of safe patterns and returns
 * the URL if trusted, or a placeholder otherwise.
 *
 * Allowed patterns:
 *   - Relative paths (starting with '/')
 *   - base64 data URIs for a small raster-image allowlist
 *   - Same-origin URLs (starting with WEBUI_BASE_URL)
 *   - Gravatar URLs (https://www.gravatar.com/avatar/)
 *   - External HTTP(S) URLs when allowExternal is true
 *
 * All other URLs (including arbitrary http(s):// origins by default) are
 * rejected to prevent client-side IP/UA/Referer leaks to attacker-controlled servers.
 */
export function safeImageUrl(url: string, allowExternal = false): string {
	if (!url || url === '') {
		return `${WEBUI_BASE_URL}${PLACEHOLDER_IMAGE}`;
	}

	// Markdown image tokens are rendered as <img> components rather than through
	// DOMPurify. Keep data URIs useful for raster images without allowing HTML,
	// SVG, or other active content to enter an image source.
	const safeRasterDataUri =
		/^data:image\/(?:png|jpeg|gif|webp|avif|bmp|tiff);base64,[A-Za-z0-9+/]*={0,2}$/i;

	if (
		(WEBUI_BASE_URL && url.startsWith(WEBUI_BASE_URL)) ||
		url.startsWith('https://www.gravatar.com/avatar/') ||
		(allowExternal && /^https?:\/\//i.test(url)) ||
		safeRasterDataUri.test(url) ||
		(url.startsWith('/') && !url.startsWith('//'))
	) {
		return url;
	}

	return `${WEBUI_BASE_URL}${PLACEHOLDER_IMAGE}`;
}
