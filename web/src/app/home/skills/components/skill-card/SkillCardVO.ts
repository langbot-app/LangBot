export interface ISkillCardVO {
  id: string;
  name: string;
  description: string;
  type: 'skill' | 'workflow';
  isEnabled: boolean;
  isBuiltin: boolean;
  author?: string;
  version?: string;
  tags?: string[];
  lastUpdatedTimeAgo: string;
}

export class SkillCardVO implements ISkillCardVO {
  id: string;
  name: string;
  description: string;
  type: 'skill' | 'workflow';
  isEnabled: boolean;
  isBuiltin: boolean;
  author?: string;
  version?: string;
  tags?: string[];
  lastUpdatedTimeAgo: string;

  constructor(props: ISkillCardVO) {
    this.id = props.id;
    this.name = props.name;
    this.description = props.description;
    this.type = props.type;
    this.isEnabled = props.isEnabled;
    this.isBuiltin = props.isBuiltin;
    this.author = props.author;
    this.version = props.version;
    this.tags = props.tags;
    this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
  }
}
