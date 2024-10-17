# Userport Chrome Extension

The extension will allow users to click it and fetch details about the profile by making calls to the backend.

We want to use React to easily build and maintain the extension UI.

Used https://hackernoon.com/how-to-create-a-chrome-extension-with-react as reference to create file structure and understand how extensions work.


## Running locally

To make UI changes, you can run `npm start` and access the Popup App like a normal React App in the browser.

To test extension changes, run `npm run build` to create a build and then refresh the extension in `chrome:://extensions` (with Developer Mode enabled).

To ensure you can make `fetch` requests to local Flask server, you need to use `ngrok` to setup HTTPS interface for server running on `localhost:5000`.

Use the command: `ngrok http http://127.0.0.1:5000` to do so.

## Building extension

Since local testing extension also requires you to build it via `npm run build`, the app uses `.env.production` file by default.

When actually building for production, make sure to update `.env.production` to reflect the actual production env before starting the build.

When building for local, you can rename `.env.local.production.local` to `.env.production.local` (so that it superceded `.env.production`) but change it back before building for production.