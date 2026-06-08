const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$/;
const NAME_PATTERN = /^[A-Za-z _]+$/;

export const NAME_REQUIREMENTS =
  "Name may only contain letters, spaces, and underscores.";


export const PASSWORD_REQUIREMENTS =
  "Password must be at least 8 characters long and include uppercase and lowercase letters, at least one number, and at least one special character.";

export function isValidPassword(password: string): boolean {
  return PASSWORD_PATTERN.test(password) && password.length >= 8;
}

export function isValidName(name: string): boolean {
  const trimmed = name.trim();
  if (!trimmed) return false;
  if (!NAME_PATTERN.test(trimmed)) return false;
  return /[A-Za-z]/.test(trimmed);
}

export function normalizeName(name: string): string {
  return name.trim();
}
