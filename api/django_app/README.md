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

### Running Tests

All tests must be run from within the Docker container, not from your host machine. This is because the test environment relies on the Docker configuration to access the database and other dependencies.

To enter the Docker shell, use:
```bash
docker exec -it $(docker ps | grep userport-app | awk '{print $1}') bash
```

Once inside the Docker container, you can run the following test commands:

#### Dependency Graph Tests
```bash
# Run as a Django unit test
python manage.py test app.manual_tests.test_dependency_graph.DependencyGraphServiceTests

# Run as a standalone script
python manage.py shell < app/manual_tests/test_dependency_graph.py
```

#### API Tests
```bash
# Run as Django unit tests
python manage.py test app.manual_tests.test_column_dependencies_api.ColumnDependencyAPITests
python manage.py test app.manual_tests.test_column_dependencies_api.GenerateWithDependenciesTests

# Run as a standalone script (manual mode)
python manage.py shell < app/manual_tests/test_column_dependencies_api.py
```

#### E2E Tests
```bash
# Update token and entity IDs in the script first
python -m pytest app/manual_tests/e2e/test_custom_column_dependencies_api.py -v
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