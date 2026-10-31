export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (
    typeof error === 'object' &&
    error !== null &&
    'msg' in error &&
    typeof error.msg === 'string'
  ) {
    return error.msg;
  }
  return String(error);
}
