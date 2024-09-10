from flask import Blueprint, request, jsonify, g, Response
import logging
import time
import json
from itertools import chain
from enum import Enum
from typing import Optional, List, Dict
from celery import shared_task, chord
from functools import wraps
from pydantic import BaseModel, Field, field_validator
from app.database import Database
from app.models import LeadResearchReport, OutreachEmailTemplate, User, ContentDetails
from app.research_report import Researcher
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


@bp.route('/v1/dbz')
def get_db_check():
    try:
        db = Database()
        db.test_connection()
        logger.info(
            "Pinged your deployment. You successfully connected to MongoDB wohoo!")
        return Response(status=200)
    except Exception as e:
        logger.exception(
            f"Failed to connect to Mongodb instance with error: {e}")
        raise APIException(status_code=500, message="Failed db health check")


@bp.route('/v1/healthz')
def get_health_check():
    """
    This is required in production for Health Check of server.
    Reference: https://cloud.google.com/kubernetes-engine/docs/concepts/ingress#health_checks.
    """
    return Response(status=200)


def get_user_state_db_projection():
    """Returns dictionary with user state field that will serve as projection into to MongoDB query."""
    return {"state": 1}


class GetUserResponse(BaseModel):
    """API Response of get user request."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    user: User = Field(...,
                       description="User object for curently authenticated user.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.get('/v1/users')
@login_required
def get_user():
    db = Database()
    user_id: str = g.user["uid"]
    logger.info(f"Fetch info for user with ID: {user_id}")

    try:
        user = db.get_or_create_user(
            user_id=user_id, projection=get_user_state_db_projection())
        response = GetUserResponse(status=ResponseStatus.SUCCESS, user=user)
        logger.info(f"Got user for ID: {user_id} from database.")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to get user for ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Failed to get User due to internal error.")


class UpdateUserResponse(BaseModel):
    """API Response of update user request."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.put('/v1/users')
@login_required
def update_user():
    db = Database()
    user_id: str = g.user["uid"]

    state: User.State = None
    try:
        # Only allow state updates for now.
        state = User.State(request.json.get('state'))
    except Exception as e:
        logger.exception(
            f"Failed to update user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters for user updation.")

    try:
        setFields = {
            "state": state,
        }
        db.update_user(user_id=user_id, setFields=setFields)
        logger.info(
            f"Successfully updated state for user: {user_id} to {state}")
        response = UpdateUserResponse(status=ResponseStatus.SUCCESS)
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to update user ID: {user_id} state to {state} with error: {e}")
        raise APIException(
            status_code=500, message="Failed to update user due to internal error.")


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

    # Remove any leading and trailing whitespaces and trailing slashes.
    person_linkedin_url: str = request.json.get(
        'linkedin_url').strip().rstrip("/")
    if not LinkedInScraper.is_valid_profile_url(profile_url=person_linkedin_url):
        raise APIException(
            status_code=404, message=f"Invalid LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id}")

    logger.info(
        f"Got request from user ID: {user_id} to start report for URL: {person_linkedin_url}")

    lead_research_report: Optional[LeadResearchReport] = None
    try:
        lead_research_report = db.get_lead_research_report_by_url(
            user_id=user_id, person_linkedin_url=person_linkedin_url, projection={"_id": 1})
    except Exception as e:
        logger.exception(
            f"Failed to fetch Lead Research report for URL: {person_linkedin_url} requested by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message=f"Failed to create report for LinkedIn URL: {person_linkedin_url}")

    if lead_research_report:
        logger.info(
            f"Research report already exists with report ID: {lead_research_report.id} for LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id}.")
        raise APIException(
            status_code=409, message=f"Report already exists for URL: {person_linkedin_url}, please check in the Leads Table.")

    try:
        # Create report in the database and continue updating it in the background.
        lead_research_report = LeadResearchReport(
            user_id=user_id, person_linkedin_url=person_linkedin_url, status=LeadResearchReport.Status.NEW)
        lead_research_report_id: str = db.insert_lead_research_report(
            lead_research_report=lead_research_report)
        fetch_lead_info_orchestrator.delay(
            lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Created report: {lead_research_report_id} for lead with LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id}")
        response = CreateLeadResearchReportResponse(
            status=ResponseStatus.SUCCESS,
        )
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to create report for LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message=f"Failed to create report for LinkedIn URL: {person_linkedin_url}")


