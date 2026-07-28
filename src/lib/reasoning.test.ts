import { describe, expect, it } from 'vitest';
import {
	getNextReasoningLevel,
	normalizeReasoningControl,
	resolveReasoningLevel
} from './reasoning';

const control = normalizeReasoningControl({
	default_level: 'r1',
	levels: {
		r0: { label: 'Instant' },
		r1: { label: 'Balanced' },
		r2: { label: 'Deep' }
	}
});

describe('reasoning controls', () => {
	it('uses the configured default and accepts supported choices', () => {
		expect(resolveReasoningLevel(control, null)).toBe('r1');
		expect(resolveReasoningLevel(control, 'r2')).toBe('r2');
		expect(resolveReasoningLevel(control, 'invalid')).toBe('r1');
	});

	it('cycles through available levels in display order', () => {
		expect(getNextReasoningLevel(control!, 'r0')).toBe('r1');
		expect(getNextReasoningLevel(control!, 'r2')).toBe('r0');
	});

	it('rejects malformed metadata', () => {
		expect(normalizeReasoningControl({ levels: { r1: {} } })).toBeNull();
		expect(normalizeReasoningControl(null)).toBeNull();
	});
});
