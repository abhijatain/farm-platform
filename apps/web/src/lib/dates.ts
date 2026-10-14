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
