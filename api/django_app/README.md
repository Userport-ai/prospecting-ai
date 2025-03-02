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
   4. Make it executable: `chmod +x cloud-sql-proxy`
   5. Run `./cloud-sql-proxy --gcloud-auth omega-winter-431704-u5:us-central1:userport-pg --port 5433`
  `
3. Build Docker: `docker build -t userport-app:dev .`
4. Run the docker container using
```
sowrabh@Sowrabhs-MacBook-Pro django_app % docker run -it --rm \
    -p 8000:8000 \
    -v $(pwd)/secrets/service-account.json:/secrets/service-account.json \
    -v $(pwd):/app \
    --env-file .dev.env \
    userport-app:dev
```

### GKE logs

Add the following filters to GKE logs to filter out Health Check logs
```
-(textPayload=~".*GET /api/v2/health/.*")
-(textPayload=~".*/api/v2/health/status/ - Status 200")
-(textPayload=~".*/api/v2/health/ready/ - Status 200")
```

### Installation notes

For Mac OS using Python 3.13, we need to use: [1] uwsgi==2.0.27 and [2] psycopg2-binary==2.9.10 instead.
