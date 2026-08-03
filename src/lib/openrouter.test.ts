import { describe, expect, it } from 'vitest';

import {
	DEFAULT_OPENROUTER_IMAGE_MODEL,
	getOpenRouterImageModel,
	getOpenRouterSessionId,
	getOpenRouterSessionUrl,
	OPENROUTER_IMAGE_MODELS,
	selectedModelsSupportWebSearch
} from './openrouter';

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

describe('OpenRouter image models', () => {
	it('has a curated unique catalog and a balanced default', () => {
		const ids = OPENROUTER_IMAGE_MODELS.map((model) => model.id);
		expect(new Set(ids).size).toBe(ids.length);
		expect(ids).toContain(DEFAULT_OPENROUTER_IMAGE_MODEL);
		expect(getOpenRouterImageModel(DEFAULT_OPENROUTER_IMAGE_MODEL).shortLabel).toBe('NB2');
	});

	it('falls back safely when a draft contains a removed model', () => {
		expect(getOpenRouterImageModel('removed/model').id).toBe(DEFAULT_OPENROUTER_IMAGE_MODEL);
	});
});

describe('model web-search capability', () => {
	const models = [
		{ id: 'or.gemini3.6f', info: { meta: { capabilities: { web_search: false } } } },
		{ id: 'or.grok45', info: { meta: { capabilities: { web_search: true } } } }
	] as never[];

	it('hides search when any selected model explicitly opts out', () => {
		expect(selectedModelsSupportWebSearch(models, ['or.gemini3.6f'])).toBe(false);
		expect(selectedModelsSupportWebSearch(models, ['or.grok45'])).toBe(true);
		expect(selectedModelsSupportWebSearch(models, ['or.grok45', 'or.gemini3.6f'])).toBe(false);
	});
});
