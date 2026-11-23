export const envKeyPattern = /^[A-Z][A-Z0-9_]*$/;

export function splitEnvAnyGroup(value: string): string[] {
  return value.split("|").map((item) => item.trim()).filter(Boolean);
}

export function isEnvAnyGroup(value: string): boolean {
  const keys = splitEnvAnyGroup(value);
  return keys.length >= 2 && new Set(keys).size === keys.length && keys.every((key) => envKeyPattern.test(key));
}
