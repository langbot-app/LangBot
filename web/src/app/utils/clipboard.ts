/** Copy text using the Clipboard API, with a focus-trap-safe legacy fallback. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Permission/security errors can include sensitive text; do not log them.
  }

  const previousFocus = document.activeElement as HTMLElement | null;
  const textArea = document.createElement('textarea');
  try {
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    // Radix modal focus scopes reject focus on elements appended to body.
    const container =
      previousFocus?.closest('[role="dialog"], [role="alertdialog"]') ??
      document.body;
    container.appendChild(textArea);
    textArea.focus({ preventScroll: true });
    textArea.select();
    if (
      document.activeElement !== textArea ||
      textArea.selectionEnd !== text.length
    )
      return false;
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    textArea.remove();
    if (previousFocus?.isConnected)
      previousFocus.focus({ preventScroll: true });
  }
}
