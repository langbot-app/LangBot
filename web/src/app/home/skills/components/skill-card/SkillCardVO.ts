export interface ISkillCardVO {
  id: string;
  name: string;
  description: string;
  isEnabled: boolean;
  isBuiltin: boolean;
  lastUpdatedTimeAgo: string;
}

export class SkillCardVO implements ISkillCardVO {
  id: string;
  name: string;
  description: string;
  isEnabled: boolean;
  isBuiltin: boolean;
  lastUpdatedTimeAgo: string;

  constructor(props: ISkillCardVO) {
    this.id = props.id;
    this.name = props.name;
    this.description = props.description;
    this.isEnabled = props.isEnabled;
    this.isBuiltin = props.isBuiltin;
    this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
  }
}
