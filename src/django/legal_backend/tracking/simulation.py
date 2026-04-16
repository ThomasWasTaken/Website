import random
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from .models import Event


ALLOWED_PAGES = [
    "legal_site_agentveiw",
    "testamente",
    "ægtepagt",
    "samejeoverenskomst",
    "fuldmagt",
    "juridisk-konsultation",
    "lejekontrakt",
]

CHANNELS = [
    ("direct", 0.35),
    ("ref:linkedin.com", 0.18),
    ("ref:google.com", 0.22),
    ("campaign:spring_launch", 0.10),
    ("campaign:retargeting", 0.15),
]


@dataclass
class SimulationConfig:
    users: int = 40
    min_sessions_per_user: int = 1
    max_sessions_per_user: int = 3
    seed: int | None = None


class ContextualMarkovTrafficSimulator:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = random.Random(config.seed)

    # -------------------------
    # Utilities
    # -------------------------

    def _weighted_choice(self, weighted_values):
        values, weights = zip(*weighted_values)
        return self.rng.choices(values, weights=weights, k=1)[0]

    def _sample_user_profile(self):
        return {
            "intent": self._weighted_choice([
                ("high", 0.25),   # slightly more high intent
                ("medium", 0.5),
                ("low", 0.25),
            ]),
            "device": self._weighted_choice([
                ("mobile", 0.7),
                ("desktop", 0.3),
            ]),
        }

    # -------------------------
    # Transition Logic (IMPROVED)
    # -------------------------

    def _next_state(self, current_state: str, page: str, profile: dict, channel: str):
        base = {
            "start": [("page_view", 1.0)],

            # Reduced bounce slightly
            "page_view": [
                ("section_view_hero", 0.6),
                ("scroll_25", 0.2),
                ("end", 0.2),
            ],

            "section_view_hero": [
                ("scroll_25", 0.4),
                ("click_cta", 0.3),  # increased
                ("end", 0.3),
            ],

            "scroll_25": [
                ("scroll_50", 0.5),
                ("click_cta", 0.25),
                ("end", 0.25),
            ],

            "scroll_50": [
                ("section_view_pricing", 0.4),
                ("click_cta", 0.35),  # increased
                ("scroll_25", 0.1),
                ("end", 0.15),
            ],

            "section_view_pricing": [
                ("click_cta", 0.45),  # increased
                ("section_view_faq", 0.2),
                ("scroll_50", 0.1),
                ("end", 0.25),
            ],

            # Higher CTA effectiveness
            "click_cta": [
                ("form_view", 0.45),
                ("end", 0.55),
            ],

            # Higher form completion
            "form_view": [
                ("consultation_form_submit", 0.65),
                ("end", 0.35),
            ],

            # Higher booking rate
            "consultation_form_submit": [
                ("appointment_booked", 0.35),
                ("end", 0.65),
            ],

            "section_view_faq": [
                ("click_cta", 0.25),
                ("end", 0.75),
            ],

            "appointment_booked": [("end", 1.0)],
        }

        # Page-specific constraint (still allow some conversion)
        if page != "juridisk-konsultation":
            base["click_cta"] = [
                ("form_view", 0.15),
                ("end", 0.85),
            ]

        probs = dict(base.get(current_state, [("end", 1.0)]))

        # -------------------------
        # Contextual adjustments
        # -------------------------

        # Intent-based boost
        if profile["intent"] == "high":
            if "click_cta" in probs:
                probs["click_cta"] *= 1.4
            if "form_view" in probs:
                probs["form_view"] *= 1.4
            if "appointment_booked" in probs:
                probs["appointment_booked"] *= 1.4
            if "end" in probs:
                probs["end"] *= 0.7

        elif profile["intent"] == "low":
            if "end" in probs:
                probs["end"] *= 1.4

        # Campaign traffic converts better
        if "campaign" in channel:
            if "form_view" in probs:
                probs["form_view"] *= 1.3
            if "appointment_booked" in probs:
                probs["appointment_booked"] *= 1.2

        # Normalize
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}

        return self._weighted_choice(list(probs.items()))

    # -------------------------
    # Event Mapping
    # -------------------------

    def _event_from_state(self, state: str, page: str):
        if state == "page_view":
            return {"action": "page_view", "section": "page", "step": "landing", "target": f"/{page}.html"}

        if state.startswith("section_view_"):
            section = state.replace("section_view_", "", 1)
            return {
                "action": "section_view",
                "section": section,
                "step": "engagement",
                "target": section,
                "metadata": {"funnel_step": f"view_{section}"},
            }

        if state.startswith("scroll_"):
            percent = int(state.replace("scroll_", "", 1))
            return {
                "action": "scroll_depth",
                "section": "engagement",
                "step": "engagement",
                "target": f"{percent}%",
                "metadata": {"scroll_percent": percent},
            }

        if state == "click_cta":
            return {
                "action": "click_cta",
                "section": "pricing",
                "step": "consideration",
                "target": "#consultation-form",
            }

        if state == "form_view":
            return {
                "action": "section_view",
                "section": "consultation-form",
                "step": "booking",
                "target": "consultation-form",
            }

        if state == "consultation_form_submit":
            return {
                "action": "consultation_form_submit",
                "section": "consultation-form",
                "step": "booking",
                "target": "consultation_request",
            }

        if state == "appointment_booked":
            return {
                "action": "appointment_booked",
                "section": "consultation-form",
                "step": "booking",
                "target": str(uuid.uuid4())[:12],
            }

        return None

    # -------------------------
    # Core Simulation
    # -------------------------

    def generate_events(self):
        now = timezone.now()
        rows = []

        for _ in range(self.config.users):
            user_id = f"sim-user-{uuid.uuid4().hex[:10]}"
            profile = self._sample_user_profile()

            session_count = self.rng.randint(
                self.config.min_sessions_per_user,
                self.config.max_sessions_per_user
            )

            for _ in range(session_count):
                session_id = f"sim-session-{uuid.uuid4().hex[:12]}"
                page = self.rng.choice(ALLOWED_PAGES)
                channel = self._weighted_choice(CHANNELS)

                # better time distribution
                hour = self.rng.randint(0, 23)
                offset = int(abs((hour - 20) ** 2) * self.rng.random())
                ts = now - timedelta(minutes=offset)

                current_state = "start"
                step_idx = 0

                while step_idx < 20:
                    next_state = self._next_state(current_state, page, profile, channel)

                    if next_state == "end":
                        break

                    event = self._event_from_state(next_state, page)
                    current_state = next_state
                    step_idx += 1

                    if not event:
                        continue

                    # realistic timing
                    if next_state.startswith("scroll"):
                        delay = self.rng.randint(2, 10)
                    elif next_state == "form_view":
                        delay = self.rng.randint(10, 40)
                    else:
                        delay = self.rng.randint(5, 25)

                    ts += timedelta(seconds=delay)

                    metadata = event.get("metadata", {})
                    metadata.update({
                        "source_channel": channel,
                        "intent": profile["intent"],
                        "device": profile["device"],
                    })

                    referrer = (
                        "https://google.com" if "google" in channel else
                        "https://linkedin.com" if "linkedin" in channel else
                        ""
                    )

                    rows.append(
                        Event(
                            timestamp=ts,
                            page=page,
                            step=event.get("step", ""),
                            section=event.get("section", ""),
                            action=event.get("action", ""),
                            service=page,
                            target=(event.get("target", "") or "")[:255],
                            user_id=user_id,
                            session_id=session_id,
                            url=f"http://127.0.0.1:8000/{page}.html",
                            referrer=referrer,
                            user_agent=f"SyntheticTrafficBot/1.0 ({profile['device']})",
                            metadata=metadata,
                        )
                    )

        return rows


# -------------------------
# Entry Point
# -------------------------

def run_simulation_to_db(users=40, min_sessions=1, max_sessions=3, seed=None):
    config = SimulationConfig(
        users=max(1, int(users)),
        min_sessions_per_user=max(1, int(min_sessions)),
        max_sessions_per_user=max(int(min_sessions), int(max_sessions)),
        seed=seed,
    )

    simulator = ContextualMarkovTrafficSimulator(config)
    rows = simulator.generate_events()

    Event.objects.bulk_create(rows, batch_size=1000)

    return {
        "users": config.users,
        "events_inserted": len(rows),
        "sessions_estimated": len({row.session_id for row in rows}),
    }