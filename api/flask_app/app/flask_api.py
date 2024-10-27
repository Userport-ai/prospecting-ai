from flask import Blueprint, request, jsonify, g, Response
import logging
import time
import json
from itertools import chain
from enum import Enum
from typing import Optional, List
from celery import shared_task, chord
from celery.exceptions import SoftTimeLimitExceeded
from functools import wraps
from pydantic import BaseModel, Field, field_validator
from app.database import Database
from app.models import LeadResearchReport, OutreachEmailTemplate, User, ContentDetails, OpenAITokenUsage, LinkedInActivity
from app.research_report import Researcher
from app.linkedin_scraper import LinkedInScraper, InvalidLeadLinkedInUrlException, LeadLinkedInProfileNotFoundException
from app.personalization import Personalization
from app.activity_parser import LinkedInActivityParser
from app.utils import Utils
from app.rate_limiter import rate_limiter, get_value
from firebase_admin import auth
from flask_limiter import RateLimitExceeded
from app.metrics import Metrics

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


@bp.errorhandler(RateLimitExceeded)
def ratelimit_handler(e: RateLimitExceeded):
    # Convert 429 error code form rate limiter to Standard API response so UI can show it to the user.
    return ErrorDetails(status=ResponseStatus.ERROR, status_code=e.code, message=e.description).model_dump(), e.code


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
    #health_checks.
    Reference: https://cloud.google.com/kubernetes-engine/docs/concepts/ingress
    """
    return Response(status=200)


def get_user_state_db_projection():
    """Returns dictionary with user state field that will serve as projection into to MongoDB query."""
    return {"state": 1}


class GetCustomAuthTokenResponse(BaseModel):
    """API Response to get custom auth token."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    custom_token: str = Field(...,
                              description="Custom token represented as JWT which will allow clients to sign in.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.get('/v1/auth/custom-token')