class GetLeadResearchReportResponse(BaseModel):
    """API Response to get lead research report request."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    lead_research_report: LeadResearchReport = Field(
        ..., description="Fetched Lead Research report.")
    user: User = Field(...,
                       description="User object for curently authenticated user.")

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
    user_id: str = g.user["uid"]

    try:
        projection = {
            "person_linkedin_url": 1,
            "person_name": 1,
            "company_name": 1,
            "person_role_title": 1,
            "status": 1,
            "report_creation_date_readable_str": 1,
            "report_publish_cutoff_date_readable_str": 1,
            "details": 1,
            "chosen_outreach_email_template": {
                "id": 1,
                "name": 1,
                "message": 1,
            },
            "personalized_emails": {
                "_id": 1,
                "highlight_id": 1,
                "highlight_url": 1,
                "email_subject_line": 1,
                "email_opener": 1,
            },
            "personalized_outreach_messages": {
                "personalized_emails": {
                    "_id": 1,
                    "highlight_id": 1,
                    "highlight_url": 1,
                    "email_subject_line": 1,
                    "email_opener": 1,
                    "template": {
                        "id": 1,
                        "name": 1,
                        "message": 1,
                    },
                },
            }
        }
        lead_research_report: LeadResearchReport = db.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection=projection)
        logger.info(
            f"Found research report for ID: {lead_research_report_id}")
        user = db.get_or_create_user(user_id=user_id,
                                     projection=get_user_state_db_projection())
        response = GetLeadResearchReportResponse(
            status=ResponseStatus.SUCCESS,
            lead_research_report=lead_research_report,
            user=user
        )
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to read report with ID: {lead_research_report_id} from database with error: {e}")
        raise APIException(
            status_code=500, message="Failed to read research report")


class ListLeadsResponse(BaseModel):
    """API response listing leads."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    leads: List[LeadResearchReport] = Field(
        ..., description="List of leads.")
    user: User = Field(...,
                       description="User object for curently authenticated user.")

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
    start_time = time.time()
    try:
        filter = {
            "user_id": user_id,
        }
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
            filter=filter, projection=projection)
        user = db.get_or_create_user(user_id=user_id,
                                     projection=get_user_state_db_projection())
        response = ListLeadsResponse(
            status=ResponseStatus.SUCCESS, leads=lead_research_reports, user=user)
        logger.info(
            f"Fetched {len(lead_research_reports)} from database for user ID: {user_id}. Time taken was: {time.time() - start_time} seconds")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to list lead research reports for user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Failed to list lead research reports.")


