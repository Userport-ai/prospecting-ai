/*global chrome*/

// Get current tab of the popup.
export async function getCurrentTab() {
  let queryOptions = { active: true, lastFocusedWindow: true };
  // `tab` will either be a `tabs.Tab` instance or `undefined`.
  let [tab] = await chrome.tabs.query(queryOptions);
  if (tab === undefined) {
    console.error("Got undefined active tab, could not fetch lead profile.");
    return null;
  }
  return tab;
}
