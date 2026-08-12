"""Review-first Home Assistant blueprint generation."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe


class BlueprintPlanner:
    """Recognise blueprint intent and install only a confirmed bounded draft."""

    def __init__(self, install_root=None, *, clock=None, ttl_seconds=600):
        self._root = None if install_root is None else Path(install_root)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._ttl = ttl_seconds
        self._awaiting = set()
        self._pending = {}

    def handle(self, text, conversation_id):
        raw = text.strip(); normalized = " ".join(raw.casefold().split())
        explicit = any(phrase in normalized for phrase in (
            "create a blueprint", "create blueprint", "make a blueprint",
            "build a blueprint", "blueprint for me",
        ))
        if explicit and len(normalized.split()) < 8:
            self._awaiting.add(conversation_id)
            return {
                "status": "clarification_required",
                "message": "Certainly. What should the blueprint do? Include its trigger, conditions, actions, and output devices.",
            }
        if not explicit and conversation_id not in self._awaiting:
            return None
        self._awaiting.discard(conversation_id)
        if not self._looks_complete(normalized):
            self._awaiting.add(conversation_id)
            return {
                "status": "clarification_required",
                "message": "I still need a trigger and at least one action before I can draft the blueprint.",
            }
        name = self._name(raw)
        yaml_text = (
            self._office_work_blueprint(name)
            if self._is_office_briefing(normalized)
            else self._generic_blueprint(name, raw)
        )
        self._validate(yaml_text)
        token = token_urlsafe(24)
        self._pending[token] = (
            self._clock() + timedelta(seconds=self._ttl),
            conversation_id,
            name,
            yaml_text,
        )
        return {
            "status": "requires_confirmation",
            "token": token,
            "summary": (
                f"Create the reusable automation blueprint “{name}”. It will expose graphical selectors "
                "for the short-press trigger, controlled targets, weather, work calendar, TTS provider, "
                "and output speaker. Morning, afternoon, weekday-calendar, and fallback toggle branches "
                "will run inside Home Assistant. No automation instance will be created yet"
            ),
            "risk": "configuration_confirmation_required",
            "action_payload": {"kind": "blueprint_install", "conversation_id": conversation_id},
        }

    def cancel(self, token): self._pending.pop(token, None)

    def confirm(self, token, payload):
        pending = self._pending.pop(token, None)
        if (
            pending is None or pending[0] < self._clock()
            or payload.get("kind") != "blueprint_install"
            or payload.get("conversation_id") != pending[1]
        ):
            return {"status": "forbidden", "message": "Blueprint confirmation is invalid or expired."}
        if self._root is None:
            return {"status": "unavailable", "message": "Home Assistant blueprint storage is not mounted."}
        name, yaml_text = pending[2], pending[3]
        folder = self._root / "blueprints" / "automation" / "project_jarvis"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_") + ".yaml")
        path.write_text(yaml_text, encoding="utf-8")
        return {
            "status": "success",
            "message": (
                f"Blueprint “{name}” has been installed. In Home Assistant, create an automation from "
                "that blueprint and select the Lumi short-press trigger and the six requested entities."
            ),
            "path": str(path),
        }

    @staticmethod
    def _looks_complete(text):
        return "trigger" in text and any(word in text for word in ("action", "turn on", "turn off", "toggle"))

    @staticmethod
    def _is_office_briefing(text):
        return "weather" in text and "calendar" in text and any(word in text for word in ("office", "work greeting"))

    @staticmethod
    def _name(text):
        match = re.search(
            r"\bname\s*:\s*(.+?)(?=\s+(?:trigger|conditions?|actions?)\s*:|[\r\n]|$)",
            text,
            re.IGNORECASE,
        )
        return (match.group(1).strip() if match else "Jarvis generated automation")[:80]

    @staticmethod
    def _validate(value):
        required = ("blueprint:", "domain: automation", "input:", "triggers:", "actions:", "!input")
        if not all(item in value for item in required) or "../" in value:
            raise ValueError("generated blueprint failed structural validation")

    @staticmethod
    def _generic_blueprint(name, description):
        clean_name = name.replace('"', '')
        clean_description = " ".join(description.replace('"', "'").split())[:500]
        return f'''blueprint:
  name: "{clean_name}"
  description: "Jarvis draft: {clean_description}"
  domain: automation
  author: Project Jarvis
  homeassistant:
    min_version: 2024.10.0
  input:
    automation_trigger:
      name: Trigger
      selector:
        trigger:
    automation_actions:
      name: Actions
      selector:
        action:

triggers:
  - triggers: !input automation_trigger
actions:
  - sequence: !input automation_actions
mode: single
'''

    @staticmethod
    def _office_work_blueprint(name):
        return f'''blueprint:
  name: "{name.replace('"', '')}"
  description: >-
    Jarvis-generated office short-press routine with morning briefing,
    afternoon sign-off, and an outside-hours target toggle.
  domain: automation
  author: Project Jarvis
  homeassistant:
    min_version: 2024.10.0
  input:
    remote_trigger:
      name: Lumi remote short-press trigger
      selector:
        trigger:
    office_targets:
      name: Office lights and switches
      selector:
        target:
    weather_entity:
      name: Weather entity
      selector:
        entity:
          filter:
            - domain: weather
    work_calendar:
      name: Reach Work calendar
      selector:
        entity:
          filter:
            - domain: calendar
    tts_entity:
      name: Jarvis TTS provider
      selector:
        entity:
          filter:
            - domain: tts
    output_speaker:
      name: Lofstue Group Speaker
      selector:
        entity:
          filter:
            - domain: media_player

triggers:
  - triggers: !input remote_trigger

variables:
  weather_entity: !input weather_entity
  work_calendar: !input work_calendar
  tts_entity: !input tts_entity
  output_speaker: !input output_speaker

actions:
  - choose:
      - conditions:
          - condition: time
            after: "06:00:00"
            before: "10:00:00"
        sequence:
          - action: homeassistant.turn_on
            continue_on_error: true
            target: !input office_targets
          - action: weather.get_forecasts
            target:
              entity_id: !input weather_entity
            data:
              type: daily
            response_variable: daily_weather
          - action: calendar.get_events
            target:
              entity_id: !input work_calendar
            data:
              start_date_time: "{{{{ today_at('00:00') }}}}"
              end_date_time: "{{{{ today_at('00:00') + timedelta(days=1) }}}}"
            response_variable: today_agenda
          - variables:
              forecast: "{{{{ daily_weather.get(weather_entity, {{}}).get('forecast', []) }}}}"
              appointments: "{{{{ today_agenda.get(work_calendar, {{}}).get('events', []) }}}}"
              briefing: >-
                Good morning, Benny. It is {{{{ now().strftime('%H:%M') }}}}.
                {{{{ ('Today will be ' ~ forecast[0].condition | replace('_', ' ') ~
                ', with a high of ' ~ forecast[0].temperature ~ ' degrees.') if forecast else
                'The weather forecast is unavailable.' }}}}
                You have {{{{ appointments | count }}}} appointment{{{{ '' if appointments | count == 1 else 's' }}}} today.
                {{{{ ('The first is ' ~ appointments[0].summary ~ ' at ' ~
                as_datetime(appointments[0].start).astimezone().strftime('%H:%M') ~ '.') if appointments else '' }}}}
          - action: tts.speak
            target:
              entity_id: !input tts_entity
            data:
              media_player_entity_id: !input output_speaker
              message: "{{{{ briefing }}}}"
              cache: true
              options:
                preferred_format: mp3
                preferred_sample_rate: 44100
                preferred_sample_channels: 2
          - delay: "00:00:01"
          - action: tts.speak
            target:
              entity_id: !input tts_entity
            data:
              media_player_entity_id: !input output_speaker
              message: "{{{{ briefing }}}}"
              cache: true
              options:
                preferred_format: mp3
                preferred_sample_rate: 44100
                preferred_sample_channels: 2
      - conditions:
          - condition: time
            after: "15:00:00"
            before: "18:00:00"
        sequence:
          - action: homeassistant.turn_off
            continue_on_error: true
            target: !input office_targets
          - variables:
              days_ahead: "{{{{ 3 if now().weekday() == 4 else 1 }}}}"
              next_day: "{{{{ today_at('00:00') + timedelta(days=days_ahead) }}}}"
          - action: calendar.get_events
            target:
              entity_id: !input work_calendar
            data:
              start_date_time: "{{{{ next_day }}}}"
              end_date_time: "{{{{ next_day + timedelta(days=1) }}}}"
            response_variable: next_agenda
          - variables:
              next_appointments: "{{{{ next_agenda.get(work_calendar, {{}}).get('events', []) }}}}"
              signoff: >-
                You had a productive day at work, Benny.
                {{{{ ('Your first appointment on the next working day is ' ~
                next_appointments[0].summary ~ ' at ' ~
                as_datetime(next_appointments[0].start).astimezone().strftime('%H:%M') ~ '.')
                if next_appointments else 'There are no appointments on the next working day.' }}}}
          - action: tts.speak
            target:
              entity_id: !input tts_entity
            data:
              media_player_entity_id: !input output_speaker
              message: "{{{{ signoff }}}}"
              cache: true
              options:
                preferred_format: mp3
                preferred_sample_rate: 44100
                preferred_sample_channels: 2
          - delay: "00:00:01"
          - action: tts.speak
            target:
              entity_id: !input tts_entity
            data:
              media_player_entity_id: !input output_speaker
              message: "{{{{ signoff }}}}"
              cache: true
              options:
                preferred_format: mp3
                preferred_sample_rate: 44100
                preferred_sample_channels: 2
    default:
      - action: homeassistant.toggle
        continue_on_error: true
        target: !input office_targets
mode: single
'''
