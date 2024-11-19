import logging
import random
import json
import time
from typing import List
from itertools import chain
from celery import shared_task, chord
from celery.exceptions import SoftTimeLimitExceeded
from app.database import Database
from app.models import LeadResearchReport, LinkedInActivity
from app.research_report import Researcher
from app.linkedin_scraper import InvalidLeadLinkedInUrlException, LeadLinkedInProfileNotFoundException
from app.metrics import Metrics


logger = logging.getLogger()


@shared_task(bind=True, acks_late=True)
def fetch_lead_info_orchestrator(self, lead_research_report_id: str):
    """Main Orchestrator that routes the given report to the correct Celery task."""
    logger.info(
        f"Orchestrator called for lead report ID: {lead_research_report_id}")
    database = Database()

    report_status: LeadResearchReport.Status = None
    report: LeadResearchReport = None
    try:
        report = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection={"status": 1, "status_before_failure": 1, "user_id": 1})
        report_status: LeadResearchReport.Status = report.status if report.status != LeadResearchReport.Status.FAILED_WITH_ERRORS else report.status_before_failure
        user_id: str = report.user_id
        logger.info(
            f"Current report status: {report_status} for report ID: {lead_research_report_id}")
        if report_status == LeadResearchReport.Status.NEW:
            logger.info(
                f"Report just created with ID: {lead_research_report_id}, enrich lead profile next.")
            enrich_lead_info_in_background.delay(
                user_id=user_id, lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.BASIC_PROFILE_FETCHED:
            logger.info(
                f"Basic profile fetched for {lead_research_report_id}, fetch search results next.")
            fetch_search_results_in_background.delay(
                user_id=user_id, lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED:
            logger.info(
                f"Fetched search results for {lead_research_report_id}, process content in search results next.")
            process_content_in_search_results_and_activities_in_background.delay(
                user_id=user_id, lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.CONTENT_PROCESSING_COMPLETE:
            logger.info(
                f"Processed content in search results for {lead_research_report_id}, aggregate report results next.")
            aggregate_report_in_background.delay(
                user_id=user_id, lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE:
            logger.info(
                f"Lead Report aggregation complete for {lead_research_report_id}, select email template next.")
            choose_template_and_create_emails_in_background.delay(
                user_id=user_id, lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.COMPLETE:
            logger.info(
                f"Lead research complete for {lead_research_report_id}, nothing more to do here.")

    except Exception as e:
        user_id = report.user_id if report else None
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="fetch_lead_info_orchestrator", status_before_failure=report_status)


@shared_task(bind=True, acks_late=True)
def enrich_lead_info_in_background(self, user_id: str, lead_research_report_id: str):
    """Enrich lead with name, company name, role titles in the given Lead Report."""
    logger.info(
        f"Creating lead profile for Lead Research report ID: {lead_research_report_id}")
    database = Database()
    try:
        research_request_type: LeadResearchReport.ResearchRequestType = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection={"research_request_type": 1}).research_request_type

        rp = Researcher(database=database)
        rp.enrich_lead_info(
            lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Enriched lead successfully in report ID: {lead_research_report_id} for user ID: {user_id}.")

        if research_request_type == LeadResearchReport.ResearchRequestType.LINKEDIN_ONLY:
            # No need to fetch web search results. Directly process stored activities next.
            process_content_in_search_results_and_activities_in_background.delay(
                user_id=user_id, lead_research_report_id=lead_research_report_id)
        else:
            # Fetch Search Results associated with the given leads.
            fetch_search_results_in_background.delay(
                user_id=user_id, lead_research_report_id=lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_lead_info_enriched", properties={
            "report_id": lead_research_report_id})
    except InvalidLeadLinkedInUrlException as e:
        logger.exception(
            f"Lead LinkedIn URL is invalid in Lead Report ID: {lead_research_report_id} and user ID: {user_id}")
        _update_status_as_failed(database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                 e=e, event_name="invalid_lead_linkedin_url", task_name="enrich_lead_info", status_before_failure=LeadResearchReport.Status.NEW)
        return
    except LeadLinkedInProfileNotFoundException as e:
        logger.exception(
            f"Lead Profile not found for Lead report ID: {lead_research_report_id} and user ID: {user_id}")
        _update_status_as_failed(database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                 e=e, event_name="lead_profile_not_found", task_name="enrich_lead_info", status_before_failure=LeadResearchReport.Status.NEW)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_lead_linkedin_url_not_found",
                          properties={"report_id": lead_research_report_id})
        return
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="enrich_lead_info", status_before_failure=LeadResearchReport.Status.NEW)


@shared_task(bind=True, acks_late=True)
def fetch_search_results_in_background(self, user_id: str, lead_research_report_id: str):
    """Fetch search results for given lead in background."""
    logger.info(
        f"Start fetching search URLs for lead report ID: {lead_research_report_id} for user ID: {user_id}")
    database = Database()
    try:
        start_time = time.time()
        r = Researcher(database=database)
        r.fetch_search_results(lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Completed fetching search results for lead report ID: {lead_research_report_id} for user ID: {user_id}")

        # Process search URLs contents next.
        process_content_in_search_results_and_activities_in_background.delay(
            user_id=user_id, lead_research_report_id=lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_search_results_fetched", properties={
            "report_id": lead_research_report_id, "time_taken_seconds": time.time() - start_time})
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="fetch_search_results", status_before_failure=LeadResearchReport.Status.BASIC_PROFILE_FETCHED)


