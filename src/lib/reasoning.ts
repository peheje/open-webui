export const REASONING_LEVEL_IDS = ['r0', 'r1', 'r2'] as const;

export type ReasoningLevel = (typeof REASONING_LEVEL_IDS)[number];

export type ReasoningLevelConfig = {
	label: string;
	description?: string;
	params?: Record<string, unknown>;
};

export type ReasoningControl = {
	default_level: ReasoningLevel;
	levels: Partial<Record<ReasoningLevel, ReasoningLevelConfig>>;
};

export const normalizeReasoningControl = (value: unknown): ReasoningControl | null => {
	if (!value || typeof value !== 'object') return null;

	const raw = value as Record<string, unknown>;
	const rawLevels =
		raw.levels && typeof raw.levels === 'object' ? (raw.levels as Record<string, unknown>) : {};
	const levels: Partial<Record<ReasoningLevel, ReasoningLevelConfig>> = {};

	for (const level of REASONING_LEVEL_IDS) {
		const config = rawLevels[level];
		if (!config || typeof config !== 'object') continue;
		const typed = config as Record<string, unknown>;
		if (typeof typed.label !== 'string' || typed.label.trim() === '') continue;
		levels[level] = {
			label: typed.label,
			...(typeof typed.description === 'string' ? { description: typed.description } : {})
		};
	}

	const available = REASONING_LEVEL_IDS.filter((level) => levels[level]);
	if (available.length === 0) return null;

	const requestedDefault = raw.default_level;
	const defaultLevel =
		typeof requestedDefault === 'string' &&
		REASONING_LEVEL_IDS.includes(requestedDefault as ReasoningLevel) &&
		levels[requestedDefault as ReasoningLevel]
			? (requestedDefault as ReasoningLevel)
			: levels.r1
				? 'r1'
				: available[0];

	return {
		default_level: defaultLevel,
		levels
	};
};

export const getReasoningControlForModels = (
	models: any[],
	selectedModelIds: string[]
): ReasoningControl | null => {
	if (selectedModelIds.length !== 1) return null;
	const model = models.find((item) => item.id === selectedModelIds[0]);
	return normalizeReasoningControl(model?.info?.meta?.reasoning_control);
};

export const resolveReasoningLevel = (
	control: ReasoningControl | null,
	requestedLevel: string | null | undefined
): ReasoningLevel | null => {
	if (!control) return null;
	if (
		requestedLevel &&
		REASONING_LEVEL_IDS.includes(requestedLevel as ReasoningLevel) &&
		control.levels[requestedLevel as ReasoningLevel]
	) {
		return requestedLevel as ReasoningLevel;
	}
	return control.default_level;
};

export const getNextReasoningLevel = (
	control: ReasoningControl,
	currentLevel: ReasoningLevel
): ReasoningLevel => {
	const available = REASONING_LEVEL_IDS.filter((level) => control.levels[level]);
	const currentIndex = available.indexOf(currentLevel);
	return available[(currentIndex + 1) % available.length];
};
