const NAME_PATTERN = /^[A-Za-z _]+$/;

export const NAME_REQUIREMENTS =
  "Name may only contain letters, spaces, and underscores.";

export function isValidName(name: string): boolean {
  const trimmed = name.trim();
  if (!trimmed) return false;
  if (!NAME_PATTERN.test(trimmed)) return false;
  return /[A-Za-z]/.test(trimmed);
}

export function normalizeName(name: string): string {
  return name.trim();
}
