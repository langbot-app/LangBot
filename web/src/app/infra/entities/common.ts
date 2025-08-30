export interface I18nObject {
  en_US: string;
  zh_Hans: string;
  zh_Hant?: string;
  ja_JP?: string;
}

export interface ComponentManifest {
  apiVersion: string;
  kind: string;
  metadata: {
    name: string;
    label: I18nObject;
    description?: I18nObject;
    icon?: string;
    repository?: string;
    version?: string;
    author?: string;
  };
  spec: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
}
