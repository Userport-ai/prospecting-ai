import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

// Set up MockServiceWorker; see https://mswjs.io/docs/integrations/browser
export const worker = setupWorker(...handlers);
