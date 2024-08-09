from flask import Blueprint, request, jsonify, g
import logging
from enum import Enum
from typing import Optional, List
from celery import shared_task
from functools import wraps
from pydantic import BaseModel, Field, field_validator
from app.database import Database
from app.models import LeadResearchReport, OutreachEmailTemplate
from app.research_report import Researcher
from app.utils import Utils
from app.linkedin_scraper import LinkedInScraper
from firebase_admin import auth

bp = Blueprint('api', __name__, url_prefix='/api')

logger = logging.getLogger()


class ResponseStatus(str, Enum):
    """Enum representing success or error status in API responses."""
    SUCCESS = "success"
    ERROR = "error"


class ErrorDetails(BaseModel):
    """Details of Error response."""
    status: ResponseStatus = Field(...,
                                   description="Status (error) of the response.")
    status_code: int = Field(...,
                             description="Status code associated with error.")
    message: str = Field(..., description="Message associated with error.")

    @field_validator('status')
    @classmethod
    def status_must_be_error(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.ERROR:
            raise ValueError(f'Expected error status, got: {v}')
        return v


class APIException(Exception):
    """Class to create JSON API responses when an exception is encountered."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code: int = status_code
        self.error_details = ErrorDetails(
            status=ResponseStatus.ERROR, status_code=status_code, message=message)

    def to_dict(self):
        return self.error_details.model_dump()


@bp.errorhandler(APIException)
def api_exception(e):
    return jsonify(e.to_dict()), e.status_code


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "Authorization" not in request.headers:
            logger.exception(
                f"Unauthenticated request, missing Authorization in headers: {request.headers}")
            raise APIException(
                status_code=401, message="Missing Authentication credentials in request")
        bearer = request.headers.get("Authorization")
        id_token = bearer.split()[1]
        user = None
        try:
            user = auth.verify_id_token(id_token)
        except Exception as e:
            logger.exception(f"Failed to verify ID token with error: {e}")
            raise APIException(
                status_code=401, message="Invalid Authentication credentials")
        g.user = user
        return f(*args, **kwargs)

    return decorated_function


class CreateLeadResearchReportResponse(BaseModel):
    """API Response of create lead research report request."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.post('/v1/lead-research-reports')
@login_required
def create_lead_report():
    db = Database()
    user_id: str = g.user["uid"]

    # Create research report.
    rp = Researcher(database=db)
    person_linkedin_url: str = request.json.get('linkedin_url').strip()
    if not LinkedInScraper.is_valid_profile_url(profile_url=person_linkedin_url):
        raise APIException(
            status_code=404, message=f"Invalid URL: {person_linkedin_url}")

    logger.info(f"Got request to start report for URL: {person_linkedin_url}")
    try:
        lead_research_report: Optional[LeadResearchReport] = db.get_lead_research_report_by_url(user_id=user_id,
                                                                                                person_linkedin_url=person_linkedin_url)
    except Exception as e:
        logger.exception(
            f"Failed to fetch Lead Research report for URL: {person_linkedin_url} with error: {e}")
        raise APIException(
            status_code=500, message=f"Failed to create report for LinkedIn URL: {person_linkedin_url}")

    if lead_research_report:
        logger.info(
            f"Research report already exists for LinkedIn URL: {person_linkedin_url}, returning it.")
        raise APIException(
            status_code=409, message=f"Report already exists for URL: {person_linkedin_url}")

    try:
        lead_research_report = rp.create(
            user_id=user_id, person_linkedin_url=person_linkedin_url)
        fetch_search_results_in_background.delay(
            lead_research_report_id=lead_research_report.id)

        logger.info(
            f"Created a new lead research report: {lead_research_report.id} for URL: {person_linkedin_url}")
        response = CreateLeadResearchReportResponse(
            status=ResponseStatus.SUCCESS,
        )
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to create report for LinkedIn URL: {person_linkedin_url} with error: {e}")
        raise APIException(
            status_code=500, message=f"Failed to create report for LinkedIn URL: {person_linkedin_url}")


class GetLeadResearchReportResponse(BaseModel):
    """API Response to get lead research report request."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    lead_research_report: LeadResearchReport = Field(
        ..., description="Fetched Lead Research report.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.get('/v1/lead-research-reports/<string:lead_research_report_id>')
@login_required
def get_lead_report(lead_research_report_id: str):
    # Fetch existing report.
    db = Database()
    try:
        logger.info(
            f"Got lead research report ID: {lead_research_report_id}")
        projection = {
            "person_linkedin_url": 1,
            "person_name": 1,
            "company_name": 1,
            "person_role_title": 1,
            "status": 1,
            "report_creation_date_readable_str": 1,
            "report_publish_cutoff_date_readable_str": 1,
            "details": 1,
        }
        lead_research_report: LeadResearchReport = db.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection=projection)
        logger.info(
            f"Found research report for ID: {lead_research_report_id}")
        response = GetLeadResearchReportResponse(
            status=ResponseStatus.SUCCESS,
            lead_research_report=lead_research_report
        )
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to read report from database with error: {e}")
        raise APIException(
            status_code=500, message="Failed to read research report")


class ListLeadsResponse(BaseModel):
    """API response listing leads."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    leads: List[LeadResearchReport] = Field(
        ..., description="List of leads.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.get('/v1/leads')
@login_required
def list_leads():
    # List all leads created by given user.
    # TODO: Add limit to the leads response.
    db = Database()
    user_id: str = g.user["uid"]
    try:
        projection = {
            "person_linkedin_url": 1,
            "person_name": 1,
            "company_name": 1,
            "person_role_title": 1,
            "status": 1,
            "company_headcount": 1,
            "company_industry_categories": 1,
        }
        lead_research_reports: List[LeadResearchReport] = db.list_lead_research_reports(
            user_id=user_id, projection=projection)
        logger.info(
            f"Got {len(lead_research_reports)} reports from the database")
        response = ListLeadsResponse(
            status=ResponseStatus.SUCCESS, leads=lead_research_reports)
        return response.model_dump()
    except Exception as e:
        logger.exception(f"Failed to list with error: {e}")
        raise APIException(
            status_code=500, message="Failed to list lead research reports.")


class CreateOutreachTemplateResponse(BaseModel):
    """API response for creating Outreach Email template."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.post('/v1/outreach-email-templates')
@login_required
def create_outreach_email_template():
    """Create Outreach Email template."""
    db = Database()
    user_id: str = g.user["uid"]

    persona_role_titles: List[str] = None
    description: str = None
    message: str = None
    try:
        persona_role_titles = [title.strip() for title in request.json.get(
            "persona_role_titles").split(",")]
        description = request.json.get("description")
        message = request.json.get("message")
    except Exception as e:
        logger.exception(
            f"Failed to fetch input for creating email template for request: {request} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters for template creation")

    try:
        outreach_email_template = OutreachEmailTemplate(
            user_id=user_id, persona_role_titles=persona_role_titles, description=description, message=message)
        template_id: str = db.insert_outreach_email_template(
            outreach_email_template=outreach_email_template)
        logger.info(
            f"Created email template with ID: {template_id} for role titles: {persona_role_titles}")
        response = CreateOutreachTemplateResponse(
            status=ResponseStatus.SUCCESS)
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to create email template for request: {request} with error: {e}")
        raise APIException(
            status_code=500, message="Internal Error when creating email template")


class ListOutreachEmailTemplatesResponse(BaseModel):
    """API response for listing Outreach Email templates."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    outreach_email_templates: List[OutreachEmailTemplate] = Field(
        ..., description="List of Outreach email templates created by the user.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.get('/v1/outreach-email-templates')
@login_required
def list_outreach_email_templates():
    """List Outreach Email templates created by the user."""
    db = Database()
    user_id: str = g.user["uid"]

    try:
        projection = {
            "persona_role_titles": 1,
            "description": 1,
            "message": 1,
            "creation_date_readable_str": 1,
            "last_updated_date_readable_str": 1,
        }
        outreach_email_templates: List[OutreachEmailTemplate] = db.list_outreach_email_templates(
            user_id=user_id, projection=projection)
        logger.info(
            f"Fetched {len(outreach_email_templates)} outreach email templates for user: {user_id}")
        response = ListOutreachEmailTemplatesResponse(
            status=ResponseStatus.SUCCESS, outreach_email_templates=outreach_email_templates)
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to List outreach email templates with error: {e}")
        raise APIException(
            status_code=500, message="Internal Error when listing outreach email templates")


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
