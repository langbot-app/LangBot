import styles from "./createCartComponent.module.css";

export default function CreateCardComponent({
    width,
    height,
    plusSize,
    onClick,
}: {
    width: number;
    height: number;
    plusSize: number;
    onClick: () => void
}) {
    return (
        <div
            className={`${styles.cardContainer} ${styles.createCardContainer} `}
            style={{
                width: `${width}px`,
                height: `${height}px`,
                fontSize: `${plusSize}px`
            }}
            onClick={onClick}
        >
            +
        </div>
    )
}