import { useId } from 'react'
import { useTheme, type ThemeChoice } from '@/lib/theme'
import styles from './ThemeSwitch.module.css'

const OPTIONS: readonly { value: ThemeChoice; label: string }[] = [
    { value: 'system', label: 'Match device' },
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
]

/**
 * Light, dark, or whatever the device is set to: a small radio group for
 * the page's small print. Arrow keys move between the three, as with any
 * radio group, and the choice is kept in this browser.
 */
export function ThemeSwitch() {
    const { choice, setChoice } = useTheme()
    const name = useId()
    return (
        <fieldset className={styles.switch}>
            <legend className={styles.legend}>Appearance</legend>
            <div className={styles.options}>
                {OPTIONS.map((option) => (
                    <label key={option.value} className={styles.option}>
                        <input type="radio" name={name} className={styles.radio} checked={choice === option.value} onChange={() => setChoice(option.value)} />
                        {option.label}
                    </label>
                ))}
            </div>
        </fieldset>
    )
}
