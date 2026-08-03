import { afterEach, describe, expect, it, vi } from 'vitest';

import { openRouterImageGenerations } from './index';

describe('direct OpenRouter image generation', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('calls the dedicated OWUI image route without a chat model payload', async () => {
		const response = {
			model: 'google/gemini-3.1-flash-image',
			images: [{ type: 'image', url: '/api/v1/files/file-1/content' }],
			usage: { cost: 0.01 }
		};
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => response
		});
		vi.stubGlobal('fetch', fetchMock);

		await expect(
			openRouterImageGenerations('token', {
				model: 'google/gemini-3.1-flash-image',
				prompt: 'A blue circle'
			})
		).resolves.toEqual(response);

		expect(fetchMock).toHaveBeenCalledOnce();
		const [url, options] = fetchMock.mock.calls[0];
		expect(url).toMatch(/\/api\/v1\/images\/openrouter\/generations$/);
		expect(JSON.parse(options.body)).toEqual({
			model: 'google/gemini-3.1-flash-image',
			prompt: 'A blue circle',
			n: 1
		});
		expect(JSON.parse(options.body)).not.toHaveProperty('messages');
	});
});
