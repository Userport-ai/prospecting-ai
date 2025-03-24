import { format, isValid } from "date-fns";
import { unparse } from "papaparse";

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

// Exports given JSON data to CSV.
export const exportToCSV = (data: any[], filename: string) => {
  if (!data.length) {
    console.warn("No data available to export.");
    return;
  }

  const csv = unparse(data); // Convert JSON to CSV format
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${filename}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
