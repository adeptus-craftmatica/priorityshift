from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class WorkRequestForm(FlaskForm):
    title = StringField("Request title", validators=[DataRequired()])
    description = TextAreaField("Description")
    business_need = TextAreaField("Business need")
    requesting_department_id = SelectField("Requesting department", coerce=int, validators=[Optional()])
    desired_completion_date = DateField("Desired completion date", validators=[Optional()])
    requested_priority_id = SelectField("Requested priority", coerce=int, validators=[Optional()])
    is_client = BooleanField("Client-related")
    is_paid = BooleanField("Paid work")
    estimated_business_impact = TextAreaField("Estimated business impact")
    approver_id = SelectField("Approver", coerce=int, validators=[Optional()])


class RequestDecisionForm(FlaskForm):
    decision_notes = TextAreaField("Notes", validators=[Optional()])