@shared_task(bind=True, acks_late=True)
def process_content_in_search_results_and_activities_in_background(self, user_id: str, lead_research_report_id: str):
    """Processes URLs in search result and activities s in background."""
    logger.info(
        f"Start content processing from search URLs and activities in lead report: {lead_research_report_id} for user ID: {user_id}")
    database = Database()
    try:
        research_report: LeadResearchReport = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)
        # Split search URLs into batches depending on the number of concurrent processes in a worker.
        # Note: This concurrency value must match the concurreny passed during app intialization.
        # TODO: Make this read the concurrency value from the celery start command line argument.
        concurrency = 12
        parallel_workers = []
        total_web_search_urls_to_process = 0
        total_linkedin_activities_to_process = 0

        # Create batches for Web search result URLs if present.
        if research_report.web_search_results:
            search_results_list: List[LeadResearchReport.WebSearchResults.Result] = research_report.web_search_results.results
            total_web_search_urls_to_process: int = research_report.web_search_results.num_results
            batch_size = int(total_web_search_urls_to_process/concurrency) + \
                (0 if total_web_search_urls_to_process % concurrency == 0 else 1)
            logger.info(
                f"Splitting processing of web search URLS: {total_web_search_urls_to_process} into {concurrency} workers which will each handle at max {batch_size} URLs for processing for lead report: {lead_research_report_id} and user ID: {user_id}.")

            for i in range(concurrency):
                start_idx = i*batch_size
                end_idx = start_idx + batch_size
                batch: List[LeadResearchReport.WebSearchResults.Result] = search_results_list[start_idx: end_idx]
                logger.info(
                    f"Web search task num: {i} has batch size: {len(batch)} in report ID: {lead_research_report_id} for user ID: {user_id}")
                work = process_content_in_search_results_batch_in_background.s(
                    i, user_id, lead_research_report_id, [r.model_dump_json() for r in batch])
                parallel_workers.append(work)
                if end_idx >= total_web_search_urls_to_process:
                    break
            logger.info(
                f"Num web search result batches: {len(parallel_workers)} in report ID: {lead_research_report_id} for user ID: {user_id}")

        # Create batches for activity IDs if any.
        if research_report.linkedin_activity_info and research_report.linkedin_activity_info.activity_ref_ids:
            activities_ids_to_process: List[str] = research_report.linkedin_activity_info.activity_ref_ids
            total_linkedin_activities_to_process = len(
                research_report.linkedin_activity_info.activity_ref_ids)
            batch_size = int(total_linkedin_activities_to_process/concurrency) + \
                (0 if total_linkedin_activities_to_process %
                 concurrency == 0 else 1)
            logger.info(
                f"Splitting processing of activity IDs: {total_linkedin_activities_to_process} into {concurrency} workers which will each handle at max {batch_size} URLs for processing for lead report: {lead_research_report_id} and user ID: {user_id}.")
            num_activity_batches = 0
            for i in range(concurrency):
                start_idx = i*batch_size
                end_idx = start_idx + batch_size
                batch = activities_ids_to_process[start_idx:end_idx]
                logger.info(
                    f"Activity processing task num: {i} has batch size: {len(batch)} in report ID: {lead_research_report_id} for user ID: {user_id}")
                work = process_activities_batch_in_background.s(
                    i, user_id, lead_research_report_id, batch)
                parallel_workers.append(work)
                num_activity_batches += 1
                if end_idx >= total_linkedin_activities_to_process:
                    break
            logger.info(
                f"Num activity batches: {num_activity_batches} in report ID: {lead_research_report_id} for user ID: {user_id}")

        # Define task that will aggregate results of parallel workers at the end.
        aggregation_work = aggregate_processed_content_results_in_background.s(
            user_id, lead_research_report_id)
        aggregation_error_callback = on_process_content_results_batch_error.s(
            user_id, lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_content_start_processing", properties={
            "report_id": lead_research_report_id, "start_time": time.time(), "total_web_search_urls": total_web_search_urls_to_process, "total_linkedin_activities": total_linkedin_activities_to_process,  "concurrency": concurrency})

        # Start processing.
        chord(parallel_workers)(
            aggregation_work.on_error(aggregation_error_callback))

    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name="process_content_in_search_results", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(bind=True, acks_late=True, ignore_result=False)
