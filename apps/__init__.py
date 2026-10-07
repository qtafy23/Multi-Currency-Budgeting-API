# Import all models to ensure they're registered with SQLAlchemy
# This enables Alembic auto-generation to detect all model changes

from apps.users.models import User  # noqa: F401

from .accounts import models as account_models  # noqa: F401
from .budgets import models as budget_models  # noqa: F401
from .exchange import models as exchange_models  # noqa: F401
from .transactions import models as transaction_models  # noqa: F401
