import httpx   # an HTTP client library and dependency of Prefect
from prefect import flow, task


@task(retries=2)
def get_repo_info(repo_owner: str, repo_name: str):
    """Get info about a repo - will retry twice after failing"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info

# Define a simple flow to register
@flow(name="test-payload-flow")
async def test_payload_flow(payload):
    """This is a placeholder flow that will be replaced by the actual implementation in the deployment."""
    print(f"Processing accounts: {len(payload.get('accounts', []))} account(s)")
    print(f"Job ID: {payload.get('job_id')}")
    return {"status": "success", "message": "This is a placeholder. The actual implementation will run from the repository."}


@task
def get_contributors(repo_info: dict):
    """Get contributors for a repo"""
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contributors = response.json()
    return contributors


@flow(log_prints=True)
def repo_info(repo_owner: str = "PrefectHQ", repo_name: str = "prefect"):
    """
    Given a GitHub repository, logs the number of stargazers
    and contributors for that repo.
    """
    repo_info = get_repo_info(repo_owner, repo_name)
    print(f"Stars 🌠 : {repo_info['stargazers_count']}")

    contributors = get_contributors(repo_info)
    print(f"Number of contributors 👷: {len(contributors)}")


if __name__ == "__main__":
    repo_info()
