import { isRouteErrorResponse } from "react-router";
import { Button } from "@/components/ui/button";

// Fallback UI when an error occurs.
export function ErrorFallback({ error, resetErrorBoundary }) {
  if (isRouteErrorResponse(error)) {
    return (
      <div>
        <h1>
          {error.status} {error.statusText}
        </h1>
        <p>{error.data}</p>
        <Button onClick={resetErrorBoundary}>Try again</Button>
      </div>
    );
  } else if (error instanceof Error) {
    return (
      <div>
        <h1>Error</h1>
        <p>{error.message}</p>
        <p>The stack trace is:</p>
        <pre>{error.stack}</pre>
        <Button onClick={resetErrorBoundary}>Try again</Button>
      </div>
    );
  } else {
    return <h1>Unknown Error</h1>;
  }
}
