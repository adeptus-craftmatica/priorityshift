from flask_wtf import FlaskForm
from wtforms import TextAreaField
from wtforms.validators import DataRequired, Length


class PortalCommentForm(FlaskForm):
    body = TextAreaField("Add a comment", validators=[DataRequired(), Length(max=2000)])
