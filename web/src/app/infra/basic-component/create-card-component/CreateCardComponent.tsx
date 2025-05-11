import styles from './createCartComponent.module.css';

export default function CreateCardComponent({
  height,
  plusSize,
  onClick,
  width = '100%',
}: {
  height: string;
  plusSize: string;
  onClick: () => void;
  width?: string;
}) {
  return (
    <div
      className={`${styles.cardContainer} ${styles.createCardContainer} `}
      style={{
        width: `${width}`,
        height: `${height}`,
        fontSize: `${plusSize}px`,
      }}
      onClick={onClick}
    >
      +
    </div>
  );
}
