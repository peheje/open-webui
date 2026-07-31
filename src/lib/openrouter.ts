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
