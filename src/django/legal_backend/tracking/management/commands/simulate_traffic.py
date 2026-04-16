from django.core.management.base import BaseCommand

from tracking.simulation import run_simulation_to_db


class Command(BaseCommand):
    help = "Generate synthetic contextual Markov traffic and insert into Event table."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=40)
        parser.add_argument("--min-sessions", type=int, default=1)
        parser.add_argument("--max-sessions", type=int, default=3)
        parser.add_argument("--seed", type=int, default=None)

    def handle(self, *args, **options):
        result = run_simulation_to_db(
            users=options["users"],
            min_sessions=options["min_sessions"],
            max_sessions=options["max_sessions"],
            seed=options["seed"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Simulation done: users={result['users']} sessions={result['sessions_estimated']} "
                f"events={result['events_inserted']}"
            )
        )
