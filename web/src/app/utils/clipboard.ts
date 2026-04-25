/**
 * Copy text to clipboard with fallback support
 * Tries to use modern Clipboard API first, falls back to execCommand if not available
 *
 * @param text - The text to copy to clipboard
 * @returns Promise<boolean> - true if successful, false otherwise
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // Try modern Clipboard API first
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.error('[Clipboard] Modern API failed, trying fallback:', err);
      // Fall through to legacy method
    }
  }

  // Fallback to legacy execCommand method
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);

    return successful;
  } catch (err) {
    console.error('[Clipboard] Fallback method failed:', err);
    return false;
  }
}
