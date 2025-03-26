import styles from "./HomeTittleBar.module.css"


export default function HomeTitleBar({
    title,
}: {
    title: string
}) {
    return (
        <div className={`${styles.titleBarContainer}`}>
            <div
                className={`${styles.titleText}`}
            >{title}</div>
        </div>
    );
}