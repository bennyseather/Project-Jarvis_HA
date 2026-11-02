"""Reported symptom labels, never a model diagnosis or repair authority."""
import re

def symptom(text):
    for category,pattern in (
        ('reported_timing_problem',r'\b(?:wrong|incorrect|feil)\b.{0,35}\b(?:time|date|day|dato|tid)\b|\b(?:time|date|day|dato|tid)\b.{0,35}\b(?:wrong|incorrect|feil)\b'),
        ('reported_venue_problem',r'\b(?:wrong|incorrect|feil)\b.{0,35}\b(?:venue|location|place|sted)\b'),
        ('reported_wording_problem',r'\b(?:shorter|too long|shorten|kortere|for langt)\b'),
        ('reported_continuity_problem',r'\b(?:wrong person|lost (?:the )?context|wrong (?:appointment|topic)|feil person|glemte sammenhengen)\b'),
        ('reported_source_problem',r'\b(?:stale|out.of.date|old calendar|not refresh|utdatert|oppdatert)\b')
    ):
        if re.search(pattern,text,re.I):return category
    return 'unverified_report'

def inspection_problem(category):
    subjects={'reported_timing_problem':'time or date grounding','reported_venue_problem':'venue source attribution',
              'reported_wording_problem':'response length and presentation','reported_continuity_problem':'conversation reference continuity',
              'reported_source_problem':'source freshness and unavailable-source handling'}
    area=subjects.get(category,'answer evidence')
    return 'Inspect this supported component for a user-reported problem with '+area+'. The symptom is not a proven root cause. Reproduce with fictional data; compare fresh source evidence with the previous answer before proposing a justified small change. Preserve permissions, date boundaries and action confirmations.'
