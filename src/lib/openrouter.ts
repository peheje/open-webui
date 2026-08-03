import type { Model } from '$lib/stores';
import sha256 from 'js-sha256';

export const LOCAL_SEARCH_ENGINES = ['brave', 'serper'] as const;
export const OPENROUTER_SEARCH_ENGINES = [
	'auto',
	'native',
	'exa',
	'parallel',
	'perplexity',
	'firecrawl'
] as const;

export type LocalSearchEngine = (typeof LOCAL_SEARCH_ENGINES)[number];
export type OpenRouterSearchEngine = (typeof OPENROUTER_SEARCH_ENGINES)[number];
export type WebSearchEngine = LocalSearchEngine | OpenRouterSearchEngine;
export type OpenRouterCacheMode = 'smart' | 'long' | 'provider_default';
export type OpenRouterSearchContextSize = 'low' | 'medium' | 'high';

export const OPENROUTER_IMAGE_MODELS = [
	{
		id: 'google/gemini-3.1-flash-lite-image',
		label: 'Nano Banana 2 Lite',
		shortLabel: 'NB2 Lite',
		icon: '/static/model-icons/gemini.png',
		description: 'Fastest and cheapest option for drafts and everyday images.'
	},
	{
		id: 'google/gemini-3.1-flash-image',
		label: 'Nano Banana 2',
		shortLabel: 'NB2',
		icon: '/static/model-icons/gemini.png',
		description: 'Balanced default with strong prompt following and image quality.'
	},
	{
		id: 'google/gemini-3-pro-image',
		label: 'Nano Banana Pro',
		shortLabel: 'NB Pro',
		icon: '/static/model-icons/gemini.png',
		description: 'Premium Google model for complex compositions, design, and text.'
	},
	{
		id: 'openai/gpt-image-2',
		label: 'GPT Image 2',
		shortLabel: 'GPT Image 2',
		icon: '/static/favicon.png',
		description: 'Strong general generation and precise image editing.'
	},
	{
		id: 'x-ai/grok-imagine-image-quality',
		label: 'Grok Imagine Quality',
		shortLabel: 'Grok Imagine',
		icon: '/static/favicon.png',
		description: 'High-quality xAI image generation with a distinctive visual style.'
	},
	{
		id: 'bytedance-seed/seedream-4.5',
		label: 'Seedream 4.5',
		shortLabel: 'Seedream',
		icon: '/static/favicon.png',
		description: 'Good-value aesthetic generation with high-resolution output.'
	},
	{
		id: 'black-forest-labs/flux.2-max',
		label: 'FLUX.2 Max',
		shortLabel: 'FLUX Max',
		icon: '/static/favicon.png',
		description: 'Premium FLUX model for realism and polished final images.'
	}
] as const;

export type OpenRouterImageModel = (typeof OPENROUTER_IMAGE_MODELS)[number]['id'];
export const DEFAULT_OPENROUTER_IMAGE_MODEL: OpenRouterImageModel = 'google/gemini-3.1-flash-image';

export const getOpenRouterImageModel = (model: string) =>
	OPENROUTER_IMAGE_MODELS.find((item) => item.id === model) ??
	OPENROUTER_IMAGE_MODELS.find((item) => item.id === DEFAULT_OPENROUTER_IMAGE_MODEL)!;

export type OpenRouterControl = {
	official_provider: string;
	web_search?: boolean;
	cache_mode?: OpenRouterCacheMode;
};

export const getOpenRouterControlForModels = (
	models: Model[],
	selectedModelIds: string[]
): OpenRouterControl | null => {
	if (selectedModelIds.length !== 1) return null;
	const model = models.find((item) => item.id === selectedModelIds[0]);
	return model?.info?.meta?.openrouter ?? null;
};

export const isOpenRouterSearchEngine = (
	engine: WebSearchEngine
): engine is OpenRouterSearchEngine =>
	OPENROUTER_SEARCH_ENGINES.includes(engine as OpenRouterSearchEngine);

export const isLocalSearchEngine = (engine: WebSearchEngine): engine is LocalSearchEngine =>
	LOCAL_SEARCH_ENGINES.includes(engine as LocalSearchEngine);

export const OPENROUTER_SESSIONS_URL = 'https://openrouter.ai/logs?tab=sessions';

export const getOpenRouterSessionId = async (chatId: string): Promise<string | null> => {
	if (!chatId) return null;
	return `owui-${sha256(chatId).slice(0, 40)}`;
};

export const getOpenRouterSessionUrl = async (chatId: string): Promise<string | null> => {
	const sessionId = await getOpenRouterSessionId(chatId);
	return sessionId
		? `${OPENROUTER_SESSIONS_URL}&session_id=${encodeURIComponent(sessionId)}`
		: null;
};
