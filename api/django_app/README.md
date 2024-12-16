## Get started

1. Build the docker container using
```
sowrabh@Sowrabhs-MacBook-Pro django_app % docker build -t userport-app:dev .
```
2. Update `.dev.env` file in `api/django_app/.dev.env` with the latest credentials
3. Install and run `cloud-sql-proxy` using the right credentials.
   1. First install gcloud sdk from [here](https://cloud.google.com/sdk/docs/install)
   2. Run `gcloud auth login` and authenticate
   3. Install `cloud-sql-proxy` using `curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.2/cloud-sql-proxy.darwin.arm64`
   3. Run `./cloud-sql-proxy --gcloud-auth omega-winter-431704-u5:us-central1:userport-pg --port 5433`
  `
4. Run the docker container using
```
sowrabh@Sowrabhs-MacBook-Pro django_app % docker run -it --rm \
    -p 8000:8000 \
    -v $(pwd):/app \
    --env-file .dev.env \
    userport-app:dev
```