def process_content_in_search_results_batch_in_background(self, batch_num: int, user_id: str, lead_research_report_id: str, search_results_batch_json: List[str]):
    """Process batch of given Search Result URLs and returns a list of URLs that failed to process."""
    search_results_batch = []
    for r_json in search_results_batch_json:
        search_result = LeadResearchReport.WebSearchResults.Result(
            **json.loads(r_json))
        search_results_batch.append(search_result)

    logger.info(
        f"In batch number: {batch_num} for user ID: {user_id}, got {len(search_results_batch)} search URLs to process for lead report")
    database = Database()
    try:
        r = Researcher(database=database)
        failed_urls: List[str] = r.process_content_in_search_urls(
            lead_research_report_id=lead_research_report_id, search_results_batch=search_results_batch, task_num=batch_num)
        logger.info(
            f"Completed search URLs processing for lead report: {lead_research_report_id} in batch number: {batch_num} for user ID: {user_id}")
        return failed_urls
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name=f"process_content_in_search_results_batch_{batch_num}", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(bind=True, acks_late=True, ignore_result=False)
def process_activities_batch_in_background(self, batch_num: int, user_id: str, lead_research_report_id: str, activity_ids: List[str]):
    """Process given batch of LinkedIn Activities for given lead in background and return Activity IDs that failed to process."""
    logger.info(
        f"Start processing LinkedIn activity in batch num: {batch_num} for num activities: {len(activity_ids)} in report ID: {lead_research_report_id}")
    database = Database()
    try:
        r = Researcher(database=database)
        r.process_linkedin_activities(
            lead_research_report_id=lead_research_report_id, activity_ids=activity_ids, task_num=batch_num)
        logger.info(
            f"Completed Activities processing in batch number: {batch_num} for lead report ID: {lead_research_report_id} and user ID: {user_id}")

        # We are returning Empty list so that the API is compatible with other parallel worker that returns a list of failed web search URLs.
        # TODO: Return failed activities in the form of a message container that can hold both failed activities and failed web URLs.
        return []
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name=f"process_activities_batch_{batch_num}", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(bind=True, acks_late=True)
def aggregate_processed_content_results_in_background(self, failed_urls_list: List[List[str]], user_id: str, lead_research_report_id: str):
    """Aggregate processing of search results and activity results from each worker task that worked on a batch."""
    logger.info(
        f"Start aggregating search results for lead report ID: {lead_research_report_id} for user ID: {user_id}")
    database = Database()
    try:
        # Update status and failed URLs in database.
        flattened_urls_list = list(chain.from_iterable(failed_urls_list))
        setFields = {
            "status": LeadResearchReport.Status.CONTENT_PROCESSING_COMPLETE,
            "content_parsing_failed_urls": flattened_urls_list,
        }
        database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)

        logger.info(
            f"Completed aggregation of processed content results for lead report ID: {lead_research_report_id} for user ID: {user_id}")

        # Aggregate Report next.
        aggregate_report_in_background.delay(
            user_id=user_id, lead_research_report_id=lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_all_content_results_processed", properties={
            "report_id": lead_research_report_id, "end_time": time.time(), "failed_urls": flattened_urls_list, "num_failed_urls": len(flattened_urls_list)})
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name=f"aggregate_processed_search_results", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(acks_late=True)
def on_process_content_results_batch_error(request, exc, traceback, user_id: str, lead_research_report_id: str):
    """Handler in any of the search results or activities processing tasks timeout due to hard timeout limit.

    Ideally this should be caught by SoftTimeLimitExceeded exception but that doesn't seem to work once the Web scraper code starts
    executing likely because it use libraries that are not written in Python (e.g. langchain) and aren't able to handle the SIGUSR1 signal
    at the time of soft deletion. If the soft deletion signal is not caught at the right time, it is never raised again and that is why
    we are running into hard time limit.

    If we switch to gevent pool in the future, it won't even enforce hard limit since our tasks are synchonrous and thus blocking. 
    Long term solution is to implement a Celery task that periodically monitors executing task status and kills them if they are taking too long.

    Reference: https://docs.celeryq.dev/en/4.4.1/userguide/canvas.html#error-handling.
    """
    _update_status_as_failed(database=Database(), user_id=user_id, lead_research_report_id=lead_research_report_id,
                             e=f'Celery Task {request.id} raised error: {exc}', event_name="process_content_task_limit_exceeded", task_name="on_process_content_in_search_results_batch_error", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(bind=True, acks_late=True)
def aggregate_report_in_background(self, user_id: str, lead_research_report_id: str):
    """Create a research report in background."""
    logger.info(
        f"Start lead research report aggregation for report ID: {lead_research_report_id} for user ID: {user_id}")
    database = Database()
    try:
        research_request_type: LeadResearchReport.ResearchRequestType = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection={"research_request_type": 1}).research_request_type

        r = Researcher(database=database)
        if research_request_type == LeadResearchReport.ResearchRequestType.LINKEDIN_ONLY:
            # Aggregate only LinkedIn activities.
            r.aggregate_only_linkedin_activities(
                lead_research_report_id=lead_research_report_id)
        else:
            # Aggregate linkedin activities and web content.
            r.aggregate(lead_research_report_id=lead_research_report_id)

        logger.info(
            f"Completed aggregation of research report complete for report ID: {lead_research_report_id} for user ID: {user_id}")

        # Select email outreach template next.
        choose_template_and_create_emails_in_background.delay(
            user_id=user_id, lead_research_report_id=lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_details_created", properties={
            "report_id": lead_research_report_id})
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="aggregate_report", status_before_failure=LeadResearchReport.Status.CONTENT_PROCESSING_COMPLETE)


