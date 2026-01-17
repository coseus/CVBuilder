# components/__init__.py
# Keep this minimal and only export functions that definitely exist.

from .photo_upload import render_photo_upload
from .work_experience import render_work_experience
from .education import render_education

from .ats_personal_info import render_ats_personal_info
from .ats_summary import render_ats_summary
from .ats_skills import render_ats_skills
from .ats_helper_panel import render_ats_helper_panel

from .europass_complete import render_europass_complete
from .profile_manager import render_profile_manager
from .ats_dashboard import render_ats_score_dashboard
