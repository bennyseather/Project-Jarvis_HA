"""Read-only shared dashboard projection. Never serialize the raw profile/history."""
from copy import deepcopy
from datetime import datetime, timezone

def overview(profile):
    if profile is None:
        raise ValueError('Household profile unavailable')
    with profile._edits.lock:
        # Re-read the authoritative, atomically-written document, not a second store.
        current = type(profile).load(profile._source_path) if hasattr(profile, '_source_path') else profile
        shared = current.context()
        directory = shared.get('directory', {})
        details = shared.get('approved_personal_details', {})
        names = list(dict.fromkeys(directory.get('names', []) + list(details)))
        revisions = []
        for record in current._data.get('household_edit_audit', [])[-20:]:
            try:
                stamp = datetime.fromisoformat(record['at']).isoformat()
                revision = int(record['revision'])
            except (KeyError, TypeError, ValueError):
                continue
            revisions.append({'revision':revision, 'at':stamp,
                              'method':'Confirmed conversation update',
                              'actor':'Shared HA account; individual not identified'})
        return {
            'schema_version':1, 'revision':current._data['revision'],
            'generated_at':datetime.now(timezone.utc).isoformat(),
            'timezone':'Europe/Oslo', 'read_only':True,
            'assistant':{'name':current._data['assistant']['name']},
            'profiles':[{'name':name, 'details':deepcopy(details.get(name, {}))} for name in names],
            'relationships':deepcopy(directory.get('relationships', [])),
            'rooms':deepcopy(directory.get('rooms', [])),
            'routines':deepcopy(shared.get('usual_household_routines', {})),
            'exceptions':deepcopy(shared.get('confirmed_routine_overrides', [])),
            'notes':deepcopy(shared.get('shared_household_notes', [])),
            'changes':list(reversed(revisions)),
            'limitations':[
                'Only confirmed information approved for shared household access is shown.',
                'Missing details may be unrecorded or not shared; do not infer them.',
                'Schedules are routines, not proof of attendance or current location.',
                'Dated school exceptions expire at the following midnight in Europe/Oslo; recurring overrides do not expire automatically.',
                'Change history contains confirmation metadata only, not private or withdrawn snapshots.',
            ],
        }
