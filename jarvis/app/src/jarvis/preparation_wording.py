"""Small source-preserving prose helpers; no inference, writes or extra AI call."""
import re


def join_words(values):
    values=list(values)
    if len(values)<2:return ''.join(values)
    return ', '.join(values[:-1])+(' and ' if len(values)==2 else ', and ')+values[-1]


def activity_name(value):
    # Surface form only; the stored meaning and activity evidence stay unchanged.
    return 'orchestra practice' if value.casefold()=='music orchestra practice' else value


def kit_item(value):
    if not re.fullmatch(r"[\w][\w '’-]*",value):return '“'+value+'”'
    articles={'instrument':'the instrument','water bottle':'a water bottle',
              'small towel':'a small towel','music folder':'the music folder'}
    return articles.get(value.casefold(),value)


def usual_preparation(activity,equipment,preparation,owner=None):
    label=activity_name(activity);subject=(owner+"'s " if owner else '')+label
    gear=join_words(kit_item(v) for v in equipment[:3])
    # Keep negations, conditions and multi-sentence instructions intact. Only
    # a whole, simple positive imperative can follow the grammatical "to".
    simple=bool(preparation and re.match(r'^(?:wear|bring|pack|check|take|put|have|collect|prepare|fill|charge|make|ensure)\b',preparation,re.I)
                and not re.search(r'[.!?;:]',preparation.rstrip('.')))
    if simple:
        clause=preparation.removesuffix('.')
        clause=clause[0].lower()+clause[1:]
        return 'For '+subject+', the usual routine is to '+clause+(', and bring '+gear if gear else '')+'.'
    pieces=[]
    if gear:pieces.append('For '+subject+', have '+gear+' ready as usual.')
    if preparation:pieces.append('The usual instruction for '+subject+' is: “'+preparation+'”')
    return ' '.join(pieces)
