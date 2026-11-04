import { Button, Select } from '@mantine/core'
import { type ReactNode, useMemo } from 'react'

const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

/** Pick a time zone, with a one-click switch to the browser's when it differs. */
export function TimeZoneSelect({
  value,
  onChange,
  description,
  error,
}: {
  value: string
  onChange: (zone: string) => void
  description?: ReactNode
  error?: ReactNode
}) {
  const zones = useMemo(
    () => Array.from(new Set([value, browserTimeZone, ...Intl.supportedValuesOf('timeZone')])),
    [value],
  )
  const differs = value !== browserTimeZone
  return (
    <Select
      label="Time zone"
      data={zones}
      searchable
      allowDeselect={false}
      value={value}
      onChange={(zone) => zone && onChange(zone)}
      error={error}
      description={
        description || differs ? (
          <>
            {description}
            {description && differs ? ' ' : ''}
            {differs && (
              <>
                Your browser is set to {browserTimeZone}.{' '}
                <Button
                  variant="transparent"
                  size="compact-xs"
                  p={0}
                  onClick={() => onChange(browserTimeZone)}
                >
                  Use it
                </Button>
              </>
            )}
          </>
        ) : undefined
      }
    />
  )
}
