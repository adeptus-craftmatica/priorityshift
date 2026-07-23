from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in", default=True)
    # Deliberately not named "submit" — a field/button named "submit" shadows
    # the DOM's native form.submit() method (the element becomes the value
    # of form.submit instead of the function), which silently breaks any
    # JS-driven submission such as password-manager autofill+submit.
    submit_button = SubmitField("Sign in")


class MfaCodeForm(FlaskForm):
    code = StringField("Authentication code", validators=[
        DataRequired(), Length(min=6, max=6), Regexp(r"^\d{6}$", message="Enter the 6-digit code."),
    ])
    submit_button = SubmitField("Verify")


class MfaDisableForm(FlaskForm):
    password = PasswordField("Current password", validators=[DataRequired()])
    submit_button = SubmitField("Disable two-factor authentication")
