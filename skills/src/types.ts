export type Skill = {
  path: string;
  directory: string;
  name: string;
  description: string;
  body: string;
};

export type CommandContext = {
  root: string;
  args: string[];
};

export type ParsedYamlValue = string | boolean | string[];

export type ParsedYaml = Record<string, ParsedYamlValue>;

export type StructuredItem = {
  path: string;
  skill: string;
  fields: ParsedYaml;
  raw: string;
};

export type StructuredItemKind = "cases" | "suites" | "troubleshooting";
