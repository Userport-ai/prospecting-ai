import AppLayout from "./AppLayout";
import { ErrorBoundary } from "react-error-boundary";
import { ErrorFallback } from "./ErrorFallBack";

// Error Logging Function
function logErrorToService(error, info) {
  // Log error to server.
}

function App() {
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