class UpdateTemplateInReportResponse(BaseModel):
    """API response after updateing template and personalized emails in Lead Research Report."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    chosen_outreach_email_template: LeadResearchReport.ChosenOutreachEmailTemplate = Field(
        ..., description="Updated outreach email template.")
    personalized_emails: List[LeadResearchReport.PersonalizedEmail] = Field(
        ..., description="Updated personalized emails.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.post('/v1/lead-research-reports/template')
@login_required
def add_template_in_lead_report():
    # Add a new template in given lead report. This will create a new template object and
    # TODO: This method is deprecated. Update this method for the new flow decided.
    db = Database()
    user_id: str = g.user["uid"]

    lead_research_report_id: str = None
    selected_template_id: str = None
    try:
        lead_research_report_id: str = request.json.get(
            "lead_research_report_id")
        selected_template_id: str = request.json.get("selected_template_id")
    except Exception as e:
        logger.exception(
            f"Invalid request: {request} to update template for user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters for template selection in lead report.")

    logger.info(
        f"Got request to update report: {lead_research_report_id} with given template ID: {selected_template_id}")

    start_time = time.time()
    rp = Researcher(database=db)
    try:
        rp.update_template_and_regen_emails(
            lead_research_report_id=lead_research_report_id, selected_template_id=selected_template_id)

        # Fetch and return updated email template and personalized emails.
        projection = {
            "chosen_outreach_email_template": {
                "id": 1,
                "name": 1,
                "message": 1,
            },
            "personalized_emails": {
                "_id": 1,
                "highlight_id": 1,
                "highlight_url": 1,
                "email_subject_line": 1,
                "email_opener": 1,
            },
        }
        lead_research_report: LeadResearchReport = db.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection=projection)
        response = UpdateTemplateInReportResponse(
            status=ResponseStatus.SUCCESS,
            chosen_outreach_email_template=lead_research_report.chosen_outreach_email_template,
            personalized_emails=lead_research_report.personalized_emails,
        )
        logger.info(
            f"Successfully updated report: {lead_research_report_id} with template ID: {selected_template_id} and emails. Time elapsed: {time.time()-start_time} seconds")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to update report with ID: {lead_research_report_id} with a new template with ID: {selected_template_id} with error: {e}")
        raise APIException(
            status_code=500, message="Failed to select template due to an error.")


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

    name: str = None
    persona_role_titles: List[str] = None
    description: str = None
    message: str = None
    try:
        name = request.json.get("name")
        persona_role_titles = [title.strip() for title in request.json.get(
            "persona_role_titles").split(",")]
        description = request.json.get("description")
        message = request.json.get("message")
    except Exception as e:
        logger.exception(
            f"Invalid request: {request} to create outreach email template by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters for template creation")

    try:
        outreach_email_template = OutreachEmailTemplate(
            user_id=user_id, name=name, persona_role_titles=persona_role_titles, description=description, message=message)
        template_id: str = db.insert_outreach_email_template(
            outreach_email_template=outreach_email_template)
        logger.info(
            f"Successfully created outreach email template with ID: {template_id} for user ID: {user_id}")
        response = CreateOutreachTemplateResponse(
            status=ResponseStatus.SUCCESS)
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to create email template for request: {request} by user: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Internal Error when creating email template")


class GetOutreachEmailTemplateResponse(BaseModel):
    """API response for fetching a single Outreach Email template."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    outreach_email_template: OutreachEmailTemplate = Field(
        ..., description="Outreach email template requested by user in request.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.get('/v1/outreach-email-templates/<string:outreach_email_template_id>')
@login_required
def get_outreach_email_template(outreach_email_template_id: str):
    """Get Outreach Email template with given ID."""
    db = Database()
    user_id: str = g.user["uid"]
    try:
        outreach_email_template: OutreachEmailTemplate = db.get_outreach_email_template(
            outreach_email_template_id=outreach_email_template_id)
        response = GetOutreachEmailTemplateResponse(
            status=ResponseStatus.SUCCESS,
            outreach_email_template=outreach_email_template
        )
        logger.info(
            f"Got Outreach Email template for ID: {outreach_email_template_id}")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to get Outreach Email template for ID: {outreach_email_template_id} by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Internal Error when fetching Outreach Email template")


