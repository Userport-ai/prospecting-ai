import { runtime, storage, alarms, notifications } from "webextension-polyfill";

// Returns a string key from given tab Id (Number).
function getTabIdKey(tabId) {
  return tabId.toString();
}

// Helper that converts tabId key to number.
export function tabIdKeyToNumber(tabIdKey) {
  return Number(tabIdKey);
}

// Insert or update given data object in storage for given tab Id.
export function setTabData(tabId, data) {
  const tabIdKey = getTabIdKey(tabId);
  storage.local.set({ [tabIdKey]: data });
}

// Returns data object associated with given tab Id from storage. Returns null if it does not exist.
export async function getTabData(tabId) {
  const tabIdKey = getTabIdKey(tabId);
  const item = await storage.local.get([tabIdKey]);
  if (tabIdKey in item) {
    return item[tabIdKey];
  }
  // User object does not exist (likely because this tab does not currently have a valid LinkedIn profile), return null.
  return null;
}

// Delete data object associated with given tab. Usually called when tab is closed.
export function clearTabData(tabId) {
  const tabIdKey = getTabIdKey(tabId);
  storage.local.remove([tabIdKey]);
}

// Alarm methods.

// Create alarm for given tab.
export function createAlarm(tabId) {
  const tabIdKey = getTabIdKey(tabId);
  alarms.create(tabIdKey, { periodInMinutes: 1 });
}

// Returns true if alarms exists for given tab and false otherwise.
export async function doesAlarmExist(tabId) {
  const tabIdKey = getTabIdKey(tabId);
  const item = await alarms.get(tabIdKey);
  return item !== undefined && "name" in item;
}

// Delete alarm associated with given tab.
export function clearAlarm(tabId) {
  const tabIdKey = getTabIdKey(tabId);
  alarms.clear(tabIdKey);
}

// Create notification in given tab.
export async function createNotification(tabId, title, message) {
  const tabIdKey = getTabIdKey(tabId);
  notifications.create(tabIdKey, {
    type: "basic",
    title: title,
    message: message,
    iconUrl: runtime.getURL("logo256.png"),
  });
}
