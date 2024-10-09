console.log("[content] loaded ");

let count = 0;

// Listener for click events on browser tab.
function registerClickListener(listener) {
  window.addEventListener("click", listener);
}

function countClicks() {
  // Do nothing for now.
}

export function init() {
  registerClickListener(countClicks);
}

init();
