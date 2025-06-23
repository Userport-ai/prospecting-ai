import AppLayout from "./AppLayout";
import { useAuthContext } from "./auth/AuthProvider";
import { Navigate } from "react-router";
import { Toaster } from "./components/ui/toaster";

function App() {
  const { firebaseUser } = useAuthContext();
  if (!firebaseUser) {
    // User is logged out.
    return <Navigate to="/login" />;
  }

  return (
    <div className="flex flex-col font-sans">
      <AppLayout />
      <Toaster />
    </div>
  );
}

export default App;
