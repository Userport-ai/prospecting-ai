# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)

## Other Commands

### Run Flask, Celery and Redis locally.

We need to run Flask App with Celery worker using Redis as backend.

These commands should be run from `flask_app` directory not the `app` directory.

Flask: `flask --app app run --debug`

In a shell with virtual env activated and Redis installed (`pip install Redis`):

Start Celery worker: `celery -A app.make_celery worker --loglevel INFO`

Start Local redis server: `redis-server`

Purge unacked tasks in Celery Task queue: `celery -A app.make_celery purge`

Retry management in Celery Task example: https://stackoverflow.com/questions/67968018/how-to-execute-some-code-at-last-retry-of-a-celery-task


## Docker Commands

We want to specify platform as linux/amd64 since we are usually building these images on Mac M1s which by default select linux/arm64 as the target platform and this causes Deployment on Cloud to fail.

Building Frontend for GKE Deployment in production: `docker build --platform linux/amd64 -f Dockerfile.frontend  --build-arg GIT_COMMIT=$(git log -1 --format=%h) -t userport/frontend .`

Building Backend for GKE Deployment in production: `docker build --platform linux/amd64 -f Dockerfile.backend  --build-arg GIT_COMMIT=$(git log -1 --format=%h) -t userport/backend .`

Docker CMD for running Flask server: `CMD ["gunicorn","--bind", "0.0.0.0:5000", "app:create_app"]`

Docker CMD for running Celery Worker: `CMD ["celery", "-A", "app.make_celery worker", "--loglevel=INFO"]`

Get list of local images: `docker image list`

Tag a local image with a new name (usually before push to registry): `docker tag <local image name or image ID> <new image name>`

Delete unused Docker images locally: `docker system prune -a` 

# Kubernetes Commands

[Reference doc](https://cloud.google.com/kubernetes-engine/docs/how-to/cluster-access-for-kubectl#install_kubectl)

Check path of kubectl binary to ensure its the one inside Google Cloud SDK: `which kubectl`

Get contexts (contains a cluster, a user and namespace) that kubectl can connect to: `kubectl config view`

To get the default context that kubctl connects to: `kubectl config current-context`

Create a GKE deployment: `kubectl apply -f <deployment file>`

Get detailed information abotu GKE deployment: `kubectl describe deployment <deployment name>`

Details of installed components in Google Cloud SDK: `gcloud info`


## GKE Debugging

To view all pods in deployment, their status and logs from failures if any.

Get all pods deployed: `kubectl get pods`

Get log from chosen pod: `kubectl logs <Pod Name>`

Stackoverflow links to help debug architecture related issues:
1. https://stackoverflow.com/questions/77766805/aws-batch-run-ecr-repository-error-exec-usr-local-bin-python3-exec-format-err
2. Layer already exists: https://stackoverflow.com/questions/48188268/docker-push-seems-not-to-update-image-layer-already-exists. I saw this problem too that prevented the app from running in the Cloud even after it was built for amd64 locally. Somehow the Cloud image was caching some layers that decided the platform of the image and that never changed even though I pushed new amd64 images multiple times. The solution I used was to delete the entire repository of the remote registry and start over with a fresh repository. Then my image upload resulted in a successful container run. This post talks about how maybe a fix to this problem may be to retag the new image, maybe we will try it out in the future.