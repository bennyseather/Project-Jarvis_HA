"""Read-only display coalescing of explicitly equivalent, identical occurrences.

Keeps every selected source ID and whole instruction. Same sport alone is not a
link. Different owners, sources, starts/ends, usual facts or conflicting current
venues stay separate. Does not merge, remove or edit real calendar records.
"""
from copy import deepcopy
import json


def prepared(obj,events,notes):
    by_id={e['id']:e for e in events};display=[];items=[];lookup={};remap={}
    for item in obj['events']:
        event=by_id[item['id']];key=None
        relation=event.get('activity_equivalence');profile=event.get('activity_profile')
        if relation and profile and event.get('start') and event.get('end'):
            usual={k:profile[k] for k in ('activity','equipment','preparation','usual_venue','duration_minutes')}
            key=(tuple(relation),tuple(event['owners']),event['source'],event['date'],event['start'],event['end'],
                 event['all_day'],json.dumps(usual,sort_keys=True,ensure_ascii=False))
        candidates=lookup.get(key,[]) if key else []
        found=next((i for i in candidates if not (display[i].get('location') and event.get('location')) or display[i]['location']==event['location']),None)
        if found is None:
            found=len(display);display.append(deepcopy(event));items.append(deepcopy(item))
            display[-1]['presented_source_ids']=[event['id']]
            if key:lookup.setdefault(key,[]).append(found)
        else:
            current=display[found];current['presented_source_ids'].append(event['id'])
            if not current.get('location'):current['location']=event.get('location','')
            items[found]['excerpts']=list(dict.fromkeys(items[found]['excerpts']+item['excerpts']))
        remap[event['id']]=display[found]['id']
    selected_notes=[];selected_ids=[];seen=set()
    for note in notes:
        if note['id'] not in obj['notes']:continue
        row=deepcopy(note);row['events']=list(dict.fromkeys(remap[e] for e in note['events'] if e in remap))
        identity=(tuple(row['events']),row['text'],row.get('origin'))
        if not row['events'] or identity in seen:continue
        seen.add(identity);selected_notes.append(row);selected_ids.append(row['id'])
    return {**obj,'events':items,'notes':selected_ids},display,selected_notes
