import { I18nObject } from '@/app/infra/entities/common';

export interface ISidebarChildVO {
  id: string;
  icon: React.ReactNode;
  name: string;
  route: string;
  description: string;
  helpLink: I18nObject;
}

export class SidebarChildVO {
  id: string;
  icon: React.ReactNode;
  name: string;
  route: string;
  description: string;
  helpLink: I18nObject;

  constructor(props: ISidebarChildVO) {
    this.id = props.id;
    this.icon = props.icon;
    this.name = props.name;
    this.route = props.route;
    this.description = props.description;
    this.helpLink = props.helpLink;
  }
}
