import { format, isValid } from "date-fns";

// Classes used to ensure content in a given Table column breaks and wraps at container column size width.
export const wrapColumnContentClass = "whitespace-normal break-all";

// Convert given ISO format date string to date
// represented in the client's time zone;
export function formatDate(isoDateString: string): string {
  // The Date object in JavaScript automatically handles time zone conversions, so you don't need to manually adjust for the user's time zone
  const localDate = new Date(isoDateString);
  if (!isValid(localDate)) {
    // Not a valid date, return same string.
    console.error(`Invalid ISO date string: ${isoDateString}`);
    return isoDateString;
  }
  return format(localDate, "yyyy-MM-dd HH:mm:ss a");
}
