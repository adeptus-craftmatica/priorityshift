import click


def register_cli_commands(app):
    @app.cli.command("seed-db")
    def seed_db():
        """Populate roles, permissions, catalogs, demo users, and demo work
        items so the app isn't empty on first run."""
        from seed import run_seed
        run_seed()
        click.echo("Database seeded.")

    @app.cli.command("generate-occurrences")
    def generate_occurrences():
        """Create any chore occurrences that are now due."""
        from app.extensions import db
        from app.services.chore_service import generate_due_occurrences_for_all

        created = generate_due_occurrences_for_all()
        db.session.commit()
        click.echo(f"Generated {len(created)} chore occurrence(s).")
