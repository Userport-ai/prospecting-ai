from flask import Blueprint
from app.database import Database
from app.models import LeadResearchReport

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/v1/lead_report', methods=['GET'])
def lead_report():
    db = Database()

    report: LeadResearchReport = None
    try:
        report = db.get_lead_research_report(
            lead_research_report_id="66aa17d158f79392393414a6")
    except Exception as e:
        raise ValueError("Failed to read report from database")

    return report.model_dump()
