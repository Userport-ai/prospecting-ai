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
        // Send message to service worker to get user state.
        const userFromStorage = await chrome.runtime.sendMessage({
          action: "fetch-user",
        });
        setUser(userFromStorage);
        setStateLoading(false);
      }
    }
    fetchUser();
  }, []);

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

  return (
    <Main
      linkedinProfileUrl={"https://www.linkedin.com/in/ranjith-v-85261219b/"}
      researchStatus={"complete"}
    />
  );
}

export default App;
