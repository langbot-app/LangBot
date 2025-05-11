import styles from './emptyAndCreate.module.css';

export default function EmptyAndCreateComponent({
  title,
  subTitle,
  buttonText,
  onButtonClick,
}: {
  title: string;
  subTitle: string;
  buttonText: string;
  onButtonClick: () => void;
}) {
  return (
    <div className={`${styles.emptyPageContainer}`}>
      <div className={`${styles.emptyContainer}`}>
        <div className={`${styles.emptyInfoContainer}`}>
          <div className={`${styles.emptyInfoText}`}>{title}</div>
          <div className={`${styles.emptyInfoSubText}`}>{subTitle}</div>
        </div>
        <div className={`${styles.emptyCreateButton}`} onClick={onButtonClick}>
          {buttonText}
        </div>
      </div>
    </div>
  );
}
