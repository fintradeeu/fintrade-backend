"""
Import all models here so Alembic and `Base.metadata.create_all` can discover them.
"""


def import_all_models():
    """Side-effect import of every model module."""
    import app.modules.auth.models  # noqa: F401
    import app.modules.courses.models  # noqa: F401
    import app.modules.exams.models  # noqa: F401
    import app.modules.offers.models  # noqa: F401
    import app.modules.lectures.models  # noqa: F401
    import app.modules.ai.models  # noqa: F401
    import app.modules.distributors.models  # noqa: F401
    import app.modules.learning.models  # noqa: F401
    import app.modules.certificates.models  # noqa: F401
    import app.modules.simulator.models  # noqa: F401
    import app.modules.placement.models  # noqa: F401
    import app.modules.feedback.models  # noqa: F401
    import app.modules.dashboard.models  # noqa: F401
    import app.modules.kyc.models  # noqa: F401
    import app.modules.roles.models  # noqa: F401
    import app.modules.news.models  # noqa: F401
    import app.modules.settings.models  # noqa: F401
    import app.modules.payments.models  # noqa: F401


# Also run on import so `from app.db.base import ...` triggers discovery
import_all_models()
