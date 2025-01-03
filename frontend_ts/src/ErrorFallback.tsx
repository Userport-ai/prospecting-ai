import { isRouteErrorResponse } from "react-router";
import { Button } from "@/components/ui/button";
import { FallbackProps } from "react-error-boundary";

// Fallback UI when an error occurs.
export const ErrorFallback: React.FC<FallbackProps> = ({
  error,
  resetErrorBoundary,
}) => {
  // Check if the error is a route error response.
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
  }

  // Check if the error is a standard Error object.
  if (error instanceof Error) {
    return (
      <div>
        <h1>Error</h1>
        <p>{error.message || "An unexpected error occurred."}</p>
        {/* TODO: Show tis error stack only in dev, never in production. */}
        {error.stack && (
          <>
            <p>The stack trace is:</p>
            <pre>{error.stack}</pre>
          </>
        )}
        <Button onClick={resetErrorBoundary}>Try again</Button>
      </div>
    );
  }

  // Fallback for unknown error types.
  return (
    <div>
      <h1>Unknown Error</h1>
      <p>An unknown error occurred. Please try again later.</p>
      <Button onClick={resetErrorBoundary}>Try again</Button>
    </div>
  );
};
