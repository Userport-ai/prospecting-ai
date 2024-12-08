# Userport Chrome Extension

The extension will allow users to click it and fetch details about the profile by making calls to the backend.

We want to use React to easily build and maintain the extension UI.

Used https://hackernoon.com/how-to-create-a-chrome-extension-with-react as reference to create file structure and understand how extensions work.

We are using a custom build environment by following: https://create-react-app.dev/docs/deployment/#customizing-environment-variables-for-arbitrary-build-environments 

## Testing locally

1. First you need to setup the Userport Frontend and Backend locally:
    * Frontend: `npm start`. This will create a react server on port `3000`.
    * Backend: `flask --app app run --debug`. This will create the backend server on port `5000`.
2. Then you need to create a tunnel using ngrok so that the Backend API is accessible by the local Extension. Use `ngrok http http://127.0.0.1:5000` to point the local backend server.
3. Copy the created ngrok endpoint to `REACT_APP_API_HOSTNAME` env variable in the `.env.dev` file.
4. Run `npm run build:dev` to build the extension.
5. Load the built extension by going to `chrome:://extensions` and loading unpacked extension (point to created build folder locally).

### Deploying to production

Steps:
1. Build the production package using: `npm run build:prod`. Ensusre the manifest version in `manifests/manifest.prod.json` is higher than existing manifest version on Chrome Webstore.
2. Zip the created `build` folder.
3. Upload it to Chrome Webstore at https://chrome.google.com/webstore/devconsole/0554aeb6-ad99-4c8b-bfee-cd6e88275373/eblpjefkdhgnbemdannmkfpocddfffcm/edit/package.