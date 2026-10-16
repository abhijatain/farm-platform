export function localDateInputValue(
  value: Date = new Date(),
) {
  const local = new Date(
    value.getTime()
    - value.getTimezoneOffset()
      * 60_000,
  );

  return local
    .toISOString()
    .slice(
      0,
      10,
    );
}

/** Preserve the farmer's civil calendar day when sending datetime-local input.

  Backend uses the submitted timestamp's own date for planting/harvest.
  Converting midnight IST to UTC first would incorrectly subtract one day.
*/
export function localDateTimeWithOffset(datetimeLocal: string) {
  const instant = new Date(datetimeLocal);
  if (!datetimeLocal || !Number.isFinite(instant.getTime())) {
    throw new Error("Choose a valid local date and time.");
  }
  const offset = -instant.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const magnitude = Math.abs(offset);
  return `${datetimeLocal}${sign}${String(Math.floor(magnitude / 60)).padStart(2, "0")}:${String(magnitude % 60).padStart(2,"0")}`;
}
