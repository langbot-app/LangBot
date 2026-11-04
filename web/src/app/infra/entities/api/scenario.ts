export interface ScenarioPackage {
  format: 'langbot-scenario';
  format_version: 1;
  metadata: {
    name: string;
    description: string;
    version: string;
    author: string;
    instructions: string;
  };
  resources: { id: string; kind: string; data: Record<string, unknown> }[];
  dependencies: {
    kind: string;
    id: string;
    plugin_id: string;
    version: string | null;
  }[];
  inputs: ScenarioInput[];
}

export interface ScenarioInput {
  resource: string;
  path: (string | number)[];
  kind: string;
  label: string | Record<string, string>;
  required: boolean;
  status?: string;
}

export interface ScenarioReport {
  id: string;
  metadata: ScenarioPackage['metadata'];
  resources: { id: string; kind: string; uuid: string; name: string }[];
  inputs: ScenarioInput[];
  dependencies: (ScenarioPackage['dependencies'][number] & {
    status: string;
  })[];
}
