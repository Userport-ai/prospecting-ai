// No external code loading possible (this disables all extensions such as Replay, Surveys, Exceptions etc.)
// Reference: https://posthog.com/docs/libraries/js.
import posthog from "posthog-js/dist/module.no-external";

// Initializes posthog instance if not initialized.
// Problem is that service worker can go idle so it
// needs to be re-initialized.
function initPosthog() {
  if (posthog.__loaded) {
    return;
  }
  posthog.init(process.env.REACT_APP_PUBLIC_POSTHOG_KEY, {
    api_host: process.env.REACT_APP_PUBLIC_POSTHOG_HOST,
    person_profiles: "identified_only",
  });
}

// Identify user with given properties in Posthog.
export function identifyUser(userId, userProperties) {
  initPosthog();
  posthog.identify(userId, userProperties);
}

// Capture event with given properties in Posthog.
export function captureEvent(eventName, properties = null) {
  initPosthog();
  posthog.capture(eventName, properties);
}

// Reset currently identified user in Posthog.
// Usually called upon user logout.
export function resetUserIdentification() {
  initPosthog();
  posthog.reset();
}
