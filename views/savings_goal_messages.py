from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from model.savings_goals_model import SavingsGoalBoundsError
from utils.i18n import tr, trf
from utils.money import format_money


def _format_param(value: object) -> object:
    if isinstance(value, (int, float)):
        return format_money(float(value))
    return value


def savings_goal_bounds_text(error: SavingsGoalBoundsError) -> str:
    params = {key: _format_param(value) for key, value in error.params.items()}
    return trf(error.message_key, **params)


def show_savings_goal_bounds_warning(
    parent: QWidget | None, error: SavingsGoalBoundsError
) -> None:
    QMessageBox.warning(
        parent, tr("savings.bounds.title"), savings_goal_bounds_text(error)
    )
