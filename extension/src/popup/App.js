/*global chrome*/
import { useEffect, useState } from "react";
import "./App.css";
import Login from "./login";
import Main from "./main";

// Main component of Popup App.
function App() {
  const [user, setUser] = useState(null);
  const [stateLoading, setStateLoading] = useState(true);
  useEffect(() => {
    async function fetchUser() {
      // Chrome runtime exists only when called inside extension.
      if (chrome.runtime) {
        // Send message to service worker to get user.
        const gotUser = await chrome.runtime.sendMessage({
          action: "fetch-user",
        });
        setUser(gotUser);
        setStateLoading(false);
      }
    }
    fetchUser();
  }, []);

  // User has chosen to log out.
  async function handleLogoutClick() {
    // Chrome runtime exists only when called inside extension.
    if (chrome.runtime) {
      const success = await chrome.runtime.sendMessage({
        action: "logout-user",
      });
      if (success) {
        setUser(null);
      }
    }
  }

  if (stateLoading) {
    // Return nothing since everything is still loading.
    return <div></div>;
  }

  if (user === null) {
    return (
      <div className="App">
        <Login />
      </div>
    );
  }

  return <Main handleLogout={handleLogoutClick} />;
}

export default App;
