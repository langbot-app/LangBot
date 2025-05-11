import styles from './HomeSidebar.module.css';

export interface ISidebarChildVO {
  id: string;
  icon: React.ReactNode;
  name: string;
  route: string;
  description: string;
  helpLink: string;
}

export class SidebarChildVO {
  id: string;
  icon: React.ReactNode;
  name: string;
  route: string;
  description: string;
  helpLink: string;

  constructor(props: ISidebarChildVO) {
    this.id = props.id;
    this.icon = props.icon;
    this.name = props.name;
    this.route = props.route;
    this.description = props.description;
    this.helpLink = props.helpLink;
  }
}

export function SidebarChild({
  icon,
  name,
  isSelected,
  onClick,
}: {
  icon: React.ReactNode;
  name: string;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <div
      className={`${styles.sidebarChildContainer} ${
        isSelected ? styles.sidebarSelected : styles.sidebarUnselected
      }`}
      onClick={onClick}
    >
      <div className={`${styles.sidebarChildIcon}`}>{icon}</div>
      <span className={`${styles.sidebarChildName}`}>{name}</span>
    </div>
  );
}
