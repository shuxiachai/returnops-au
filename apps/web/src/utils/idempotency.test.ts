import { describe, it, expect } from 'vitest';
import { generateIdempotencyKey } from './idempotency';

describe('idempotency', () => {
  it('generates keys conforming to RFC pattern ^[A-Za-z0-9._:-]{8,128}$', () => {
    const pattern = /^[A-Za-z0-9._:-]{8,128}$/;
    for (let i = 0; i < 50; i++) {
      const key = generateIdempotencyKey();
      expect(key).toMatch(pattern);
      expect(key.length).toBeGreaterThanOrEqual(8);
      expect(key.length).toBeLessThanOrEqual(128);
    }
  });

  it('generates unique keys across consecutive calls', () => {
    const keys = new Set<string>();
    for (let i = 0; i < 100; i++) {
      keys.add(generateIdempotencyKey());
    }
    expect(keys.size).toBe(100);
  });
});
