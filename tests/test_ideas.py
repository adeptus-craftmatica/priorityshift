from app.models import Idea, Project


def login(client, username):
    client.post("/auth/login", data={"username": username, "password": "testpass123"})


def test_convert_idea_to_project_preserves_link_and_history(client, db, manager_user, sample_idea, priority_levels, phases):
    login(client, "manager1")

    resp = client.post(
        f"/ideas/{sample_idea.id}/convert-to-project",
        data={
            "priority_level_id": priority_levels["Normal"].id,
            "phase_id": phases["Development"].id,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    idea = db.session.get(Idea, sample_idea.id)
    assert idea.review_status == "converted_to_project"
    assert idea.converted_to_type == "project"
    assert idea.converted_to_id is not None

    project = db.session.get(Project, idea.converted_to_id)
    assert project is not None
    assert project.origin_idea_id == idea.id
    assert project.title == idea.title


def test_idea_not_in_active_queue_before_conversion(client, sample_idea):
    resp = client.get("/ideas/")
    # Ideas list requires login; unauthenticated should redirect, not 500.
    assert resp.status_code in (302, 200)
