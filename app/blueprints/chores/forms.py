from flask_wtf import FlaskForm
from wtforms import (
    BooleanField, DateField, IntegerField, SelectField, StringField,
    TextAreaField, TimeField,
)
from wtforms.validators import DataRequired, NumberRange, Optional

from app.models.chore import RECURRENCE_TYPES


class ChoreForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    description = TextAreaField("Description")

    assigned_user_id = SelectField("Assigned user", coerce=int, validators=[Optional()])
    assigned_team_id = SelectField("Assigned team", coerce=int, validators=[Optional()])
    priority_level_id = SelectField("Priority", coerce=int)

    recurrence_type = SelectField("Recurrence", choices=[(r, r.replace("_", " ").title()) for r in RECURRENCE_TYPES])
    day_of_month = IntegerField("Day of month (1-31)", validators=[Optional(), NumberRange(min=1, max=31)])
    weekday = SelectField("Weekday", choices=[
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
    ], coerce=int, validators=[Optional()])
    interval_days = IntegerField("Repeat every N days", validators=[Optional(), NumberRange(min=1)])

    due_date = DateField("Due date / first occurrence", validators=[Optional()])
    preferred_time_of_day = TimeField("Preferred time of day", validators=[Optional()])
    estimated_duration_minutes = IntegerField("Estimated duration (minutes)", validators=[Optional(), NumberRange(min=0)])
    required_evidence = BooleanField("Requires evidence/attachment on completion")

    notes = TextAreaField("Notes")
    tag_names = StringField("Tags (comma-separated)")


class ChoreCompleteForm(FlaskForm):
    actual_duration_minutes = IntegerField("Actual duration (minutes)", validators=[Optional(), NumberRange(min=0)])
    notes = TextAreaField("Notes", validators=[Optional()])


class ChoreSkipForm(FlaskForm):
    skip_reason = TextAreaField("Reason for skipping", validators=[DataRequired()])


class ChoreReassignForm(FlaskForm):
    new_user_id = SelectField("Reassign to", coerce=int, validators=[DataRequired()])


class ChoreEscalateForm(FlaskForm):
    escalated_reason = TextAreaField("Why is this blocked?", validators=[DataRequired()])