class ListOutreachEmailTemplatesResponse(BaseModel):
    """API response for listing Outreach Email templates."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    outreach_email_templates: List[OutreachEmailTemplate] = Field(
        ..., description="List of Outreach email templates created by the user.")
    user: User = Field(...,
                       description="User object for curently authenticated user.")

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
    start_time = time.time()
    try:
        projection = {
            "name": 1,
            "persona_role_titles": 1,
            "description": 1,
            "message": 1,
            "creation_date_readable_str": 1,
            "last_updated_date_readable_str": 1,
        }
        outreach_email_templates: List[OutreachEmailTemplate] = db.list_outreach_email_templates(
            user_id=user_id, projection=projection)
        user = db.get_or_create_user(
            user_id=user_id, projection=get_user_state_db_projection())
        response = ListOutreachEmailTemplatesResponse(
            status=ResponseStatus.SUCCESS, outreach_email_templates=outreach_email_templates, user=user)
        logger.info(
            f"Fetched {len(outreach_email_templates)} outreach email templates requested by user ID: {user_id}. Time taken: {time.time() - start_time} seconds.")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to List outreach email templates requested by user: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Internal Error when listing outreach email templates")


class UpdateOutreachEmailTemplatesResponse(BaseModel):
    """API response for updating Outreach Email template."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.put('/v1/outreach-email-templates/<string:outreach_email_template_id>')
@login_required
def update_outreach_email_template(outreach_email_template_id: str):
    """Updates Outreach Email template with given ID."""
    db = Database()
    user_id: str = g.user["uid"]

    name: str = None
    persona_role_titles: List[str] = None
    description: str = None
    message: str = None
    try:
        name = request.json.get("name")
        persona_role_titles = [title.strip() for title in request.json.get(
            "persona_role_titles").split(",")]
        description = request.json.get("description")
        message = request.json.get("message")
    except Exception as e:
        logger.exception(
            f"Invalid request: {request} for updating email template ID: {outreach_email_template_id} by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters for updating template.")

    logger.info(
        f"Got update request: {request} to update template ID: {outreach_email_template_id} requested by user ID: {user_id}")
    try:
        setFields = {
            "name": name,
            "persona_role_titles": persona_role_titles,
            "description": description,
            "message": message,
        }
        db.update_outreach_email_template(
            outreach_email_template_id=outreach_email_template_id, setFields=setFields)
        response = UpdateOutreachEmailTemplatesResponse(
            status=ResponseStatus.SUCCESS,
        )
        logger.info(
            f"Updated Outreach Email template for ID: {outreach_email_template_id} requested by user ID: {user_id}")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to Update Outreach Email template: {outreach_email_template_id} requested by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Internal Error when Updating Outreach Email template")


