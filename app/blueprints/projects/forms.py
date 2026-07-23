from flask_wtf import FlaskForm
from wtforms import (
    BooleanField, DateField, FloatField, IntegerField, SelectField,
    SelectMultipleField, StringField, TextAreaField,
)
from wtforms.validators import DataRequired, NumberRange, Optional

from app.models.project import CATEGORIES


class ProjectForm(FlaskForm):
    title = StringField("Project title", validators=[DataRequired()])
    description = TextAreaField("Description")

    category = SelectField("Category", choices=[(c, c.replace("_", " ").title()) for c in CATEGORIES])
    is_client = BooleanField("Client project")
    is_paid = BooleanField("Paid work")
    client_id = SelectField("Client", coerce=int, validators=[Optional()])

    priority_level_id = SelectField("Priority", coerce=int)
    phase_id = SelectField("Phase", coerce=int)

    requesting_department_id = SelectField("Requesting department", coerce=int, validators=[Optional()])
    owner_id = SelectField("Project owner", coerce=int, validators=[Optional()])
    approving_manager_id = SelectField("Approving manager", coerce=int, validators=[Optional()])
    assignee_ids = SelectMultipleField("Assigned developers", coerce=int, validators=[Optional()])

    date_requested = DateField("Date requested", validators=[Optional()])
    date_started = DateField("Date work began", validators=[Optional()])
    target_deadline = DateField("Target deadline", validators=[Optional()])

    estimated_effort_hours = FloatField("Estimated effort (hours)", validators=[Optional(), NumberRange(min=0)])
    percent_complete = IntegerField("Percent complete", validators=[Optional(), NumberRange(min=0, max=100)])

    risks = TextAreaField("Anticipated risks")
    roadblocks = TextAreaField("Active roadblocks")
    notes = TextAreaField("Notes")
    related_links = TextAreaField("Related links")
    tag_names = StringField("Tags (comma-separated)")


class HealthUpdateForm(FlaskForm):
    health_status = SelectField("Status", choices=[
        ("on_track", "Yes — On Track"), ("at_risk", "Maybe — At Risk"), ("off_track", "No — Off Track"),
    ])
    health_reason = TextAreaField("Reason", validators=[Optional()])


class InterruptionLogForm(FlaskForm):
    new_task_description = StringField("What are you being asked to do instead?", validators=[DataRequired()])
    reason = TextAreaField("Why did this interruption happen?")
    duration_minutes = IntegerField("Time consumed (minutes)", validators=[DataRequired(), NumberRange(min=1)])
    context_switch_minutes = IntegerField("Extra context-switch/recovery time (minutes)", validators=[Optional(), NumberRange(min=0)])
    resumed_original = BooleanField("Did you resume the original work?")
    deadline_affected = BooleanField("Did this affect a deadline?")
    notes = TextAreaField("Notes", validators=[Optional()])


class TimeEntryForm(FlaskForm):
    entry_date = DateField("Date", validators=[DataRequired()])
    hours = FloatField("Hours", validators=[DataRequired(), NumberRange(min=0.1)])
    category = SelectField("Category", choices=[("planned", "Planned"), ("unplanned", "Unplanned")])
    notes = StringField("Notes", validators=[Optional()])
