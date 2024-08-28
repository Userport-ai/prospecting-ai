## Frontend

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

## Backend

### Run Flask, Celery and Redis locally.

We need to run Flask App with Celery worker using Redis as backend.

These commands should be run from `flask_app` directory not the `app` directory.

Flask: `flask --app app run --debug`

In a shell with virtual env activated and Redis installed (`pip install Redis`):

Start Celery worker: `celery -A app.make_celery worker --loglevel INFO`

Start Local redis server: `redis-server`

Purge unacked tasks in Celery Task queue: `celery -A app.make_celery purge`

Retry management in Celery Task example: https://stackoverflow.com/questions/67968018/how-to-execute-some-code-at-last-retry-of-a-celery-task

Create Flower Web app to monitor Celery: `celery -A app.make_celery flower --conf=./app/flowerconfig.py --port=8080`

Gunicorn server: `gunicorn -b localhost:5000 -c "./app/gunicorn.conf.py" "app:create_app()"`

## Docker Commands

We want to specify platform as linux/amd64 since we are usually building these images on Mac M1s which by default select linux/arm64 as the target platform and this causes Deployment on Cloud to fail.

Building Frontend for GKE Deployment in production: `docker build --platform linux/amd64 -f Dockerfile.frontend  --build-arg GIT_COMMIT=$(git log -1 --format=%h) -t userport/frontend .`

Building Backend for GKE Deployment in production: `docker build --platform linux/amd64 -f Dockerfile.backend  --build-arg GIT_COMMIT=$(git log -1 --format=%h) -t userport/backend .`

Docker CMD for running Flask server: `CMD ["gunicorn","--bind", "0.0.0.0:5000", "app:create_app"]`

Docker CMD for running Celery Worker: `CMD ["celery", "-A", "app.make_celery worker", "--loglevel=INFO"]`

Get list of local images: `docker image list`

Tag a local image with a new name (usually before push to registry): `docker tag <local image name or image ID> <new image name>`

Gcloud authentication (needed to do Docker pushes, use kubectl commands etc.): `gcloud auth login`
Push an image to GCP Artifact registry: `docker push <new image name with registry path>`

Delete unused Docker images locally: `docker system prune -a` 

# Kubernetes Commands

[Reference doc](https://cloud.google.com/kubernetes-engine/docs/how-to/cluster-access-for-kubectl#install_kubectl)

Check path of kubectl binary to ensure its the one inside Google Cloud SDK: `which kubectl`

Get contexts (contains a cluster, a user and namespace) that kubectl can connect to: `kubectl config view`

To get the default context that kubctl connects to: `kubectl config current-context`

Create a GKE deployment: `kubectl apply -f <deployment file>`

Deploy backend, celery worker and Flower at the same version to be safe.
Use `kubectl apply -f manifests/flask-deployment.yaml,manifests/celery-worker-deployment.yaml,manifests/flower-deployment.yaml`

Get deployment name in GKE: `kubectl get deployments`

Get detailed information about GKE deployment: `kubectl describe deployment <deployment name>`

Rollback deployment: `kubectl rollout undo deployment/<deployment name>`

Replace a deployment resource (sometimes K8s does not pick up changes correctly): `kubectl replace -f <deployment file>`

Delete a pod: `kubectl delete pod <pod name>`

Delete a service: `kubectl delete service <service name>`

Delete a deployment: `kubectl delete deployment <service name>`

## Updating Deployments

Reference: https://kubernetes.io/docs/tutorials/kubernetes-basics/update/update-intro/

CheatSheet for updating resources: https://kubernetes.io/docs/reference/kubectl/quick-reference/#updating-resources. It has rollout undo commands also.

Use this command to check Image IDs of each pod: `kubectl describe pods`

Update the manifest file with the new version and then run `kubectl apply -f <manifest file>`.
Same command for creation and updation and version of prod build tracked in git.

Get status of deployment rollout: `kubectl rollout status deployment/<deployment name>`

Restart rollout of deployment. Used when you need to update something like Secrets or Config maps or when app is in bad state and you want to restart your pod to get it back to healthy: `kubectl rollout restart deployment/<deployment name>`

Details of installed components in Google Cloud SDK: `gcloud info`


## GKE Debugging

To view all pods in deployment, their status and logs from failures if any.

Get all pods deployed: `kubectl get pods`

Get log from chosen pod: `kubectl logs <Pod Name>`

Describe deployment details: `kubectl describe deployment <deployment name>`

Get current ingress details: `kubectl get ingress`

Check the status of Google Managed SSL Certificate Provisioning Status (takes around 30 mins to provision): `kubectl describe managedcertificate <Managed certificate name>`

Delete managed Certificate instructions: `kubectl delete -f <manifest file of manged cert>`

Delete External Static IP address for load balancer (hope we don't need to do this): `gcloud compute addresses delete <Static IP Name>`

Stackoverflow links to help debug architecture related issues:
1. https://stackoverflow.com/questions/77766805/aws-batch-run-ecr-repository-error-exec-usr-local-bin-python3-exec-format-err
2. Layer already exists: https://stackoverflow.com/questions/48188268/docker-push-seems-not-to-update-image-layer-already-exists. I saw this problem too that prevented the app from running in the Cloud even after it was built for amd64 locally. Somehow the Cloud image was caching some layers that decided the platform of the image and that never changed even though I pushed new amd64 images multiple times. The solution I used was to delete the entire repository of the remote registry and start over with a fresh repository. Then my image upload resulted in a successful container run. This post talks about how maybe a fix to this problem may be to retag the new image, maybe we will try it out in the future.

## Gcloud commands

List In Use static external IP addresses: `gcloud compute addresses list`