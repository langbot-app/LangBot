import styles from "./createCartComponent.module.css";

export default function CreateCardComponent({
    plusSize,
    onClick,
}: {
    plusSize: number;
    onClick: () => void
}) {
    return (
        <div
            className={`${styles.cardContainer} ${styles.createCardContainer} `}
            style={{
                width: `100%`,
                height: `100%`,
                fontSize: `${plusSize}px`
            }}
            onClick={onClick}
        >
            +
        </div>
    )
}