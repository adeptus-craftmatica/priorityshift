from flask_wtf import FlaskForm
from wtforms import DateField, FloatField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

from app.models.chore import RECURRENCE_TYPES
from app.models.idea import REVIEW_STATUSES


class IdeaForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    description = TextAreaField("Description")
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    potential_value = TextAreaField("Potential value")
    expected_benefit = TextAreaField("Expected benefit")
    possible_users_affected = StringField("Who would this affect?")
    estimated_effort_hours = FloatField("Estimated effort (hours), if known", validators=[Optional()])
    notes = TextAreaField("Notes")
    tag_names = StringField("Tags (comma-separated)")


class IdeaStatusForm(FlaskForm):
    review_status = SelectField("Status", choices=[(s, s.replace("_", " ").title()) for s in REVIEW_STATUSES if not s.startswith("converted")])


class ConvertToProjectForm(FlaskForm):
    priority_level_id = SelectField("Priority", coerce=int)
    phase_id = SelectField("Starting phase", coerce=int)
    target_deadline = DateField("Target deadline", validators=[Optional()])


class ConvertToChoreForm(FlaskForm):
    priority_level_id = SelectField("Priority", coerce=int)
    recurrence_type = SelectField("Recurrence", choices=[(r, r.replace("_", " ").title()) for r in RECURRENCE_TYPES])
    due_date = DateField("Due date / first occurrence", validators=[Optional()])
