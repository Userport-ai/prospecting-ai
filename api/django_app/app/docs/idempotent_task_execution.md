# Idempotent Task Execution Using Stored Callbacks

> Created by: Sowrabh
> 
> Created time: January 28, 2025 11:42 AM

# 

Our system has multiple tasks that:

1. Process some data in `execute()`.
2. Store raw results in BigQuery (e.g., `enrichment_raw_data`).
3. Send a final callback payload indicating success or failure.

We now also want **idempotency**: if a task runs a second time with the same `(job_id, account_id/lead_id)`, we should detect that it previously completed and simply resend the final callback rather than redoing the entire process.

---

## **The New Approach**

### **1. Storing Final Callbacks in `enrichment_callbacks`**

We are adding a separate BigQuery table, **`enrichment_callbacks`**, for storing each task’s final callback payload. The schema is simplified below:

```sql
CREATE TABLE `my-project.my_dataset.enrichment_callbacks` (
  job_id STRING NOT NULL,
  account_id STRING,
  lead_id STRING,
  status STRING,
  callback_payload STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

```

- **job_id**: Unique identifier for the job/run.
- **account_id**: Associated account if applicable.
- **lead_id**: Associated lead if applicable.
- **status**: Typically `"completed"` or `"failed"`.
- **callback_payload**: JSON string storing the entire final callback data.

We only insert a row if the task fully completes. That way, the table remains a clean record of completed runs.

---

### **2. Introducing `TaskResultManager`**

The class `TaskResultManager` handles reading and writing these final callbacks. It resides in `services/task_result_manager.py`:

```python
class TaskResultManager:
    def __init__(self):
# Sets up BigQuery client and references the enrichment_callbacks tableasync def get_result(self, job_id: str, account_id: str, lead_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Returns the most recent stored callback payload for (job_id, account_id, lead_id),
        or None if not found.
        """

    async def store_result(self, callback_payload: Dict[str, Any]) -> None:
        """
        Inserts a new row into enrichment_callbacks if payload.status == 'completed'.
        """

    async def resend_callback(self, callback_service, job_id: str, account_id: str, lead_id: str) -> None:
        """
        Fetches the stored callback payload and re-sends it using PaginatedCallbackService.
        """

```

---

### **3. Changes in `BaseTask`**

All tasks inherit from `BaseTask`, which now implements idempotency in `run_task()`:

```python
async def run_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    job_id = payload.get("job_id")
    lead_id = payload.get("lead_id")
    account_id = payload.get("account_id")

# Step 1: Check if a completed result already exists
    existing = await self.result_manager.get_result(job_id, account_id, lead_id)
    if existing and existing.get("status") == "completed":
# If found, skip reprocessing and just resend the existing callbackawait self.result_manager.resend_callback(self, job_id, account_id, lead_id)
        return existing

# Step 2: Run the task if no existing completed result
    result, summary = await self.execute(payload)

# If the task completed successfully, store the callback payloadif result and result.get("status") == "completed":
        await self.result_manager.store_result(result)

# Send the final callback (completed or failed)if result:
        await self.callback_service.paginated_service.send_callback(**result)

    return summary

```

---

### **4. `(result, summary)` Return Pattern**

Each task’s `execute()` now returns **two** dictionaries:

- **`result`**: The exact payload to store and eventually send as the final callback.
- **`summary`**: Additional analytics or metadata for the caller.

Example:

```python
async def execute(self, payload: Dict[str, Any]) -> (Dict[str, Any], Dict[str, Any]):
    if success:
        result = {
            "job_id": job_id,
            "account_id": account_id,
            "status": "completed",
            "enrichment_type": "company_info",
            "source": "jina_ai",
            "completion_percentage": 100,
            "processed_data": {
# ...
            }
        }
        summary = {
            "status": "completed",
            "job_id": job_id,
            "account_id": account_id,
            "extra_insights": { ... }
        }
        return result, summary
    else:
        return None, {
            "status": "failed",
            "job_id": job_id,
            "account_id": account_id,
            "error": "Something went wrong"
        }

```

`BaseTask.run_task()` decides whether to store `result` and re-send it if needed.

---

### **5. Task Examples**

### **`AccountEnhancementTask`**

**Before**

- End-of-task callback was sent inside `execute()`, returning separate data.

**Now**

- `execute()` builds the final callback in `result`:

```python
result = {
    "job_id": job_id,
    "account_id": account_id,
    "status": "completed",
    "enrichment_type": "company_info",
    "source": "jina_ai",
    "completion_percentage": 100,
    "processed_data": {
        "company_name": account_info.name,
        "employee_count": account_info.employee_count,
        ...
    }
}
summary = {
    "status": "completed",
    "job_id": job_id,
    "account_id": account_id,
    "total_accounts": total_accounts,
    ...
}
return result, summary

```

---

### **6. Storing and Resending**

- When `result.status == "completed"`, `BaseTask.run_task()` calls `store_result(result)` in `TaskResultManager`.
- On a rerun of the same `(job_id, account_id, lead_id)`, `get_result` returns the stored callback payload. We skip reprocessing and just call `resend_callback`.

---

### **7. Intermediate Callbacks**

If tasks need to send progress updates (e.g., 30%, 60%) or send failure updates, they can still do so:

```python
await callback_service.send_callback(
    job_id=job_id,
    account_id=account_id,
    status="processing",
    completion_percentage=30,
    ...
)

```

These aren’t stored as final results. Only the *last* completed callback is stored.

---

## **Summary of Benefits**

1. **Idempotency**
    
    Tasks can detect and reuse a stored “completed” callback for the same `(job_id, entity_id)`.
    
2. **Clean, Centralized Logic**
    
    `BaseTask.run_task()` now coordinates the entire process: it checks for previous results, stores new results, and resends them if needed.
    
3. **Consistent Callbacks**
    
    All tasks share the same final callback structure, making it simpler for other consumers to handle.
    
4. **Reduced Computation**
    
    We skip heavy reprocessing if the task was already completed.
    

---

## **Implementation Steps**

1. **Create the `enrichment_callbacks` Table**
    
    Make sure it has `job_id`, `account_id`, `lead_id`, `status`, `callback_payload`, `created_at`, and `updated_at`.
    
2. **Set Up `TaskResultManager`**
    
    In `services/task_result_manager.py`, implement `get_result`, `store_result`, and `resend_callback`.
    
3. **Refactor `BaseTask`**
    - Add `result_manager` in the constructor.
    - Modify `run_task()` to do the new check/store/resend flow.
4. **Update Each Task**
    - Return `(result, summary)` from `execute()`.
    - Ensure `result` is the final callback data (e.g., `job_id`, `account_id/lead_id`, `status`).
    - Remove the final `send_callback(...)` for the completed state, since `BaseTask` now handles it.
5. **Test**
    - Run tasks normally; confirm they store results in `enrichment_callbacks`.
    - Re-run tasks with the same `(job_id, account_id, lead_id)` to ensure they skip reprocessing and just resend the stored callback.