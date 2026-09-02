<script lang="ts">
	import { getContext, onDestroy, tick } from 'svelte';
	import { fly } from 'svelte/transition';

	import { user, tools as _tools, skills as _skills, toolServers } from '$lib/stores';

	import { deleteOAuthSession } from '$lib/apis/auths';
	import { getTools } from '$lib/apis/tools';
	import { getSkills } from '$lib/apis/skills';

	import { toast } from 'svelte-sonner';

	import Knobs from '$lib/components/icons/Knobs.svelte';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import DropdownMenu from '$lib/components/common/DropdownMenu.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import SearchInput from './InputMenu/SearchInput.svelte';
	import Wrench from '$lib/components/icons/Wrench.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Photo from '$lib/components/icons/Photo.svelte';
	import Terminal from '$lib/components/icons/Terminal.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import LinkSlash from '$lib/components/icons/LinkSlash.svelte';
	import LightBulb from '$lib/components/icons/LightBulb.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import Voice from '$lib/components/icons/Voice.svelte';
	import { REASONING_LEVEL_IDS, type ReasoningControl, type ReasoningLevel } from '$lib/reasoning';
	import {
		LOCAL_SEARCH_ENGINES,
		OPENROUTER_IMAGE_MODELS,
		OPENROUTER_ROUTING_MODES,
		OPENROUTER_SEARCH_ENGINES,
		getOpenRouterImageModel,
		getOpenRouterRoutingMode,
		type OpenRouterCacheMode,
		type OpenRouterControl,
		type OpenRouterImageModel,
		type OpenRouterSearchContextSize,
		type OpenRouterRoutingMode,
		type WebSearchEngine
	} from '$lib/openrouter';

	const i18n = getContext('i18n') as any;

	type IntegrationItem = {
		id: string;
		name: string;
		description?: string;
		meta?: { description?: string };
		is_active?: boolean;
		authenticated?: boolean;
		has_user_valves?: boolean;
		[key: string]: any;
	};

	export let selectedToolIds: string[] = [];
	export let selectedSkillIds: string[] = [];

	export let selectedModels: string[] = [];
	export let fileUploadCapableModels: string[] = [];
	export let oauthRedirectHandler: Function = () => {};

	export let toggleFilters: {
		id: string;
		name: string;
		description?: string;
		icon?: string;
		has_user_valves?: boolean;
	}[] = [];
	export let selectedFilterIds: string[] = [];

	export let showWebSearchButton = false;
	export let webSearchEnabled = false;
	export let webSearchEngine: WebSearchEngine = 'brave';
	export let webSearchMaxUses = 3;
	export let webSearchMaxResults = 5;
	export let webSearchMaxTotalResults = 12;
	export let webSearchContextSize: OpenRouterSearchContextSize = 'medium';
	export let openRouterCacheMode: OpenRouterCacheMode = 'smart';
	export let openRouterRoutingMode: OpenRouterRoutingMode = 'official';
	export let openRouterImageModel: OpenRouterImageModel = 'google/gemini-3.1-flash-image';
	export let openRouterImageAvailable = false;
	export let openRouterControl: OpenRouterControl | null = null;
	export let reasoningControl: ReasoningControl | null = null;
	export let reasoningLevel: ReasoningLevel | null = null;
	export let showImageGenerationButton = false;
	export let imageGenerationEnabled = false;
	export let showCodeInterpreterButton = false;
	export let codeInterpreterEnabled = false;
	export let showVoiceModeButton = false;

	export let onShowValves: Function;
	export let onClose: Function;
	export let onWebSearchToggle: Function = () => {};
	export let onReasoningLevelChange: (level: ReasoningLevel) => void = () => {};
	export let onOpenRouterRoutingModeChange: (mode: OpenRouterRoutingMode) => void = () => {};
	export let onVoiceMode: () => void = () => {};
	export let closeOnOutsideClick = true;

	type OpenRouterSearchDepth = 'quick' | 'balanced' | 'deep';
	const OPENROUTER_SEARCH_DEPTHS: {
		id: OpenRouterSearchDepth;
		label: string;
		maxUses: number;
		maxResults: number;
		maxTotalResults: number;
		context: OpenRouterSearchContextSize;
		description: string;
	}[] = [
		{
			id: 'quick',
			label: 'Quick',
			maxUses: 1,
			maxResults: 3,
			maxTotalResults: 3,
			context: 'low',
			description: 'One focused search with up to 3 sources.'
		},
		{
			id: 'balanced',
			label: 'Balanced',
			maxUses: 3,
			maxResults: 5,
			maxTotalResults: 12,
			context: 'medium',
			description: 'Up to 3 searches and 12 sources for normal questions.'
		},
		{
			id: 'deep',
			label: 'Deep',
			maxUses: 5,
			maxResults: 8,
			maxTotalResults: 30,
			context: 'high',
			description: 'Up to 5 searches and 30 sources for research.'
		}
	];
	let webSearchDepth: OpenRouterSearchDepth = 'balanced';
	$: webSearchDepth =
		webSearchMaxUses <= 1 && webSearchMaxTotalResults <= 3 && webSearchContextSize === 'low'
			? 'quick'
			: webSearchMaxUses >= 5 || webSearchMaxTotalResults >= 25 || webSearchContextSize === 'high'
				? 'deep'
				: 'balanced';

	const applyWebSearchDepth = (depth: OpenRouterSearchDepth) => {
		const preset = OPENROUTER_SEARCH_DEPTHS.find((item) => item.id === depth);
		if (!preset) return;
		webSearchMaxUses = preset.maxUses;
		webSearchMaxResults = preset.maxResults;
		webSearchMaxTotalResults = preset.maxTotalResults;
		webSearchContextSize = preset.context;
	};

	let show = false;
	let tab = '';

	export function openTab(target: 'reasoning' | 'routing' | 'web-search' | 'image-generation') {
		if (target === 'reasoning' && !reasoningControl) return;
		if (target === 'routing' && !openRouterControl) return;
		if (target === 'web-search' && !showWebSearchButton) return;
		if (target === 'image-generation' && (!showImageGenerationButton || !openRouterImageAvailable))
			return;
		tab = target;
		show = true;
	}

	let tools: Record<string, IntegrationItem> | null = null;
	let skills: Record<string, IntegrationItem> | null = null;
	let toolQuery = '';
	let skillQuery = '';
	let searchedToolQuery = '';
	let searchedSkillQuery = '';
	let toolSearchDebounceTimer: ReturnType<typeof setTimeout>;
	let skillSearchDebounceTimer: ReturnType<typeof setTimeout>;
	let toolRequestId = 0;
	let skillRequestId = 0;

	$: toolIds = Object.keys(tools ?? {});
	$: skillIds = Object.keys(skills ?? {});

	$: if (show && toolQuery !== searchedToolQuery) {
		scheduleToolSearch();
	}

	$: if (show && skillQuery !== searchedSkillQuery) {
		scheduleSkillSearch();
	}

	$: if (show) {
		init();
	}

	let fileUploadEnabled = true;
	$: fileUploadEnabled =
		fileUploadCapableModels.length === selectedModels.length &&
		($user?.role === 'admin' || $user?.permissions?.chat?.file_upload);

	const init = async () => {
		await Promise.all([loadTools(), loadSkills()]);
	};

	const setTools = (toolItems: IntegrationItem[] | null, query = '') => {
		const q = query.trim().toLowerCase();
		const items = (toolItems ?? []).reduce<Record<string, IntegrationItem>>((a, tool) => {
			a[tool.id] = {
				...tool,
				name: tool.name,
				description: tool.meta?.description
			};
			return a;
		}, {});

		for (const serverIdx in ($toolServers ?? []) as any[]) {
			const server = (($toolServers ?? []) as any[])[serverIdx];
			if (server.info) {
				const name = server?.info?.title ?? server.url;
				if (q && !name.toLowerCase().includes(q)) {
					continue;
				}

				items[`direct_server:${serverIdx}`] = {
					id: `direct_server:${serverIdx}`,
					name,
					description: server.info.description ?? ''
				};
			}
		}

		tools = items;

		if (!q) {
			selectedToolIds = selectedToolIds.filter((id) => Object.keys(tools ?? {}).includes(id));
		}
	};

	const setSkills = (skillItems: IntegrationItem[] | null, query = '') => {
		skills = (skillItems ?? [])
			.filter((skill) => skill.is_active)
			.reduce<Record<string, IntegrationItem>>((a, skill) => {
				a[skill.id] = {
					...skill,
					name: skill.name,
					description: skill.description
				};
				return a;
			}, {});

		if (!query.trim()) {
			selectedSkillIds = selectedSkillIds.filter((id) => Object.keys(skills ?? {}).includes(id));
		}
	};

	const loadTools = async (query = toolQuery) => {
		const requestId = ++toolRequestId;
		const q = query.trim();
		searchedToolQuery = query;

		if (q) {
			const toolItems = await getTools(localStorage.token, q).catch(() => []);
			if (requestId !== toolRequestId) return;
			setTools(toolItems, q);
			return;
		}

		if ($_tools === null) {
			await _tools.set(await getTools(localStorage.token));
		}
		if (requestId !== toolRequestId) return;
		setTools($_tools, q);
	};

	const loadSkills = async (query = skillQuery) => {
		const requestId = ++skillRequestId;
		const q = query.trim();
		searchedSkillQuery = query;

		if (q) {
			const skillItems = await getSkills(localStorage.token, q).catch(() => []);
			if (requestId !== skillRequestId) return;
			setSkills(skillItems, q);
			return;
		}

		if ($_skills === null) {
			await _skills.set(await getSkills(localStorage.token));
		}
		if (requestId !== skillRequestId) return;
		setSkills($_skills, q);
	};

	const scheduleToolSearch = () => {
		clearTimeout(toolSearchDebounceTimer);
		toolSearchDebounceTimer = setTimeout(() => {
			loadTools();
		}, 200);
	};

	const scheduleSkillSearch = () => {
		clearTimeout(skillSearchDebounceTimer);
		skillSearchDebounceTimer = setTimeout(() => {
			loadSkills();
		}, 200);
	};

	const toggleTool = async (toolId: string, e: MouseEvent) => {
		const tool = tools?.[toolId];
		if (!tool) return;

		if (!(tool.authenticated ?? true)) {
			e.preventDefault();

			const parts = toolId.split(':');
			oauthRedirectHandler({
				id: toolId,
				serverId: parts.at(-1) ?? toolId,
				authType: parts.length > 1 ? (parts[0] === 'server' ? parts[1] : parts[0]) : null
			});
			return;
		}

		const state = !selectedToolIds.includes(toolId);
		await tick();

		if (state) {
			selectedToolIds = [...selectedToolIds, toolId];
		} else {
			selectedToolIds = selectedToolIds.filter((id) => id !== toolId);
		}
	};

	const toggleSkill = async (skillId: string) => {
		const skill = skills?.[skillId];
		if (!skill) return;

		const state = !selectedSkillIds.includes(skillId);
		await tick();

		if (state) {
			selectedSkillIds = [...selectedSkillIds, skillId];
		} else {
			selectedSkillIds = selectedSkillIds.filter((id) => id !== skillId);
		}
	};

	onDestroy(() => {
		clearTimeout(toolSearchDebounceTimer);
		clearTimeout(skillSearchDebounceTimer);
	});
