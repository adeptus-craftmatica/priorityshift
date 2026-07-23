from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, IntegerField, SelectField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional


class PriorityChangeForm(FlaskForm):
    new_priority_level_id = SelectField("New priority", coerce=int, validators=[DataRequired()])
    reason = TextAreaField("Reason for this change", validators=[DataRequired()])
    business_justification = TextAreaField("Business justification", validators=[Optional()])
    expected_interruption_minutes = IntegerField("Expected interruption time (minutes)", validators=[Optional(), NumberRange(min=0)])
    is_temporary = BooleanField("This is a temporary reprioritization")
    resume_date = DateField("Resume original work on", validators=[Optional()])
    acknowledged = BooleanField("I acknowledge the impact shown above", validators=[DataRequired()])
    override_blocks = BooleanField("Override blocking rules (requires approval permission)")
