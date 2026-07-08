"""Admin controller, composed from domain mixins.

Split from the former 4,592-line controllers/admin_controller.py; every method
moved verbatim into exactly one mixin. The legacy import path
`from controllers.admin_controller import AdminController` still works via the
shim left at the old module.
"""

from controllers.admin.base import AdminBase
from controllers.admin.user_admin import UserAdmin
from controllers.admin.recruiter_admin import RecruiterAdmin
from controllers.admin.job_admin import JobAdmin
from controllers.admin.application_admin import ApplicationAdmin
from controllers.admin.cost_helpers import CostStatsHelpers
from controllers.admin.cost_stats_admin import CostStatsAdmin
from controllers.admin.credit_admin import CreditAdmin


class AdminController(
    UserAdmin,
    RecruiterAdmin,
    JobAdmin,
    ApplicationAdmin,
    CostStatsHelpers,
    CostStatsAdmin,
    CreditAdmin,
    AdminBase,
):
    """All admin domains share the collections wired in AdminBase.__init__."""
