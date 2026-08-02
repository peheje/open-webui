import { describe, expect, it } from 'vitest';

import { getOpenRouterSessionId, getOpenRouterSessionUrl } from './openrouter';

describe('OpenRouter session links', () => {
	it('matches the backend session ID without requiring Web Crypto', async () => {
		const chatId = 'a3d4cc3e-e73e-425a-ba4a-6edfd1e9b6a0';
		const sessionId = 'owui-2bb4bf89dd5f8552efccf3cbb27d5bb2c0e2b704';

		await expect(getOpenRouterSessionId(chatId)).resolves.toBe(sessionId);
		await expect(getOpenRouterSessionUrl(chatId)).resolves.toBe(
			`https://openrouter.ai/logs?tab=sessions&session_id=${sessionId}`
		);
	});

	it('does not create a link without a chat ID', async () => {
		await expect(getOpenRouterSessionId('')).resolves.toBeNull();
		await expect(getOpenRouterSessionUrl('')).resolves.toBeNull();
	});
});
