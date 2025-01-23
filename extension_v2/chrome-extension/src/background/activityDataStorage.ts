import { ActivityData } from './common';

// Returns a string key from given tab Id (Number).
const getTabIdKey = (tabId: number): string => {
  return tabId.toString();
};

// Insert or update given data object in storage for given tab Id.
export const setActivityData = (tabId: number, data: ActivityData): Promise<void> => {
  const tabIdKey = getTabIdKey(tabId);
  return chrome.storage.local.set({ [tabIdKey]: data });
};

// Returns data object associated with given tab Id from storage. Returns null if it does not exist.
export const getActivityData = async (tabId: number): Promise<ActivityData | null> => {
  const tabIdKey = getTabIdKey(tabId);
  const item = await chrome.storage.local.get([tabIdKey]);
  if (tabIdKey in item) {
    return item[tabIdKey];
  }
  // Tab data object does not exist, return null.
  return null;
};