@shared_task(bind=True, acks_late=True)
def choose_template_and_create_emails_in_background(self, user_id: str, lead_research_report_id: str):
    """Selects outreach template and creates personalized emails in background."""
    logger.info(
        f"Start template selection and email creation for report ID: {lead_research_report_id}")
    database = Database()
    try:
        r = Researcher(database=database)
        r.choose_template_and_create_emails(
            lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Completed outreach template Selection and Email creation complete in background for report ID: {lead_research_report_id}")

        # Send event.
        m = Metrics()
        m.capture(user_id=user_id, event_name="report_personalized_emails_created", properties={
            "report_id": lead_research_report_id})

        # Send event with total cost for lead generation.
        lead_report: LeadResearchReport = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection={"content_parsing_total_tokens_used": 1, "personalized_outreach_messages": {"total_tokens_used": 1}})
        total_cost: float = 0.0
        content_processing_cost: float = 0.0
        personalized_emails_generation_cost: float = 0.0
        insights_generation_cost: float = 0.0
        if lead_report.content_parsing_total_tokens_used:
            content_processing_cost = lead_report.content_parsing_total_tokens_used.total_cost_in_usd
            total_cost += content_processing_cost
        if lead_report.personalized_outreach_messages and lead_report.personalized_outreach_messages.total_tokens_used:
            personalized_emails_generation_cost = lead_report.personalized_outreach_messages.total_tokens_used.total_cost_in_usd
            total_cost += personalized_emails_generation_cost
        if lead_report.insights and lead_report.insights.total_tokens_used:
            insights_generation_cost = lead_report.insights.total_tokens_used.total_cost_in_usd
            total_cost += insights_generation_cost
        m.capture(user_id=user_id, event_name="report_generation_cost_in_usd", properties={"report_id": lead_research_report_id, "total_cost_in_usd": total_cost, "content_processing_cost_in_usd":
                  content_processing_cost, "insights_generation_cost_in_usd": insights_generation_cost, "personalized_emails_generation_cost_in_usd": personalized_emails_generation_cost})
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name="choose_template_and_create_emails", status_before_failure=LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE)

