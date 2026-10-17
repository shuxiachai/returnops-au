/**
 * Idempotency key utility matching contract schema:
 * ^[A-Za-z0-9._:-]{8,128}
 */
export function generateIdempotencyKey(prefix: string = 'idem'): string {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).substring(2, 10);
  const rand2 = Math.random().toString(36).substring(2, 10);
  return `${prefix}_${ts}_${rand}${rand2}`;
}
