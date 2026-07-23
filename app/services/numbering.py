from app.models import Chore, Idea, Project, WorkRequest

_PREFIXES = {
    Project: "PRJ",
    Chore: "CHR",
    Idea: "IDA",
    WorkRequest: "REQ",
}


def next_number(model_cls) -> str:
    prefix = _PREFIXES[model_cls]
    count = model_cls.query.count()
    candidate = f"{prefix}-{1000 + count + 1}"
    while model_cls.query.filter_by(**{_number_field(model_cls): candidate}).first():
        count += 1
        candidate = f"{prefix}-{1000 + count + 1}"
    return candidate


def _number_field(model_cls) -> str:
    return {
        Project: "project_number",
        Chore: "chore_number",
        Idea: "idea_number",
        WorkRequest: "request_number",
    }[model_cls]
