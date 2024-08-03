from flask import Blueprint, request, jsonify
import logging
from enum import Enum
from typing import Optional
from celery import shared_task
from pydantic import BaseModel, Field, field_validator
from app.database import Database
from app.models import LeadResearchReport
from app.research_report import Researcher
from app.utils import Utils
from app.linkedin_scraper import LinkedInScraper

bp = Blueprint('api', __name__, url_prefix='/api')

logger = logging.getLogger()


class ResponseStatus(str, Enum):
    """Enum representing success or error status in API responses."""
    SUCCESS = "success"
    ERROR = "error"


class ErrorDetails(BaseModel):
    """Details of Error response."""
    status: str = Field(...,
                        description="Status (error) of the response.")
    status_code: int = Field(...,
                             description="Status code associated with error.")
    message: str = Field(..., description="Message associated with error.")

    @field_validator('status')
    @classmethod
    def status_must_be_error(cls, v: str) -> str:
        if v != ResponseStatus.ERROR.value:
            raise ValueError(f'Expected error status, got: {v}')
        return v


class APIException(Exception):
    """Class to create JSON API responses when an exception is encountered."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code: int = status_code
        self.error_details = ErrorDetails(
            status=ResponseStatus.ERROR.value, status_code=status_code, message=message)

    def to_dict(self):
        return self.error_details.model_dump()


@bp.errorhandler(APIException)
def api_exception(e):
    return jsonify(e.to_dict()), e.status_code


class LeadResearchReportResponse(BaseModel):
    status: str = Field(...,
                        description="Status (success) of the response.")
    lead_research_report_id: str = Field(...,
                                         description="Identifier of Lead Research report.")
    linkedin_url: str = Field(...,
                              description="LinkedIn URL of the lead.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: str) -> str:
        if v != ResponseStatus.SUCCESS.value:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.route('/v1/lead_report', methods=['GET', 'POST'])
def lead_report():
    db = Database()

    if request.method == "POST":
        # Create research report.
        rp = Researcher(database=db)
        person_linkedin_url: str = request.json.get('linkedin_url').strip()
        if not LinkedInScraper.is_valid_profile_url(profile_url=person_linkedin_url):
            raise APIException(
                status_code=404, message=f"Invalid URL: {person_linkedin_url}")
        try:
            logger.info(
                f"Got request to start report for URL: {person_linkedin_url}")
            research_report: Optional[LeadResearchReport] = db.get_lead_research_report_by_url(
                person_linkedin_url=person_linkedin_url)
            if research_report:
                logger.info(
                    f"Research report already exists for LinkedIn URL: {person_linkedin_url}, returning it.")
                return LeadResearchReportResponse(status=ResponseStatus.SUCCESS.value, lead_research_report_id=research_report.id, linkedin_url=person_linkedin_url).model_dump()

            lead_research_report_id: str = rp.create(
                person_linkedin_url=person_linkedin_url)
            fetch_search_results_in_background.delay(
                lead_research_report_id=lead_research_report_id)

            logger.info(
                f"Created a new lead research report: {lead_research_report_id} for URL: {person_linkedin_url}")

            return LeadResearchReportResponse(status=ResponseStatus.SUCCESS.value, lead_research_report_id=lead_research_report_id, linkedin_url=person_linkedin_url).model_dump()
        except Exception as e:
            logger.exception(
                f"Failed to create report for LinkedIn URL: {person_linkedin_url} with error: {e}")
            raise APIException(
                status_code=500, message=f"Failed to create report for LinkedIn URL: {person_linkedin_url}")

    elif request.method == "GET":
        # Fetch existing report.
        try:
            report: LeadResearchReport = db.get_lead_research_report(
                lead_research_report_id="66aa17d158f79392393414a6")
            return report.model_dump()
        except Exception as e:
            logger.exception("Failed to read report from database.")
            raise APIException(
                status_code=500, message="Failed to read report from database")

    raise APIException(
        status_code=400, message=f"Invalid request method: {request.method}")


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
