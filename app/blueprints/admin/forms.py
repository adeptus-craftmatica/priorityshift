from flask_wtf import FlaskForm
from wtforms import (
    BooleanField, HiddenField, IntegerField, PasswordField, SelectField,
    SelectMultipleField, StringField, TextAreaField,
)
from wtforms.validators import DataRequired, EqualTo, Length, NumberRange, Optional


class UserForm(FlaskForm):
    id = HiddenField()
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    full_name = StringField("Full name", validators=[DataRequired()])
    password = PasswordField("Password", validators=[Optional(), Length(min=4)])
    role_id = SelectField("Role", coerce=int)
    manager_id = SelectField("Manager", coerce=int, validators=[Optional()])
    team_lead_id = SelectField("Team lead", coerce=int, validators=[Optional()])
    department_ids = SelectMultipleField("Departments", coerce=int, validators=[Optional()])
    team_ids = SelectMultipleField("Teams", coerce=int, validators=[Optional()])
    capacity_hours_per_week = IntegerField("Weekly capacity (hours)", default=40)
    active = BooleanField("Active", default=True)
    client_id = SelectField(
        "External client contact for", coerce=int, validators=[Optional()],
        description="Leave as None for internal staff. Setting this restricts the account to the client portal.",
    )


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )


class RoleForm(FlaskForm):
    id = HiddenField()
    name = StringField("Role name", validators=[DataRequired()])
    hierarchy_level = IntegerField("Hierarchy level (1 = highest authority)", validators=[DataRequired(), NumberRange(min=1)])
    description = StringField("Description")
    permissions = SelectMultipleField("Permissions", coerce=str)


class DepartmentForm(FlaskForm):
    id = HiddenField()
    name = StringField("Name", validators=[DataRequired()])
    description = StringField("Description")


class TeamForm(FlaskForm):
    id = HiddenField()
    name = StringField("Name", validators=[DataRequired()])
    description = StringField("Description")
    department_id = SelectField("Department", coerce=int, validators=[Optional()])


class PriorityLevelForm(FlaskForm):
    id = HiddenField()
    name = StringField("Name", validators=[DataRequired()])
    rank = IntegerField("Rank (1 = highest priority)", validators=[DataRequired()])
    color = StringField("Color (hex)", default="#6b7280")
    icon = StringField("Icon", default="flag")
    requires_acknowledgment = BooleanField("Requires acknowledgment when applied")
    active = BooleanField("Active", default=True)


class ProjectPhaseForm(FlaskForm):
    id = HiddenField()
    name = StringField("Name", validators=[DataRequired()])
    rank = IntegerField("Order", validators=[DataRequired()])
    is_terminal = BooleanField("Terminal phase (project is done)")
    active = BooleanField("Active", default=True)


class TagForm(FlaskForm):
    id = HiddenField()
    name = StringField("Name", validators=[DataRequired()])
    color = StringField("Color (hex)", default="#94a3b8")


class ClientForm(FlaskForm):
    id = HiddenField()
    name = StringField("Name", validators=[DataRequired()])
    account_owner_id = SelectField("Account owner", coerce=int, validators=[Optional()])
    active = BooleanField("Active", default=True)


class WorkflowRuleForm(FlaskForm):
    id = HiddenField()
    rule_type = SelectField("Rule type", choices=[
        ("max_critical_per_developer", "Max Critical projects per developer"),
        ("max_high_per_team", "Max High-priority projects per team"),
        ("require_exec_approval_for_critical", "Require executive approval for Critical"),
        ("require_reason_for_increase", "Require reason when increasing priority"),
        ("require_approval_for_deadline_push", "Require approval for large deadline pushes (threshold = days)"),
    ])
    description = StringField("Description")
    scope = SelectField("Scope", choices=[("global", "Global"), ("team", "Team"), ("department", "Department")])
    threshold = IntegerField("Threshold", validators=[Optional()])
    active = BooleanField("Active", default=True)