###############
# Helper Methods
###############


def _update_status_as_failed(database: Database, user_id: str, lead_research_report_id: str, e: Exception, event_name: str, task_name: str, status_before_failure: LeadResearchReport.Status):
    """Helper to clean up report state upon task failure."""

    # Update status as failed and register last status.
    setFields = {
        "status": LeadResearchReport.Status.FAILED_WITH_ERRORS,
        "status_before_failure": status_before_failure,
    }
    database.update_lead_research_report(lead_research_report_id=lead_research_report_id,
                                         setFields=setFields)

    # Send event.
    Metrics().capture(user_id=user_id, event_name=event_name, properties={
        "report_id": lead_research_report_id, "status_before_failure": status_before_failure, "task_name": task_name, "error": str(e)})


def shared_task_exception_handler(shared_task_obj, database: Database, user_id: str, lead_research_report_id: str, e: Exception, task_name: str, status_before_failure: LeadResearchReport.Status):
    """Helper to handle the exception that occured in given shared task instance."""
    if isinstance(e, SoftTimeLimitExceeded):
        logger.exception(
            f"SoftTimeLimit Exception in Task: {task_name} with report ID: {lead_research_report_id} for user ID: {user_id} with status_before_failure: {status_before_failure} for  with error: {e}")

        _update_status_as_failed(database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                 e=e, event_name="celery_task_soft_time_limit_exceeded", task_name=task_name, status_before_failure=status_before_failure)
        return

    # We retry 3 times at max, so 4 times in total.
    max_retries = 3

    if shared_task_obj.request.retries >= max_retries:
        # Done with retries, go to the next step.
        logger.exception(
            f"Retries exhausted for request: {task_name} with report ID: {lead_research_report_id} with error: {e}")

        # Done with retries, update status as failed and register last status.
        _update_status_as_failed(database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                 e=e, event_name="report_research_failed", task_name=task_name, status_before_failure=status_before_failure)

        raise ValueError(
            f"Retries exhaused for request: {task_name} with report ID: {lead_research_report_id} with error: {e}")

    # Retry after delay. Adding randomness because we saw some concurrent RMW transactions fail on retry because all tasks were retrying at the same time.
    retry_interval_seconds: int = 10 + random.randint(0, 10)
    logger.exception(
        f"Error in {task_name} for report ID: {lead_research_report_id} with retry count: {shared_task_obj.request.retries}, error details: {e}")
    raise shared_task_obj.retry(
        exc=e, max_retries=max_retries, countdown=retry_interval_seconds)