class DeleteOutreachTemplateResponse(BaseModel):
    """API response for deleting Outreach Email template."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.delete('/v1/outreach-email-templates/<string:outreach_email_template_id>')
@login_required
def delete_outreach_email_template(outreach_email_template_id: str):
    """Delete Outreach Email template with given ID."""
    db = Database()
    user_id: str = g.user["uid"]
    logger.info(
        f"Got request to delete template ID: {outreach_email_template_id} by user ID: {user_id}.")
    try:
        db.delete_one_object_id(db.get_outreach_email_template_collection(
        ), id_to_delete=outreach_email_template_id)
        logger.info(
            f"Successfully deleted Outreach Email template ID: {outreach_email_template_id} requested by user ID: {user_id}.")
        response = DeleteOutreachTemplateResponse(
            status=ResponseStatus.SUCCESS)
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to delete Outreach Email with template ID: {outreach_email_template_id} requested by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Internal Error when deleting Outreach Email template")


@bp.get('/v1/debug/<string:report_id>')
def admin_debug(report_id: str):
    logger.info(f"Debug request got report ID: {report_id}")
    fetch_lead_info_orchestrator.delay(
        lead_research_report_id=report_id)
    logger.info(
        f"Started orchestrator in debug request for report ID: {report_id}")
    return Response("ok\n")


@bp.delete('/v1/admin/delete/<string:lead_research_report_id>/<string:confirm_deletion>')
def admin_delete_report(lead_research_report_id: str, confirm_deletion: str):
    """Admin API to delete lead research report and associated artifacts if any.

    If there are other reports that reference the same company profile as exists in this report,
    then we will only delete the report.
    If there are no other such reports, then we will delete all content details that have given
    company profile and their associated web pages and linkedin posts as well. Finally we will delete the report.
    """
    database = Database()
    report = database.get_lead_research_report(
        lead_research_report_id=lead_research_report_id, projection={"company_profile_id": 1, "user_id": 1})
    company_profile_id: str = report.company_profile_id
    user_id: str = report.user_id
    # TODO: Bug in this filter. It doesn't return the correct reports.
    reports: List[LeadResearchReport] = database.list_lead_research_reports(
        filter={"company_profile_id": company_profile_id, "user_id": {"$ne": user_id}}, projection={"_id": 1})
    if len(reports) > 0:
        logger.info(
            f"Found other reports: {[report.id for report in reports]} for given company profile ID: {company_profile_id} for request with report ID: {lead_research_report_id}.")
        if confirm_deletion == "confirm_deletion":
            # Delete lead report ID and exit.
            database.delete_one_object_id(collection=database.get_lead_research_report_collection(
            ), id_to_delete=lead_research_report_id)
            logger.info(
                f"Deletion complete. Stats deleted 1 lead report with ID: {lead_research_report_id}")
        return Response("done\n")

    logger.info(
        f"No other reports found for company profile ID: {company_profile_id} for given report ID: {lead_research_report_id}, will delete all associated artifacts.")
    content_details_list: List[ContentDetails] = database.list_content_details(
        filter={"company_profile_id": company_profile_id}, projection={"linkedin_post_ref_id": 1, "web_page_ref_id": 1})

    linkedin_ids_list: List[str] = []
    web_page_ids_list: List[str] = []
    for cd in content_details_list:
        if cd.linkedin_post_ref_id:
            linkedin_ids_list.append(cd.linkedin_post_ref_id)
        if cd.web_page_ref_id:
            web_page_ids_list.append(cd.web_page_ref_id)

    content_details_ids_list: List[str] = [
        str(cd.id) for cd in content_details_list]

    logger.info(f"Got: {len(content_details_ids_list)} content details docs, {len(linkedin_ids_list)} linkedin post docs, {len(web_page_ids_list)} web page docs and 1 Lead Report with ID: {lead_research_report_id}")

    if confirm_deletion == "confirm_deletion":
        # Delete content.
        database.delete_object_ids(collection=database.get_linkedin_posts_collection(
        ), ids_to_delete=linkedin_ids_list)
        database.delete_object_ids(
            collection=database.get_web_pages_collection(), ids_to_delete=web_page_ids_list)
        database.delete_object_ids(
            collection=database.get_content_details_collection(), ids_to_delete=content_details_ids_list)
        database.delete_one_object_id(collection=database.get_lead_research_report_collection(
        ), id_to_delete=lead_research_report_id)

        logger.info(
            f"Deletion complete. Stats: {len(content_details_ids_list)} content details docs, {len(linkedin_ids_list)} linkedin post docs, {len(web_page_ids_list)} web page docs and 1 Lead Report with ID: {lead_research_report_id}")
    return Response("done\n")


def shared_task_exception_handler(shared_task_obj, database: Database, lead_research_report_id: str, e: Exception, task_name: str, status_before_failure: LeadResearchReport.Status):
    """Helper to handle the exception that occured in given shared task instance."""
    # We retry 3 times at max, so 4 times in total.
    max_retries = 3

    if shared_task_obj.request.retries >= max_retries:
        # Done with retries, go to the next step.
        logger.exception(
            f"Retries exhausted for request: {task_name} with report ID: {lead_research_report_id} with error: {e}")
        # Done with retries, update status as failed and register last status.
        setFields = {
            "status": LeadResearchReport.Status.FAILED_WITH_ERRORS,
            "status_before_failure": status_before_failure,
        }
        database.update_lead_research_report(lead_research_report_id=lead_research_report_id,
                                             setFields=setFields)
        raise ValueError(
            f"Retries exhaused for request: {task_name} with report ID: {lead_research_report_id} with error: {e}")

    # Retry after delay.
    retry_interval_seconds: int = 10
    logger.exception(
        f"Error in {task_name} for report ID: {lead_research_report_id} with retry count: {shared_task_obj.request.retries}, error details: {e}")
    raise shared_task_obj.retry(
        exc=e, max_retries=max_retries, countdown=retry_interval_seconds)


@shared_task(bind=True, acks_late=True)
def fetch_lead_info_orchestrator(self, lead_research_report_id: str):
    """Main Orchestrator that routes the given report to the correct Celery task."""
    logger.info(
        f"Orchestrator called for lead report ID: {lead_research_report_id}")
    database = Database()

    report_status: LeadResearchReport.Status = None
    try:
        report: LeadResearchReport = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection={"status": 1, "status_before_failure": 1})
        report_status: LeadResearchReport.Status = report.status if report.status != LeadResearchReport.Status.FAILED_WITH_ERRORS else report.status_before_failure
        logger.info(
            f"Current report status: {report_status} for report ID: {lead_research_report_id}")
        if report_status == LeadResearchReport.Status.NEW:
            logger.info(
                f"Report just created with ID: {lead_research_report_id}, enrich lead profile next.")
            enrich_lead_info_in_background.delay(
                lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.BASIC_PROFILE_FETCHED:
            logger.info(
                f"Basic profile fetched for {lead_research_report_id}, fetch search results next.")
            fetch_search_results_in_background.delay(
                lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED:
            logger.info(
                f"Fetched search results for {lead_research_report_id}, process content in search results next.")
            process_content_in_search_results_in_background.delay(
                lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.CONTENT_PROCESSING_COMPLETE:
            logger.info(
                f"Processed content in search results for {lead_research_report_id}, aggregate report results next.")
            aggregate_report_in_background.delay(
                lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE:
            logger.info(
                f"Lead Report aggregation complete for {lead_research_report_id}, select email template next.")
            choose_template_and_create_emails_in_background.delay(
                lead_research_report_id=lead_research_report_id)
        elif report_status == LeadResearchReport.Status.COMPLETE:
            logger.info(
                f"Lead research complete for {lead_research_report_id}, nothing more to do here.")

    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="fetch_lead_info_orchestrator", status_before_failure=report_status)


@shared_task(bind=True, acks_late=True)
def enrich_lead_info_in_background(self, lead_research_report_id: str):
    """Enrich lead with name, company name, role titles in the given Lead Report."""
    logger.info(
        f"Creating lead profile for Lead Research report ID: {lead_research_report_id}")
    database = Database()
    try:
        rp = Researcher(database=database)
        rp.enrich_lead_info(
            lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Enriched lead successfully in report ID: {lead_research_report_id}.")

        # Fetch Search Results associated with the given leads.
        fetch_search_results_in_background.delay(
            lead_research_report_id=lead_research_report_id)
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="enrich_lead_info", status_before_failure=LeadResearchReport.Status.NEW)


@shared_task(bind=True, acks_late=True)
def fetch_search_results_in_background(self, lead_research_report_id: str):
    """Fetch search results for given lead in background."""
    logger.info(
        f"Start fetching search URLs for lead report ID: {lead_research_report_id}")
    database = Database()
    try:
        r = Researcher(database=database)
        r.fetch_search_results(lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Completed fetching search results for lead report ID: {lead_research_report_id}")

        # Process search URLs contents next.
        process_content_in_search_results_in_background.delay(
            lead_research_report_id=lead_research_report_id)
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="fetch_search_results", status_before_failure=LeadResearchReport.Status.BASIC_PROFILE_FETCHED)


@shared_task(bind=True, acks_late=True)
def process_content_in_search_results_in_background(self, lead_research_report_id: str):
    """Processes URLs in search results in background."""
    logger.info(
        f"Start processing search URLs to process for lead report: {lead_research_report_id}")
    database = Database()
    try:
        research_report: LeadResearchReport = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)
        search_results_list: List[LeadResearchReport.WebSearchResults.Result] = research_report.web_search_results.results
        total_urls_to_process: int = research_report.web_search_results.num_results

        # Split search URLs into batches depending on the number of concurrent processes in a worker.
        # Note: This concurrency value must match the concurreny passed during app intialization.
        # TODO: Make this read the concurrency value from the celery start command line argument.
        concurrency = 8
        batch_size = int(total_urls_to_process/concurrency) + \
            (0 if total_urls_to_process % concurrency == 0 else 1)
        logger.info(
            f"Splitting a total of {total_urls_to_process} Search URLs using {concurrency} workers which will each handle at max {batch_size} URLs for processing for lead report: {lead_research_report_id}.")
        batches: List[LeadResearchReport.WebSearchResults.Result] = []
        for i in range(concurrency):
            start_idx = i*batch_size
            end_idx = start_idx + batch_size
            batches.append(search_results_list[start_idx: end_idx])
            if end_idx >= total_urls_to_process:
                break

        logger.info(f"Num batches: {len(batches)}")
        logger.info(f"batching nums: {[len(b) for b in batches]}")

        parallel_workers = [process_content_in_search_results_batch_in_background.s(
            num, lead_research_report_id, [r.model_dump_json() for r in batch]) for num, batch in enumerate(batches)]
        aggregation_work = aggregate_processed_search_results_in_background.s(
            lead_research_report_id)

        # Start processing.
        chord(parallel_workers)(aggregation_work)

    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name="process_content_in_search_results", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(bind=True, acks_late=True, ignore_result=False, rate_limit="5/m")
def process_content_in_search_results_batch_in_background(self, batch_num: int, lead_research_report_id: str, search_results_batch_json: List[str]):
    """Process batch of given Search Result URLs and returns a list of URLs that failed to process."""
    search_results_batch = []
    for r_json in search_results_batch_json:
        search_result = LeadResearchReport.WebSearchResults.Result(
            **json.loads(r_json))
        search_results_batch.append(search_result)

    logger.info(
        f"Got {search_results_batch} search URLs to process for lead report: {lead_research_report_id} in batch number: {batch_num}")
    database = Database()
    try:
        r = Researcher(database=database)
        failed_urls: List[str] = r.process_content_in_search_urls(
            lead_research_report_id=lead_research_report_id, search_results_batch=search_results_batch, task_num=batch_num)
        logger.info(
            f"Completed search URLs processing for lead report: {lead_research_report_id} in batch number: {batch_num}")
        return failed_urls
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name=f"process_content_in_search_results_batch_{batch_num}", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(bind=True, acks_late=True)
def aggregate_processed_search_results_in_background(self, failed_urls_list: List[List[str]], lead_research_report_id: str):
    """Aggregate processing of search results from each worker task that worked on a batch."""
    logger.info(
        f"Start aggregating search results for lead report ID: {lead_research_report_id}")
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
            f"Completed aggregation of processed search results for lead report ID: {lead_research_report_id}")

        # Aggregate Report next.
        aggregate_report_in_background.delay(
            lead_research_report_id=lead_research_report_id)
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name=f"aggregate_processed_search_results", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(bind=True, acks_late=True)
def aggregate_report_in_background(self, lead_research_report_id: str):
    """Create a research report in background."""
    logger.info(
        f"Start lead research report aggregation for report ID: {lead_research_report_id}")
    database = Database()
    try:
        r = Researcher(database=database)
        r.aggregate(lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Completed aggregation of research report complete for report ID: {lead_research_report_id}")

        # Select email outreach template next.
        choose_template_and_create_emails_in_background.delay(
            lead_research_report_id=lead_research_report_id)
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="aggregate_report", status_before_failure=LeadResearchReport.Status.CONTENT_PROCESSING_COMPLETE)


@shared_task(bind=True, acks_late=True)
def choose_template_and_create_emails_in_background(self, lead_research_report_id: str):
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
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name="choose_template_and_create_emails", status_before_failure=LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE)
