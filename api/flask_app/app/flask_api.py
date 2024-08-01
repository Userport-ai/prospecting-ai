from flask import Blueprint, request, abort
from app.database import Database
from app.models import LeadResearchReport
from app.research_report import ResearchReport

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/v1/lead_report', methods=['GET', 'POST'])
def lead_report():
    db = Database()

    if request.method == "POST":
        # Create research report.
        rp = ResearchReport(database=db)
        person_linkedin_url = request.form.get('linkedin_url')
        try:
            report_id: str = rp.create(person_linkedin_url=person_linkedin_url)
            # TODO: Add report to background worker to continue processing.

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
