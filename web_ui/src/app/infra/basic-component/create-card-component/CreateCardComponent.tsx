import styles from "./createCartComponent.module.css";

export default function CreateCardComponent({
    height,
    plusSize,
    onClick,
}: {
    height: number;
    plusSize: number;
    onClick: () => void
}) {
    return (
        <div
            className={`${styles.cardContainer} ${styles.createCardContainer} `}
            style={{
                width: `100%`,
                height: `${height}px`,
                fontSize: `${plusSize}px`
            }}
            onClick={onClick}
        >
            +
        </div>
    )
}