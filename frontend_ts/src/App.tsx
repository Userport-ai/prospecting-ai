import AppLayout from "./AppLayout";
import { ErrorBoundary } from "react-error-boundary";;
import { useAuthContext } from "./auth/AuthProvider";
import { Navigate } from "react-router";
import { ErrorInfo } from "react";
import { ErrorFallback } from "./ErrorFallback";

// Error Logging Function
function logErrorToService(error: Error, info: ErrorInfo) {
  // Log error to server.
}

function App() {
  const user = useAuthContext();
  if (!user) {
    // User is logged out.
    return <Navigate to="/login" />;
  }

  return (
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={logErrorToService}
    >
      <div className="flex flex-col min-h-screen font-inter">
        <AppLayout />
      </div>
    </ErrorBoundary>
  );
}

export default App;
