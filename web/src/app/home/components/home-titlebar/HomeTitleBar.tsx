import styles from './HomeTittleBar.module.css';

export default function HomeTitleBar({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className={`${styles.titleBarContainer}`}>
      <div className={`${styles.titleText}`}>{title}</div>
      <div className={`${styles.subtitleText}`}>{subtitle}</div>
    </div>
  );
}