</script>

<Dropdown
	bind:show
	{closeOnOutsideClick}
	onOpenChange={(state) => {
		if (state === false) {
			toolQuery = '';
			skillQuery = '';
			onClose();
		}
	}}
>
	<Tooltip content={$i18n.t('Integrations')} placement="top">
		<slot />
	</Tooltip>
	<div slot="content">
		<DropdownMenu className="min-w-70 max-w-70 max-h-72 overflow-hidden">
			{#if tab === ''}
				<div
					class="max-h-72 overflow-y-auto overflow-x-hidden scrollbar-thin"
					in:fly={{ x: -20, duration: 150 }}
				>
					{#if tools}
						{#if Object.keys(tools).length > 0}
							<button
								class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								on:click={() => {
									tab = 'tools';
								}}
							>
								<Wrench />

								<div class="flex items-center w-full justify-between">
									<div class=" line-clamp-1">
										{$i18n.t('Tools')}
										<span class="ml-0.5 text-gray-500">{Object.keys(tools).length}</span>
									</div>

									<div class="text-gray-500">
										<ChevronRight />
									</div>
								</div>
							</button>
						{/if}

						{#if skills && Object.keys(skills).length > 0}
							<button
								class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								on:click={() => {
									tab = 'skills';
								}}
							>
								<Cube className="size-3.5" strokeWidth="1.75" />

								<div class="flex items-center w-full justify-between">
									<div class=" line-clamp-1">
										{$i18n.t('Skills')}
										<span class="ml-0.5 text-gray-500">{Object.keys(skills).length}</span>
									</div>

									<div class="text-gray-500">
										<ChevronRight />
									</div>
								</div>
							</button>
						{/if}
					{:else}
						<div class="py-4">
							<Spinner />
						</div>
					{/if}

					{#if toggleFilters && toggleFilters.length > 0}
						{#each toggleFilters.sort( (a, b) => a.name.localeCompare( b.name, undefined, { sensitivity: 'base' } ) ) as filter, filterIdx (filter.id)}
							<Tooltip content={filter?.description} placement="top-start">
								<button
									class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
									aria-pressed={selectedFilterIds.includes(filter.id)}
									on:click={() => {
										if (selectedFilterIds.includes(filter.id)) {
											selectedFilterIds = selectedFilterIds.filter((id) => id !== filter.id);
										} else {
											selectedFilterIds = [...selectedFilterIds, filter.id];
										}
									}}
								>
									<div class="flex-1 truncate">
										<div class="flex flex-1 gap-2 items-center">
											<div class="shrink-0">
												{#if filter?.icon}
													<div class="size-3.5 items-center flex justify-center">
														<img
															src={filter.icon}
															class="size-3.5 {filter.icon.includes('data:image/svg')
																? 'dark:invert-[80%]'
																: ''}"
															style="fill: currentColor;"
															alt={filter.name}
														/>
													</div>
												{:else}
													<Sparkles className="size-3.5" strokeWidth="1.75" />
												{/if}
											</div>

											<div class=" truncate">{filter?.name}</div>
										</div>
									</div>

									{#if filter?.has_user_valves && ($user?.role === 'admin' || ($user?.permissions?.chat?.valves ?? true))}
										<div class=" shrink-0">
											<Tooltip content={$i18n.t('Valves')}>
												<button
													class="self-center w-fit text-sm text-gray-600 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition rounded-full"
													type="button"
													on:click={(e) => {
														e.stopPropagation();
														e.preventDefault();
														onShowValves({
															type: 'function',
															id: filter.id
														});
													}}
												>
													<Knobs />
												</button>
											</Tooltip>
										</div>
									{/if}

									<div class=" shrink-0" inert>
										<Switch state={selectedFilterIds.includes(filter.id)} />
									</div>
								</button>
							</Tooltip>
						{/each}
					{/if}

					{#if reasoningControl && reasoningLevel}
						<Tooltip content={$i18n.t('Control how much the model reasons')} placement="top-start">
							<button
								class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[13px] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								on:click={() => {
									tab = 'reasoning';
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<LightBulb className="size-3.5" />
										</div>

										<div class="truncate">{$i18n.t('Reasoning')}</div>
									</div>
								</div>

								<div class="flex shrink-0 items-center gap-1 text-gray-500">
									<span>{reasoningLevel} · {reasoningControl.levels[reasoningLevel]?.label}</span>
									<ChevronRight />
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if openRouterControl}
						<Tooltip
							content={$i18n.t('Choose how OpenRouter selects a provider')}
							placement="top-start"
						>
							<button
								class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[13px] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								on:click={() => {
									tab = 'routing';
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<Bolt className="size-3.5" strokeWidth="1.75" />
										</div>
										<div class="truncate">{$i18n.t('Routing')}</div>
									</div>
								</div>
								<div class="flex shrink-0 items-center gap-1 text-gray-500">
									<span>{getOpenRouterRoutingMode(openRouterRoutingMode).label}</span>
									<ChevronRight />
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if showWebSearchButton}
						<Tooltip content={$i18n.t('Search the internet')} placement="top-start">
							<button
								class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								aria-pressed={webSearchEnabled}
								on:click={() => {
									tab = 'web-search';
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<GlobeAlt />
										</div>

										<div class=" truncate">{$i18n.t('Web Search')}</div>
									</div>
								</div>

								<div class="flex shrink-0 items-center gap-1 text-gray-500">
									<span class="capitalize">{webSearchEngine}</span>
									<ChevronRight />
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if showImageGenerationButton}
						<Tooltip content={$i18n.t('Generate an image')} placement="top-start">
							<button
								class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								aria-pressed={imageGenerationEnabled}
								on:click={() => {
									if (openRouterImageAvailable) {
										tab = 'image-generation';
									} else {
										imageGenerationEnabled = !imageGenerationEnabled;
									}
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<Photo className="size-3.5" strokeWidth="1.5" />
										</div>

										<div class=" truncate">{$i18n.t('Image')}</div>
									</div>
								</div>

								{#if openRouterImageAvailable}
									<div class="flex shrink-0 items-center gap-1 text-gray-500">
										<span>{getOpenRouterImageModel(openRouterImageModel).shortLabel}</span>
										<ChevronRight />
									</div>
								{:else}
									<div class="shrink-0">
										<Switch
											state={imageGenerationEnabled}
											on:change={async () => {
												await tick();
											}}
										/>
									</div>
								{/if}
							</button>
						</Tooltip>
					{/if}

					{#if showCodeInterpreterButton}
						<Tooltip content={$i18n.t('Execute code for analysis')} placement="top-start">
							<button
								class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								aria-pressed={codeInterpreterEnabled}
								on:click={() => {
									codeInterpreterEnabled = !codeInterpreterEnabled;
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<Terminal className="size-3.5" strokeWidth="1.75" />
										</div>

										<div class=" truncate">{$i18n.t('Code Interpreter')}</div>
									</div>
								</div>

								<div class=" shrink-0" inert>
									<Switch state={codeInterpreterEnabled} />
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if showVoiceModeButton}
						<Tooltip content={$i18n.t('Start a hands-free conversation')} placement="top-start">
							<button
								type="button"
								class="flex w-full select-none justify-between gap-2 items-center h-[1.6875rem] px-2 text-[13px] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
								on:click={() => {
									show = false;
									onVoiceMode();
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<Voice className="size-3.5" strokeWidth="2" />
										</div>
										<div class="truncate">{$i18n.t('Voice mode')}</div>
									</div>
								</div>

								<span class="text-[11px] text-gray-500">{$i18n.t('Open')}</span>
							</button>
						</Tooltip>
					{/if}
				</div>
			{:else if tab === 'reasoning' && reasoningControl && reasoningLevel}
				<div in:fly={{ x: 20, duration: 150 }} class="space-y-2 px-1 pb-1">
					<button
						class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-1 text-[13px] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							tab = '';
						}}
					>
						<ChevronLeft />
						<div class="flex w-full items-center justify-between">
							<span>{$i18n.t('Reasoning')}</span>
						</div>
					</button>

					<div class="px-2">
						<div class="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
							{$i18n.t('Thinking level')}
						</div>
						<div class="grid grid-cols-3 gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
							{#each REASONING_LEVEL_IDS.filter((level) => reasoningControl?.levels[level]) as level (level)}
								<button
									type="button"
									class="web-search-choice reasoning-choice relative overflow-hidden rounded-lg border border-transparent px-1 py-1 text-[11px] {reasoningLevel ===
									level
										? 'font-semibold text-gray-900 dark:text-white'
										: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
									aria-pressed={reasoningLevel === level}
									on:click={() => {
										reasoningLevel = level;
										onReasoningLevelChange(level);
									}}
								>
									{#if reasoningLevel === level}
										<span
											aria-hidden="true"
											class="pointer-events-none absolute inset-0 rounded-lg border border-sky-300 bg-sky-100 dark:border-sky-700 dark:bg-sky-900/70"
										></span>
									{/if}
									<div class="relative z-10 uppercase">{level}</div>
									<div class="relative z-10 text-[10px] text-gray-500 dark:text-gray-300">
										{reasoningControl.levels[level]?.label}
									</div>
								</button>
							{/each}
						</div>
						<p class="mt-1.5 text-[10px] leading-4 text-gray-500">
							{reasoningControl.levels[reasoningLevel]?.description ??
								$i18n.t('Provider-tested reasoning preset for this model.')}
						</p>
					</div>
				</div>
			{:else if tab === 'routing' && openRouterControl}
				<div in:fly={{ x: 20, duration: 150 }} class="space-y-2 px-1 pb-1">
					<button
						class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-1 text-[13px] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							tab = '';
						}}
					>
						<ChevronLeft />
						<div class="flex w-full items-center justify-between">
							<span>{$i18n.t('OpenRouter routing')}</span>
						</div>
					</button>

					<div class="px-2">
						<div class="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
							{$i18n.t('Provider choice')}
						</div>
						<div class="grid grid-cols-3 gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
							{#each OPENROUTER_ROUTING_MODES.filter( (mode) => (openRouterControl?.routing_modes ?? ['official']).includes(mode.id) ) as mode (mode.id)}
								<button
									type="button"
									class="relative overflow-hidden rounded-lg border border-transparent px-1 py-1 text-[11px] {openRouterRoutingMode ===
									mode.id
										? 'font-semibold text-gray-900 dark:text-white'
										: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
									aria-pressed={openRouterRoutingMode === mode.id}
									on:click={() => {
										openRouterRoutingMode = mode.id;
										onOpenRouterRoutingModeChange(mode.id);
									}}
								>
									{#if openRouterRoutingMode === mode.id}
										<span
											aria-hidden="true"
											class="pointer-events-none absolute inset-0 rounded-lg border border-violet-300 bg-violet-100 dark:border-violet-700 dark:bg-violet-900/70"
										></span>
									{/if}
									<span class="relative z-10">{mode.label}</span>
								</button>
							{/each}
						</div>
						<p class="mt-1.5 text-[10px] leading-4 text-gray-500">
							{getOpenRouterRoutingMode(openRouterRoutingMode).description}
						</p>
						{#if openRouterRoutingMode !== 'official'}
							<p class="mt-1 text-[10px] leading-4 text-amber-700 dark:text-amber-300">
								{$i18n.t('May use a third-party endpoint; capabilities and caching can vary.')}
							</p>
						{/if}
					</div>
				</div>
			{:else if tab === 'web-search'}
				<div in:fly={{ x: 20, duration: 150 }} class="space-y-2 px-1 pb-1">
					<button
						class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-1 text-[13px] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							tab = '';
						}}
					>
						<ChevronLeft />
						<div class="flex w-full items-center justify-between">
							<span>{$i18n.t('Web Search')}</span>
						</div>
					</button>

					<button
						class="flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-[13px] hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							webSearchEnabled = !webSearchEnabled;
							onWebSearchToggle(webSearchEnabled);
						}}
					>
						<span>{$i18n.t('Enabled')}</span>
						<span class="flex items-center gap-1.5">
							<span
								class="text-[11px] font-medium {webSearchEnabled
									? 'text-sky-700 dark:text-sky-300'
									: 'text-gray-500 dark:text-gray-400'}"
							>
								{webSearchEnabled ? $i18n.t('On') : $i18n.t('Off')}
							</span>
							<span
								aria-hidden="true"
								class="relative h-4 w-7 shrink-0 rounded-full transition-colors duration-150 {webSearchEnabled
									? 'bg-sky-500 dark:bg-sky-400'
									: 'bg-gray-300 dark:bg-gray-700'}"
							>
								<span
									class="absolute top-0.5 block h-3 w-3 rounded-full bg-white shadow-sm transition-all duration-150 {webSearchEnabled
										? 'left-3.5 dark:bg-white'
										: 'left-0.5 dark:bg-gray-400'}"
								></span>
							</span>
						</span>
					</button>

					<div class="px-2">
						<div class="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
							{$i18n.t('Search provider')}
						</div>
						<div
							class="grid {openRouterControl
								? 'grid-cols-3'
								: 'grid-cols-2'} gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800"
						>
							{#each openRouterControl ? OPENROUTER_SEARCH_ENGINES : LOCAL_SEARCH_ENGINES as engine (engine)}
								<button
									type="button"
									class="web-search-choice relative overflow-hidden rounded-lg border border-transparent px-2 py-1 text-[12px] capitalize {webSearchEngine ===
									engine
										? 'font-semibold text-gray-900 dark:text-white'
										: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
									aria-pressed={webSearchEngine === engine}
									on:click={() => {
										webSearchEngine = engine;
									}}
								>
									{#if webSearchEngine === engine}
										<span
											aria-hidden="true"
											class="pointer-events-none absolute inset-0 rounded-lg border border-sky-300 bg-sky-100 dark:border-sky-700 dark:bg-sky-900/70"
										></span>
									{/if}
									<span class="relative z-10">{engine}</span>
								</button>
							{/each}
						</div>
					</div>

					{#if openRouterControl}
						<div class="px-2">
							<div class="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
								{$i18n.t('Search depth')}
							</div>
							<div class="grid grid-cols-3 gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
								{#each OPENROUTER_SEARCH_DEPTHS as depth (depth.id)}
									<button
										type="button"
										class="relative overflow-hidden rounded-lg border border-transparent px-1 py-1 text-[11px] {webSearchDepth ===
										depth.id
											? 'font-semibold text-gray-900 dark:text-white'
											: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
										aria-pressed={webSearchDepth === depth.id}
										on:click={() => applyWebSearchDepth(depth.id)}
									>
										{#if webSearchDepth === depth.id}
											<span
												aria-hidden="true"
												class="pointer-events-none absolute inset-0 rounded-lg border border-sky-300 bg-sky-100 dark:border-sky-700 dark:bg-sky-900/70"
											></span>
										{/if}
										<span class="relative z-10">{$i18n.t(depth.label)}</span>
									</button>
								{/each}
							</div>
							<p class="mt-1.5 text-[10px] leading-4 text-gray-500">
								{$i18n.t(
									OPENROUTER_SEARCH_DEPTHS.find((depth) => depth.id === webSearchDepth)
										?.description ?? ''
								)}
							</p>
						</div>

						<div class="px-2">
							<div class="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
								{$i18n.t('Prompt cache')}
							</div>
							<div class="grid grid-cols-3 gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
								{#each [{ id: 'smart', label: $i18n.t('Smart') }, { id: 'long', label: '1h' }, { id: 'provider_default', label: $i18n.t('Provider') }] as cache (cache.id)}
									<button
										type="button"
										class="relative overflow-hidden rounded-lg border border-transparent px-1 py-1 text-[11px] {openRouterCacheMode ===
										cache.id
											? 'font-semibold text-gray-900 dark:text-white'
											: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
										on:click={() => {
											openRouterCacheMode = cache.id as OpenRouterCacheMode;
										}}
									>
										{#if openRouterCacheMode === cache.id}
											<span
												aria-hidden="true"
												class="pointer-events-none absolute inset-0 rounded-lg border border-sky-300 bg-sky-100 dark:border-sky-700 dark:bg-sky-900/70"
											></span>
										{/if}
										<span class="relative z-10">{cache.label}</span>
									</button>
								{/each}
							</div>
							<p class="mt-1.5 text-[10px] leading-4 text-gray-500">
								{openRouterControl.official_provider === 'anthropic'
									? $i18n.t(
											'Smart uses a five-minute Claude prompt cache; 1h costs more to write but suits long sessions.'
										)
									: $i18n.t(
											'This provider manages prompt caching automatically. Sticky per-chat routing remains enabled.'
										)}
							</p>
						</div>
					{/if}
				</div>
			{:else if tab === 'image-generation' && openRouterImageAvailable}
				<div in:fly={{ x: 20, duration: 150 }} class="space-y-2 px-1 pb-1">
					<button
						class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-1 text-[13px] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							tab = '';
						}}
					>
						<ChevronLeft />
						<div class="flex w-full items-center justify-between">
							<span>{$i18n.t('Image generation')}</span>
						</div>
					</button>

					<button
						class="flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-[13px] hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							imageGenerationEnabled = !imageGenerationEnabled;
						}}
					>
						<span>{$i18n.t('Enabled')}</span>
						<span class="flex items-center gap-1.5">
							<span
								class="text-[11px] font-medium {imageGenerationEnabled
									? 'text-sky-700 dark:text-sky-300'
									: 'text-gray-500 dark:text-gray-400'}"
							>
								{imageGenerationEnabled ? $i18n.t('On') : $i18n.t('Off')}
							</span>
							<span
								aria-hidden="true"
								class="relative h-4 w-7 shrink-0 rounded-full transition-colors duration-150 {imageGenerationEnabled
									? 'bg-sky-500 dark:bg-sky-400'
									: 'bg-gray-300 dark:bg-gray-700'}"
							>
								<span
									class="absolute top-0.5 block h-3 w-3 rounded-full bg-white shadow-sm transition-all duration-150 {imageGenerationEnabled
										? 'left-3.5 dark:bg-white'
										: 'left-0.5 dark:bg-gray-400'}"
								></span>
							</span>
						</span>
					</button>

					<div class="px-2">
						<div class="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
							{$i18n.t('Image model')}
						</div>
						<div class="grid grid-cols-2 gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
							{#each OPENROUTER_IMAGE_MODELS as model (model.id)}
								<button
									type="button"
									class="relative overflow-hidden rounded-lg border border-transparent px-2 py-1.5 text-left text-[11px] {openRouterImageModel ===
									model.id
										? 'font-semibold text-gray-900 dark:text-white'
										: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
									aria-pressed={openRouterImageModel === model.id}
									on:click={() => {
										openRouterImageModel = model.id;
									}}
								>
									{#if openRouterImageModel === model.id}
										<span
											aria-hidden="true"
											class="pointer-events-none absolute inset-0 rounded-lg border border-sky-300 bg-sky-100 dark:border-sky-700 dark:bg-sky-900/70"
										></span>
									{/if}
									<span class="relative z-10 block truncate">{model.shortLabel}</span>
								</button>
							{/each}
						</div>
						<p class="mt-1.5 text-[10px] leading-4 text-gray-500">
							{getOpenRouterImageModel(openRouterImageModel).description}
						</p>
						<p class="mt-1 text-[10px] leading-4 text-gray-500">
							{$i18n.t('Your prompt goes directly to this image model. No chat model is called.')}
						</p>
					</div>
				</div>
			{:else if tab === 'tools' && tools}
				<div class="flex max-h-72 min-h-0 flex-col gap-0.5" in:fly={{ x: 20, duration: 150 }}>
					<button
						class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							toolQuery = '';
							tab = '';
						}}
					>
						<ChevronLeft />

						<div class="flex items-center w-full justify-between">
							<div>
								{$i18n.t('Tools')}
								<span class="ml-0.5 text-gray-500">{toolIds.length}</span>
							</div>
						</div>
					</button>

					<SearchInput bind:value={toolQuery} placeholder={$i18n.t('Search tools')} />

					<div class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin">
						{#if toolIds.length === 0}
							<div class="text-center text-xs text-gray-500 py-3">{$i18n.t('No tools found')}</div>
						{:else}
							<div class="flex flex-col gap-0.5">
								{#each toolIds as toolId}
									<button
										class="relative flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
										aria-pressed={(tools?.[toolId]?.authenticated ?? true)
											? selectedToolIds.includes(toolId)
											: undefined}
										on:click={async (e) => {
											await toggleTool(toolId, e);
										}}
									>
										{#if !(tools?.[toolId]?.authenticated ?? true)}
											<!-- make it slighly darker and not clickable -->
											<div class="absolute inset-0 opacity-50 rounded-xl cursor-pointer z-10"></div>
										{/if}
										<div class="flex-1 truncate">
											<div class="flex flex-1 gap-2 items-center">
												<Tooltip content={tools?.[toolId]?.name ?? ''} placement="top">
													<div class="shrink-0">
														<Wrench />
													</div>
												</Tooltip>
												<Tooltip content={tools?.[toolId]?.description ?? ''} placement="top-start">
													<div class=" truncate">{tools?.[toolId]?.name}</div>
												</Tooltip>
											</div>
										</div>

										{#if tools?.[toolId]?.authenticated === true && toolId.startsWith('server:mcp:')}
											<div class="shrink-0">
												<Tooltip content={$i18n.t('Disconnect OAuth')}>
													<button
														class="self-center w-fit text-sm text-gray-600 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition rounded-full"
														type="button"
														on:click={async (e) => {
															e.stopPropagation();
															e.preventDefault();

															const parts = toolId.split(':');
															const serverId = parts.at(-1) ?? toolId;
															const provider = `mcp:${serverId}`;

															try {
																await deleteOAuthSession(localStorage.token, provider);
																toast.success($i18n.t('OAuth session disconnected'));

																// Refresh tools to update authenticated state
																_tools.set(await getTools(localStorage.token));
																selectedToolIds = selectedToolIds.filter((id) => id !== toolId);
																await init();
															} catch (err) {
																toast.error(err ?? $i18n.t('Failed to disconnect'));
															}
														}}
													>
														<LinkSlash className="size-3.5" />
													</button>
												</Tooltip>
											</div>
										{/if}

										{#if tools?.[toolId]?.has_user_valves && ($user?.role === 'admin' || ($user?.permissions?.chat?.valves ?? true))}
											<div class=" shrink-0">
												<Tooltip content={$i18n.t('Valves')}>
													<button
														class="self-center w-fit text-sm text-gray-600 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition rounded-full"
														type="button"
														on:click={(e) => {
															e.stopPropagation();
															e.preventDefault();
															onShowValves({
																type: 'tool',
																id: toolId
															});
														}}
													>
														<Knobs />
													</button>
												</Tooltip>
											</div>
										{/if}

										<div class=" shrink-0" inert>
											<Switch state={selectedToolIds.includes(toolId)} />
										</div>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			{:else if tab === 'skills' && skills}
				<div class="flex max-h-72 min-h-0 flex-col gap-0.5" in:fly={{ x: 20, duration: 150 }}>
					<button
						class="flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
						on:click={() => {
							skillQuery = '';
							tab = '';
						}}
					>
						<ChevronLeft />

						<div class="flex items-center w-full justify-between">
							<div>
								{$i18n.t('Skills')}
								<span class="ml-0.5 text-gray-500">{skillIds.length}</span>
							</div>
						</div>
					</button>

					<SearchInput bind:value={skillQuery} placeholder={$i18n.t('Search skills')} />

					<div class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin">
						{#if skillIds.length === 0}
							<div class="text-center text-xs text-gray-500 py-3">{$i18n.t('No skills found')}</div>
						{:else}
							<div class="flex flex-col gap-0.5">
								{#each skillIds as skillId}
									<button
										class="relative flex w-full justify-between gap-2 items-center h-[1.6875rem] px-2 text-[0.8125rem] font-normal cursor-pointer rounded-xl hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
										aria-pressed={selectedSkillIds.includes(skillId)}
										on:click={async () => {
											await toggleSkill(skillId);
										}}
									>
										<div class="flex-1 truncate">
											<div class="flex flex-1 gap-2 items-center">
												<Tooltip content={skills?.[skillId]?.name ?? ''} placement="top">
													<div class="shrink-0">
														<Cube className="size-3.5" strokeWidth="1.75" />
													</div>
												</Tooltip>
												<Tooltip
													content={skills?.[skillId]?.description ?? ''}
													placement="top-start"
												>
													<div class=" truncate">{skills?.[skillId]?.name}</div>
												</Tooltip>
											</div>
										</div>

										<div class=" shrink-0" inert>
											<Switch state={selectedSkillIds.includes(skillId)} />
										</div>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</DropdownMenu>
	</div>
</Dropdown>

<style>
	button.web-search-choice {
		-webkit-tap-highlight-color: transparent;
	}

	button.web-search-choice[aria-pressed='true'] {
		background-color: rgb(255 255 255) !important;
		border-color: rgb(229 231 235) !important;
		border-radius: 0.5rem !important;
		box-shadow:
			0 1px 2px 0 rgb(0 0 0 / 0.05),
			0 0 0 1px rgb(0 0 0 / 0.02) !important;
	}

	:global(.dark) button.web-search-choice[aria-pressed='true'] {
		background-color: rgb(55 65 81) !important;
		border-color: rgb(75 85 99) !important;
	}

	button.web-search-choice[aria-pressed='false'],
	button.web-search-choice[aria-pressed='false']:hover {
		background-color: transparent !important;
		border-color: transparent !important;
		box-shadow: none !important;
	}

	button.web-search-choice:focus:not(:focus-visible) {
		outline: none;
	}

	@media (hover: hover) and (pointer: fine) {
		button.web-search-choice[aria-pressed='false']:hover {
			background-color: rgb(249 250 251 / 0.4) !important;
		}

		:global(.dark) button.web-search-choice[aria-pressed='false']:hover {
			background-color: rgb(31 41 55 / 0.4) !important;
		}
	}
</style>
