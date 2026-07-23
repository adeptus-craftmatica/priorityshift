from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, TextAreaField
from wtforms.validators import DataRequired


class CommentForm(FlaskForm):
    body = TextAreaField("Comment", validators=[DataRequired()])
    is_decision = BooleanField("Mark as decision")
    is_blocker = BooleanField("Mark as blocker")
    client_visible = BooleanField("Visible to client")
    parent_comment_id = HiddenField()
