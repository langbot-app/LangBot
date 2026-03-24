export interface ISkillCardVO {
  skillName: string;
  name: string;
  description: string;
  isBuiltin: boolean;
  lastUpdatedTimeAgo: string;
}

export class SkillCardVO implements ISkillCardVO {
  skillName: string;
  name: string;
  description: string;
  isBuiltin: boolean;
  lastUpdatedTimeAgo: string;

  constructor(props: ISkillCardVO) {
    this.skillName = props.skillName;
    this.name = props.name;
    this.description = props.description;
    this.isBuiltin = props.isBuiltin;
    this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
  }
}
