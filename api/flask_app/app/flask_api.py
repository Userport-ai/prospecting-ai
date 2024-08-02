from flask import Blueprint, request, abort, app
import logging
from typing import List, Dict
from app.database import Database
from app.models import LeadResearchReport
from app.research_report import Researcher
from app.utils import Utils
from celery import shared_task

bp = Blueprint('api', __name__, url_prefix='/api')

logger = logging.getLogger()


@bp.route('/v1/lead_report', methods=['GET', 'POST'])
def lead_report():
    db = Database()

    if request.method == "POST":
        # Create research report.
        rp = Researcher(database=db)
        person_linkedin_url = request.form.get('linkedin_url')
        try:
            logging.info(
                f"Got request to start report for URL: {person_linkedin_url}")
            report_id: str = rp.create(person_linkedin_url=person_linkedin_url)
            fetch_search_results_in_background.delay(
                lead_research_report_id=report_id)

            return {
                "report_id": report_id,
                "linkedin_url": person_linkedin_url,
            }
        except Exception as e:
            print(e)
            abort(
                500, f"Failed to create report for LinkedIn URL: {person_linkedin_url}")

    elif request.method == "GET":
        # Fetch existing report.
        try:
            report: LeadResearchReport = db.get_lead_research_report(
                lead_research_report_id="66aa17d158f79392393414a6")
            return report.model_dump()
        except Exception as e:
            print(e)
            abort(500, "Failed to read report from database")

    abort(400, f"Invalid request method: {request.method}")


@bp.route('/v1/debug', methods=['GET'])
def debug():
    # Only used for debugging locally, do not call in production.
    report_id = request.args.get("lead_report_id")
    # process_search_results_in_background.delay(
    #     lead_research_report_id=report_id)
    aggregate_report_in_background.delay(lead_research_report_id=report_id)
    return {"status": "ok"}


@shared_task(acks_late=True)
def fetch_search_results_in_background(lead_research_report_id: str):
    """Start research in background Celery Task."""
    logger.info(
        f"Fetching search results for report ID: {lead_research_report_id}")

    r = Researcher(database=Database())
    try:
        r.fetch_search_results(lead_research_report_id=lead_research_report_id)
    except Exception as e:
        logger.exception(f"Ran into search results error: {e}")
        return

    logger.info(
        f"Done fetching search results for report ID: {lead_research_report_id}")

    # Now enqueue task to fetch content details.
    process_content_in_search_results_in_background.delay(
        lead_research_report_id=lead_research_report_id)


@shared_task(bind=True, acks_late=True)
def process_content_in_search_results_in_background(self, lead_research_report_id: str):
    max_retries = 2
    r = Researcher(database=Database())
    try:
        r.process_content_in_search_urls(
            lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Finished processing search ULRs for report: {lead_research_report_id}")
        aggregate_report_in_background.delay(
            lead_research_report_id=lead_research_report_id)
    except Exception as e:
        logger.exception(
            f"Error in processing search URLs for report: {lead_research_report_id} with retry count: {self.request.retries} details: {e}")

        if self.request.retries >= max_retries:
            # Done with retries, go to the next step.
            logger.info(
                "Done with retrying search results, moving to the next step.")
            aggregate_report_in_background.delay(
                lead_research_report_id=lead_research_report_id)
            return

        # Retry after 5 seconds.
        raise self.retry(exc=e, max_retries=max_retries, countdown=5)


@shared_task(bind=True, acks_late=True)
def aggregate_report_in_background(self, lead_research_report_id: str):
    max_retries = 2
    r = Researcher(database=Database())
    try:
        r.aggregate(lead_research_report_id=lead_research_report_id)
    except Exception as e:
        logger.exception(
            f"Error in aggregating research report: {lead_research_report_id} with details: {e}")
        if self.request.retries >= max_retries:
            # Done with retries, mark task as failed.
            setFields = {"status": LeadResearchReport.Status.FAILED_WITH_ERRORS,
                         "last_updated_date": Utils.create_utc_time_now()}
            r.database.update_lead_research_report(lead_research_report_id=lead_research_report_id,
                                                   setFields=setFields)

        # Retry after 5 seconds.
        raise self.retry(exc=e, max_retries=max_retries, countdown=5)