@login_required
def get_auth_custom_token():
    """
    Fetch Custom Auth token for given logged in user. This will be used by Chrome Extension to authenticate
    with the app and perform API requests.
    """
    user_id: str = g.user["uid"]
    try:
        custom_token = auth.create_custom_token(uid=user_id)
        response = GetCustomAuthTokenResponse(
            status=ResponseStatus.SUCCESS, custom_token=custom_token)
        logger.info(f"Got custom token for user ID: {user_id} successfully")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to get custom Firebase Auth token for user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Failed to authenticate user due to an internal error.")


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
    """
    Fetch User state from database. If the user does not exist, it will create the user in the database first.

    This is also the method that gets called when the user first signs up on the app.
    """
    db = Database()
    user_id: str = g.user["uid"]
    email: str = g.user["email"]
    logger.info(f"Fetch info for user with ID: {user_id}")

    try:
        user: Optional[User] = db.get_user(
            user_id=user_id, projection=get_user_state_db_projection())
        if not user:
            logger.info(
                f"User ID: {user_id} does not exist in database, creating one for this new user.")
            db.create_new_user(user_id=user_id, email=email)
            logger.info(f"Created User with ID: {user_id} in the database.")
            user = db.get_user(
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

    lead_research_report: LeadResearchReport = Field(
        ..., description="Created Lead Research report. Not all fields are populated since creation will still be in progress when this API response is returned.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.post('/v1/lead-research-reports')
@login_required
@rate_limiter.limit(key_func=lambda: g.user["uid"], limit_value=get_value)
def create_lead_report():
    db = Database()
    user_id: str = g.user["uid"]

    person_linkedin_url: Optional[str] = None
    origin: Optional[str] = None
    postsHTML: Optional[str] = None
    commentsHTML: Optional[str] = None
    reactionsHTML: Optional[str] = None
    try:
        # Remove any leading and trailing whitespaces and trailing slashes.
        person_linkedin_url = Utils.remove_spaces_and_trailing_slashes(
            url=request.json.get('linkedin_url'))
        if not LinkedInScraper.is_valid_profile_url(profile_url=person_linkedin_url):
            raise ValueError(
                f"Invalid LinkedIn URL: {person_linkedin_url} requested.")
        origin = request.json.get("origin")
        postsHTML = request.json.get("postsHTML")
        commentsHTML = request.json.get("commentsHTML")
        reactionsHTML = request.json.get("reactionsHTML")
        if origin == LeadResearchReport.Origin.EXTENSION.value:
            # Origin is Extension, so we expect HTML for posts, comments and reactions to be present.
            if postsHTML == None:
                raise ValueError(
                    f"Posts HTML cannot be empty for Origin Extension")
            if commentsHTML == None:
                raise ValueError(
                    f"Comments HTML cannot be empty for Origin Extension")
            if reactionsHTML == None:
                raise ValueError(
                    f"Reactions HTML cannot be empty for Origin Extension")
    except Exception as e:
        logger.exception(
            f"Failed to create report with request: {request} for user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message=f"Invalid request to create a report")

    logger.info(
        f"Got request to start report for URL: {person_linkedin_url} and origin: {origin}, from user ID: {user_id}")

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
        lead_research_report_id: str
        lead_research_report = LeadResearchReport(
            user_id=user_id, person_linkedin_url=person_linkedin_url, status=LeadResearchReport.Status.NEW, origin=origin)
        if origin == LeadResearchReport.Origin.WEB.value:
            # Create report in the database and continue updating it in the background.
            lead_research_report_id = db.insert_lead_research_report(
                lead_research_report=lead_research_report)
        else:
            # Create report along with any activity HTML in the database and continue updating it in the background.
            # This is done in a single transaction so that we insert all activities and lead report successfully in an atomic manner.
            with db.transaction_session() as session:
                # Fetch list of activities from HTML.
                posts_list: List[LinkedInActivity] = LinkedInActivityParser.get_activities(
                    person_linkedin_url=person_linkedin_url, page_html=postsHTML, activity_type=LinkedInActivity.Type.POST)
                comments_list: List[LinkedInActivity] = LinkedInActivityParser.get_activities(
                    person_linkedin_url=person_linkedin_url, page_html=commentsHTML, activity_type=LinkedInActivity.Type.COMMENT)
                reactions_list: List[LinkedInActivity] = LinkedInActivityParser.get_activities(
                    person_linkedin_url=person_linkedin_url, page_html=reactionsHTML, activity_type=LinkedInActivity.Type.REACTION)

                # Add activities to database.
                all_activities: List[LinkedInActivity] = posts_list + \
                    comments_list + reactions_list
                activity_ref_ids: List[str] = db.insert_linkedin_activities(
                    linkedin_activities=all_activities, session=session)
                logger.info(
                    f"Created {len(all_activities)} activities into database for LinkedIn URL: {person_linkedin_url}, requested by user ID: {user_id}")

                # Populate activity IDs in lead report and insert into database. They will be processed in the background later.
                lead_research_report.linkedin_activity_info = LeadResearchReport.LinkedInActivityInfo(
                    activity_ref_ids=activity_ref_ids)
                lead_research_report_id = db.insert_lead_research_report(
                    lead_research_report=lead_research_report, session=session)

        if origin == LeadResearchReport.Origin.WEB:
            # TODO: Remove this if condition once the flow for extension has been written.
            fetch_lead_info_orchestrator.delay(
                lead_research_report_id=lead_research_report_id)

        logger.info(
            f"Created report: {lead_research_report_id} for lead with LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id} for origin: {origin}")

        # Add created report ID to the response.
        lead_research_report.id = lead_research_report_id
        response = CreateLeadResearchReportResponse(
            status=ResponseStatus.SUCCESS,
            lead_research_report=lead_research_report
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
            "personalized_outreach_messages": {
                "personalized_emails": {
                    "id": 1,
                    "last_updated_date": 1,
                    "highlight_id": 1,
                    "highlight_url": 1,
                    "email_subject_line": 1,
                    "email_opener": 1,
                    "template": {
                        "id": 1,
                        "name": 1,
                        "message": 1,
                        "message_index": 1,
                    },
                },
            }
        }
        lead_research_report: LeadResearchReport = db.get_lead_research_report(
            lead_research_report_id=lead_research_report_id, projection=projection)
        logger.info(
            f"Found research report for ID: {lead_research_report_id}")
        user = db.get_user(
            user_id=user_id, projection=get_user_state_db_projection())
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
        user = db.get_user(
            user_id=user_id, projection=get_user_state_db_projection())
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


class UpdateTemplateInPersonalizedEmailResponse(BaseModel):
    """API response after updateing template in personalized email in Lead Research Report."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


class CheckLeadReportExistsResponse(BaseModel):
    """API response for whether lead research report exists for given person linkedin URL."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    report_exists: bool = Field(...,
                                description="True if report exists and False otherwise.")
    lead_research_report: Optional[LeadResearchReport] = Field(
        default=None, description="Lead report if it exists and None otherwise.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.get('/v1/lead-research-reports')
@login_required
def check_if_report_exists():
    # Check if lead research report existing for given LinkedIn profile.
    person_linkedin_url: str = None
    try:
        person_linkedin_url = Utils.remove_spaces_and_trailing_slashes(
            request.args.get("url"))
    except Exception as e:
        logger.exception(
            f"Invalid check if report exists with request: {request} with error: {e}")
        raise APIException(
            status_code=400, message=f"Invalid request to check if lead report exists.")

    # Checks whether Lead Research report exists for given person's LinkedIn URL and returns Report ID and Status if so.
    db = Database()
    user_id: str = g.user["uid"]
    lead_research_report: Optional[LeadResearchReport] = None

    logger.info(
        f"Check if lead report exists for linkedin URL: {person_linkedin_url} requested by user ID: {user_id}")

    try:
        projection = {
            "_id": 1,
            "status": 1,
            "personalized_outreach_messages": {
                "personalized_emails": {
                    "email_opener": 1,
                    "highlight_url": 1
                }
            }
        }
        lead_research_report = db.get_lead_research_report_by_url(
            user_id=user_id, person_linkedin_url=person_linkedin_url, projection=projection)
    except Exception as e:
        logger.exception(
            f"Failed to check if Lead Research report exists for person LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message=f"Failed to check if Lead Research report exists for LinkedIn URL: {person_linkedin_url}")

    response: CheckLeadReportExistsResponse = None
    if lead_research_report:
        logger.info(
            f"Found Research report with report ID: {lead_research_report.id} for LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id}.")
        response = CheckLeadReportExistsResponse(
            status=ResponseStatus.SUCCESS, report_exists=True, lead_research_report=lead_research_report)
    else:
        logger.info(
            f"Did not find research report for person LinkedIn URL: {person_linkedin_url} requested by user ID: {user_id}")
        response = CheckLeadReportExistsResponse(
            status=ResponseStatus.SUCCESS, report_exists=False, lead_research_report=None)
    return response.model_dump()


@bp.put('/v1/lead-research-reports/personalized-emails/<string:personalized_email_id>')
@login_required
def update_template_in_personalized_email(personalized_email_id: str):
    """Update given template as the new template for given personalized email. This action is initiated by the user.
    The email subject line and opener will not be regenerated on template update."""
    db = Database()
    user_id: str = g.user["uid"]

    lead_research_report_id: Optional[str] = None
    new_template_id: Optional[str] = None
    new_message_index: Optional[int] = None
    new_email_opener: Optional[str] = None
    new_email_subject_line: Optional[str] = None
    try:
        lead_research_report_id = request.json.get(
            "lead_research_report_id")
        new_template_id = request.json.get("new_template_id")
        new_message_index = request.json.get("new_message_index")
        new_email_opener = request.json.get("new_email_opener")
        new_email_subject_line = request.json.get(
            "new_email_subject_line")

        if new_template_id == None and new_email_opener == None and new_email_subject_line == None:
            raise ValueError(
                f"Invalid request parameters, all inputs are None!")
    except Exception as e:
        logger.exception(
            f"Invalid request: {request} to update template in personalized email for user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters for update template in personalized email.")

    logger.info(
        f"Got request: {request.json} to update in personalized email ID: {personalized_email_id} in report ID:{lead_research_report_id}")

    try:
        # Fetch lead report and new template from the database.
        report = db.get_lead_research_report(lead_research_report_id=lead_research_report_id, projection={
                                             "personalized_outreach_messages": 1})
        personalized_outreach_messages: LeadResearchReport.PersonalizedOutreachMessages = report.personalized_outreach_messages

        # Find reference to email object (that needs update) from within personalized outreach messages object.
        idx = -1
        for i, email in enumerate(personalized_outreach_messages.personalized_emails):
            if email.id != personalized_email_id:
                continue
            idx = i
            break
        if idx == -1:
            raise ValueError(
                f"Personalized Email ID: {personalized_email_id} not found in personalized outreach messages: {personalized_outreach_messages} in report ID: {lead_research_report_id}")
        email: LeadResearchReport.PersonalizedEmail = personalized_outreach_messages.personalized_emails[
            idx]

        if new_template_id:
            logger.info(
                f"Updating template in email ID: {personalized_email_id} in report ID: {lead_research_report_id}")
            new_template: OutreachEmailTemplate = db.get_outreach_email_template(
                outreach_email_template_id=new_template_id)

            # Convert new template to Personalized email template.
            email.template = new_template.to_personalized_email_outreach_template(
                message_index=new_message_index)

        if new_email_opener:
            logger.info(
                f"Updating email opener in email ID: {personalized_email_id} in report ID: {lead_research_report_id}")
            email.email_opener = new_email_opener

        if new_email_subject_line:
            logger.info(
                f"Updating email subject line in email ID: {personalized_email_id} in report ID: {lead_research_report_id}")
            email.email_subject_line = new_email_subject_line

        current_time = Utils.create_utc_time_now()
        email.last_updated_date = current_time
        email.last_updated_date_readable_str = Utils.to_human_readable_date_str(
            current_time)

        # Updated object in database.
        db.update_lead_research_report(lead_research_report_id=lead_research_report_id, setFields={
                                       "personalized_outreach_messages": personalized_outreach_messages.model_dump()})
        response = UpdateTemplateInPersonalizedEmailResponse(
            status=ResponseStatus.SUCCESS,
        )
        logger.info(
            f"Successfully updated personalized email ID: {personalized_email_id} for request: {request.json} in report ID: {lead_research_report_id}")
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to update personalized email ID: {personalized_email_id} with a new template with ID: {new_template_id} in report with ID: {lead_research_report_id} with error: {e}")
        raise APIException(
            status_code=500, message="Failed to update template in personalized email due to an error.")


class CreatePersonalizedEmailResponse(BaseModel):
    """API response for creating personalized email for a given highlight."""
    status: ResponseStatus = Field(...,
                                   description="Status (success) of the response.")
    personalized_email: LeadResearchReport.PersonalizedEmail = Field(
        ..., description="Created personalized email.")

    @field_validator('status')
    @classmethod
    def status_must_be_success(cls, v: ResponseStatus) -> str:
        if v != ResponseStatus.SUCCESS:
            raise ValueError(f'Expected success status, got: {v}')
        return v


@bp.post('/v1/lead-research-reports/personalized-emails')
@login_required
@rate_limiter.limit(key_func=lambda: g.user["uid"], limit_value=get_value)
def create_personalized_email():
    """Creates a personalized outreach email for given highlight in the given lead report."""
    db = Database()
    user_id: str = g.user["uid"]
    logger.info(
        f"Got request to create personalized email by user ID: {user_id}.")

    lead_research_report_id: str = None
    highlight_id: str = None
    try:
        lead_research_report_id = request.json.get(
            "lead_research_report_id")
        highlight_id = request.json.get("highlight_id")
    except Exception as e:
        logger.exception(
            f"Invalid request: {request} to create personalized email for user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters to create personalized email.")

    try:
        # Fetch highlight for given ID from the report.
        lead_research_report = db.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)
        report_details: Optional[List[LeadResearchReport.ReportDetail]
                                 ] = lead_research_report.details
        if report_details == None:
            raise ValueError(
                f"Report Details is None, expected not None value in report ID: {lead_research_report_id}")
        highlight: Optional[LeadResearchReport.ReportDetail.Highlight] = None
        for detail in report_details:
            for hl in detail.highlights:
                if hl.id == highlight_id:
                    highlight = hl
                    break
        if not highlight:
            raise ValueError(
                f"Could not find Highlight with ID: {highlight_id} in report ID: {lead_research_report_id}")

        # The algorithm here tries to smartly detect which template to use for generating the personalized email. It is as follows:
        # [1] Sort existing personalized emails in report in order of most recently updated to least recently updated.
        # [2] Pick the first email that has a template (not None) and note down the last updated date for this email.
        # [3] If the email's last updated date is equal to creation date, then it was created by the system on lead report creation and no were done by the user.
        #     In this case, use the frst message in this template for new outreach email creation.
        # [4] If the email's last updated date is different from creation date, it means the user has edited email subject line, body or template from the UI,
        #     Use this as hint that the template in this email was already used. So use the next message (follow up) in this template for outreach email creation.
        # [5] If our guess is wrong, the user can always manually elect a different template from the UI.
        personalized_outreach_messages: Optional[LeadResearchReport.PersonalizedOutreachMessages] = lead_research_report.personalized_outreach_messages
        if not personalized_outreach_messages or not personalized_outreach_messages.personalized_emails or not personalized_outreach_messages.total_tokens_used:
            raise ValueError(
                f"Personalized Outreach Messages or personalized emails or tokens is None, expected not None value in report ID: {lead_research_report_id}")
        personalized_emails: List[LeadResearchReport.PersonalizedEmail] = personalized_outreach_messages.personalized_emails
        if len(personalized_emails) == 0:
            raise ValueError(
                f"Expected personalied emails to be not empty, got empty in report ID: {lead_research_report_id}")

        # Sort emails by last updated date.
        sorted_emails: List[LeadResearchReport.PersonalizedEmail] = sorted(
            personalized_emails, key=lambda e: e.last_updated_date, reverse=True)
        email_template: Optional[LeadResearchReport.ChosenOutreachEmailTemplate] = None
        for email in sorted_emails:
            if not email.template:
                continue

            if email.last_updated_date == email.creation_date:
                # Created by system and likely not used by the user for outreach yet.
                # Use the same template.
                logger.info(
                    f"Using template with ID: {email.template.id} and message index: 0 to create personalized email for highlight ID: {highlight_id}, report ID: {lead_research_report_id} requested by user: {user_id}")
                email_template = email.template
            else:
                # User has edited this email so likely has used it before.
                # Set email template to the next message if there is one else set to current template.
                next_message_index: int = email.template.message_index + 1
                orig_template: OutreachEmailTemplate = db.get_outreach_email_template(
                    outreach_email_template_id=email.template.id)
                if next_message_index < len(orig_template.messages):
                    # Next message index exists, get personalized email template with this index.
                    logger.info(
                        f"Using template with ID: {email.template.id} and message index: {next_message_index} to create personalized email for highlight ID: {highlight_id}, report ID: {lead_research_report_id} requested by user: {user_id}")
                    email_template = orig_template.to_personalized_email_outreach_template(
                        message_index=next_message_index)
                else:
                    logger.info(
                        f"Next message index: {next_message_index} not found, using template with ID: {email.template.id} and and current message index: {email.template.message_index} to create personalized email for highlight ID: {highlight_id}, report ID: {lead_research_report_id} requested by user: {user_id}")
                    # Next index doesn't exist. Just use current personalzed email template.
                    email_template = email.template

            break

        # Create email.
        pz = Personalization(database=db)
        created_email: LeadResearchReport.PersonalizedEmail = pz.create_personalized_email(
            highlight=highlight, email_template=email_template, lead_research_report=lead_research_report)
        tokens_used = pz.get_tokens_used()

        # Update created email and tokens in database.
        personalized_emails.append(created_email)
        existing_tokens_used: OpenAITokenUsage = personalized_outreach_messages.total_tokens_used
        existing_tokens_used.add_tokens(tokens_used)
        setFields = {
            "personalized_outreach_messages": personalized_outreach_messages.model_dump(),
        }
        db.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)
        logger.info(
            f"Successfully created personalized email for highlight ID: {highlight_id} in lead report ID: {lead_research_report_id} for user ID: {user_id}")
        response = CreatePersonalizedEmailResponse(
            status=ResponseStatus.SUCCESS, personalized_email=created_email)
        return response.model_dump()
    except Exception as e:
        logger.exception(
            f"Failed to create personalized email for report ID: {lead_research_report_id} and highlight ID: {highlight_id} for user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=500, message="Failed to create personalized email due to an internal error.")


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
    messages: List[str] = None
    try:
        name = request.json.get("name")
        persona_role_titles = [title.strip() for title in request.json.get(
            "persona_role_titles").split(",")]
        description = request.json.get("description")
        messages = request.json.get("messages")
        if len(messages) == 0:
            raise ValueError(
                "Outreach template messages cannot be empty in request")
    except Exception as e:
        logger.exception(
            f"Invalid request: {request} to create outreach email template by user ID: {user_id} with error: {e}")
        raise APIException(
            status_code=400, message="Invalid request parameters for template creation")

    try:
        outreach_email_template = OutreachEmailTemplate(
            user_id=user_id, name=name, persona_role_titles=persona_role_titles, description=description, messages=messages)
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
            "messages": 1,
            "creation_date_readable_str": 1,
            "last_updated_date_readable_str": 1,
        }
        outreach_email_templates: List[OutreachEmailTemplate] = db.list_outreach_email_templates(
            user_id=user_id, projection=projection)
        user = db.get_user(
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
    messages: List[str] = None
    try:
        name = request.json.get("name")
        persona_role_titles = [title.strip() for title in request.json.get(
            "persona_role_titles").split(",")]
        description = request.json.get("description")
        messages = request.json.get("messages")
        if len(messages) == 0:
            raise ValueError(
                "Outreach template messages cannot be empty in request")
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
            "messages": messages,
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


@bp.get('/v1/admin/debug/<string:report_id>')
def admin_debug(report_id: str):
    logger.info(f"Got Debug request for report ID: {report_id}")
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

    WARNING: DO NOT USE IN PRODUCTION. This method has bugs and should be rewritten before it is used properly
    in production.
    """
    # Remove return when there is safe to use.
    return
    database = Database()
    report = database.get_lead_research_report(
        lead_research_report_id=lead_research_report_id, projection={"company_profile_id": 1})
    company_profile_id: str = report.company_profile_id
    # TODO: We probably want to delete only those Content Details (or highlights) in current report that are orphaned
    # i.e. do not show up as highlights in any of the research report highlights across the database. For a given report,
    # get all highlight IDs and then write an aggregation pipeline to fetch all reports (other than the one being deleted) that have
    # any of the given highlight IDs. If there are other reports that reference the hightlights, we won't delete
    # those content details.
    logger.info(
        f"Will delete all associated artifacts with company profile ID: {company_profile_id} across all reports.")
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


@bp.post('/v1/admin/migration')
def admin_migration():
    logger.info("Got Migration request")
    db = Database()
    num_emails_updated = 0

    dry_run: bool = request.json.get("dry_run")
    logger.info(f"Dry run: {dry_run}")

    # Remove return when there is a new migration to do.
    return

    for report in db.list_lead_research_reports(filter={"personalized_outreach_messages": {"$ne": None}}, projection={"personalized_outreach_messages": 1}):
        update_report: bool = False
        for email in report.personalized_outreach_messages.personalized_emails:
            if email.template and not email.template.message_index:
                # Set message index to 0 by default.
                email.template.message_index = 0
                num_emails_updated += 1
                update_report = True

        if dry_run and update_report:
            db.update_lead_research_report(lead_research_report_id=report.id, setFields={
                "personalized_outreach_messages": report.personalized_outreach_messages.model_dump()})

    if not dry_run:
        logger.info(
            f"Successfully completed migration request. Num updated emails: {num_emails_updated}")
    else:
        logger.info(
            f"This is a dry run, will update: {num_emails_updated} emails")
    return Response("ok\n")


#######################
# Start of Celery Tasks
#######################


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
            process_content_in_search_results_in_background.delay(
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
        rp = Researcher(database=database)
        rp.enrich_lead_info(
            lead_research_report_id=lead_research_report_id)
        logger.info(
            f"Enriched lead successfully in report ID: {lead_research_report_id} for user ID: {user_id}.")

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
        process_content_in_search_results_in_background.delay(
            user_id=user_id, lead_research_report_id=lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_search_results_fetched", properties={
            "report_id": lead_research_report_id, "time_taken_seconds": time.time() - start_time})
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id,
                                      e=e, task_name="fetch_search_results", status_before_failure=LeadResearchReport.Status.BASIC_PROFILE_FETCHED)


@shared_task(bind=True, acks_late=True)
def process_content_in_search_results_in_background(self, user_id: str, lead_research_report_id: str):
    """Processes URLs in search results in background."""
    logger.info(
        f"Start processing search URLs to process for lead report: {lead_research_report_id} for user ID: {user_id}")
    database = Database()
    try:
        research_report: LeadResearchReport = database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)
        search_results_list: List[LeadResearchReport.WebSearchResults.Result] = research_report.web_search_results.results
        total_urls_to_process: int = research_report.web_search_results.num_results

        # Split search URLs into batches depending on the number of concurrent processes in a worker.
        # Note: This concurrency value must match the concurreny passed during app intialization.
        # TODO: Make this read the concurrency value from the celery start command line argument.
        concurrency = 12
        batch_size = int(total_urls_to_process/concurrency) + \
            (0 if total_urls_to_process % concurrency == 0 else 1)
        logger.info(
            f"Splitting a total of {total_urls_to_process} Search URLs using {concurrency} workers which will each handle at max {batch_size} URLs for processing for lead report: {lead_research_report_id} and user ID: {user_id}.")
        batches: List[LeadResearchReport.WebSearchResults.Result] = []
        for i in range(concurrency):
            start_idx = i*batch_size
            end_idx = start_idx + batch_size
            batches.append(search_results_list[start_idx: end_idx])
            if end_idx >= total_urls_to_process:
                break

        logger.info(
            f"Num batches: {len(batches)} for report: {lead_research_report_id} for user ID: {user_id}")
        logger.info(
            f"Batching nums: {[len(b) for b in batches]} for report: {lead_research_report_id} for user ID: {user_id}")

        parallel_workers = [process_content_in_search_results_batch_in_background.s(
            num, user_id, lead_research_report_id, [r.model_dump_json() for r in batch]) for num, batch in enumerate(batches)]
        aggregation_work = aggregate_processed_search_results_in_background.s(
            user_id, lead_research_report_id)
        aggregation_error_callback = on_process_content_in_search_results_batch_error.s(
            user_id, lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_search_results_start_processing", properties={
            "report_id": lead_research_report_id, "start_time": time.time(), "total_urls": total_urls_to_process, "concurrency": concurrency, "batch_sizes": [len(b) for b in batches]})

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


@shared_task(bind=True, acks_late=True)
def aggregate_processed_search_results_in_background(self, failed_urls_list: List[List[str]], user_id: str, lead_research_report_id: str):
    """Aggregate processing of search results from each worker task that worked on a batch."""
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
            f"Completed aggregation of processed search results for lead report ID: {lead_research_report_id} for user ID: {user_id}")

        # Aggregate Report next.
        aggregate_report_in_background.delay(
            user_id=user_id, lead_research_report_id=lead_research_report_id)

        # Send event.
        Metrics().capture(user_id=user_id, event_name="report_search_results_processed", properties={
            "report_id": lead_research_report_id, "end_time": time.time(), "failed_urls": flattened_urls_list, "num_failed_urls": len(flattened_urls_list)})
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name=f"aggregate_processed_search_results", status_before_failure=LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED)


@shared_task(acks_late=True)
def on_process_content_in_search_results_batch_error(request, exc, traceback, user_id: str, lead_research_report_id: str):
    """Handler in any of the search result processing tasks timeout due to hard timeout limit.

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
        r = Researcher(database=database)
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
        if lead_report.content_parsing_total_tokens_used:
            total_cost += lead_report.content_parsing_total_tokens_used.total_cost_in_usd
        if lead_report.personalized_outreach_messages and lead_report.personalized_outreach_messages.total_tokens_used:
            total_cost += lead_report.personalized_outreach_messages.total_tokens_used.total_cost_in_usd
        m.capture(user_id=user_id, event_name="report_generation_cost_in_usd", properties={
                  "report_id": lead_research_report_id, "cost_in_usd": total_cost})
    except Exception as e:
        shared_task_exception_handler(shared_task_obj=self, database=database, user_id=user_id, lead_research_report_id=lead_research_report_id, e=e,
                                      task_name="choose_template_and_create_emails", status_before_failure=LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE)
