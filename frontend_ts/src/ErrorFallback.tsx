import { Button } from "@/components/ui/button";
import { FallbackProps } from "react-error-boundary";

// Fallback UI when an error occurs.
export const ErrorFallback: React.FC<FallbackProps> = ({
  error,
  resetErrorBoundary,
}) => {
  const isDev = import.meta.env.MODE === "development"; // Determine the environment.

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 text-gray-800 px-6">
      <div className="bg-white rounded-lg shadow-md p-8 max-w-lg w-full border  border-gray-300">
        <h1 className="text-2xl font-semibold text-red-600">
          Oops! Something went wrong.
        </h1>
        <p className="mt-4 text-gray-600">
          {error instanceof Error
            ? error.message || "An unexpected error occurred."
            : "An unknown error occurred. Please try again later."}
        </p>

        {/* Show stack trace in development mode only */}
        {error instanceof Error && error.stack && isDev && (
          <div className="mt-6 p-4 bg-gray-100 rounded-lg overflow-auto max-h-64 border border-gray-300">
            <p className="text-sm font-mono text-gray-500">Stack trace:</p>
            <pre className="text-xs text-gray-600 whitespace-pre-wrap">
              {error.stack}
            </pre>
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <Button
            onClick={resetErrorBoundary}
            variant="outline"
            className="w-full"
          >
            Try Again
          </Button>
        </div>
      </div>
    </div>
  );
};
