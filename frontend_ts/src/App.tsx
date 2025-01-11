import AppLayout from "./AppLayout";
import { useAuthContext } from "./auth/AuthProvider";
import { Navigate } from "react-router";

function App() {
  const { firebaseUser } = useAuthContext();
  if (!firebaseUser) {
    // User is logged out.
    return <Navigate to="/login" />;
  }

  return (
    <div className="flex flex-col min-h-screen font-inter">
      <AppLayout />
    </div>
  );
}

export default App;
