/** A template is plain text with `{{ step.key }}` references shown as chips. */
export type TemplateSegment =
  { kind: 'text'; text: string } | { kind: 'ref'; path: string };

const REF = /\{\{\s*([A-Za-z_一-鿿][\w一-鿿]*(?:\.[\w一-鿿]+)+)\s*\}\}/g;

export function parseTemplate(value: string): TemplateSegment[] {
  const segments: TemplateSegment[] = [];
  let last = 0;
  for (const match of value.matchAll(REF)) {
    if (match.index! > last) {
      segments.push({ kind: 'text', text: value.slice(last, match.index) });
    }
    segments.push({ kind: 'ref', path: match[1] });
    last = match.index! + match[0].length;
  }
  if (last < value.length) {
    segments.push({ kind: 'text', text: value.slice(last) });
  }
  return segments;
}

export const refToken = (path: string) => `{{ ${path} }}`;

/** Paths referenced by a template, e.g. `llm_1.text`. */
export function templateRefs(value: string): string[] {
  return [...value.matchAll(REF)].map((match) => match[1]);
}
