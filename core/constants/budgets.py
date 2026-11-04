from enum import Enum


class BudgetPeriod(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BudgetStatus(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    EXCEEDED = "exceeded"
