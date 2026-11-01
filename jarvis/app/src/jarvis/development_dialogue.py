"""Pure read presentation for supervised cases. No authority or execution."""
import re

def phase_line(name,phase):
    count=phase.get('tests_reported',0)
    status='passed' if phase.get('passed') else 'did not pass'
    if name=='original_regression' and phase.get('assertion_failure') is True and phase.get('passed') is False:status='failed as expected'
    noun='test' if count==1 else 'tests'
    return name.replace('_',' ')+': '+str(count)+' '+noun+' reported, '+status

def followup(text):
    value=' '.join(text.casefold().strip(' .?!').replace('’',"'").split())
    patterns={
      'status':r"(?:how(?: is|'s) (?:it|that|the inspection|the case) going|any progress|what(?: is|'s) the status|give me a progress update)",
      'findings':r'(?:(?:what did|what have) you (?:find|found)|what does (?:it|that) do|tell me what you found)',
      'patch':r'(?:show (?:me )?(?:the |your )?(?:patch|diff|proposed changes)|what changes did you propose)',
      'tests':r'(?:(?:did|have) the tests (?:pass|passed)|what are the test results|show (?:me )?(?:the )?test results)',
      'why':r'(?:why (?:this|that|the) change|why (?:do you|would you) recommend (?:this|that)(?: change)?)',
      'risks':r'(?:what could (?:it|this|that)(?: change)? affect|what are the risks|what could go wrong)',
      'next':r'(?:what would you improve next|what should (?:we|you) improve next|what(?: is|\x27s) the next development step)'}
    return next((kind for kind,pattern in patterns.items() if re.fullmatch(pattern,value)),None)

def resumed(text):
    match=re.fullmatch(r'(?:back to|return to|about) (?:the )?(?:development workspace|development|inspection)\s*[:,]\s*(.+)',text.strip(),re.I)
    return match[1] if match else None

def state_words(state):
    if state=='released':return 'independently reviewed and released'
    return {'selecting':'choosing the relevant helper','inspecting':'reading the source','drafting':'checking the source and preparing a response','regression':'drafting a regression test','submitting':'sending the isolated test job','testing':'running isolated tests','inspection_complete':'inspection complete','review_required':'candidate ready for independent review','needs_revision':'candidate needs revision','no_candidate':'no justified change found','needs_review':'needs a manual check','source_changed':'source changed; needs a fresh snapshot','interrupted':'interrupted before completion','cancelled':'cancelled','baseline_failed':'existing tests did not pass','timeout':'test time limit reached','output_limit':'test output limit reached','runner_error':'runner could not complete'}.get(state,'status needs checking')

def result_lines(row):
    result=row.get('result') or {}
    if not result:
        return ['This was an inspection; no tests were run.'] if row.get('mode')=='inspect' and row.get('state')=='inspection_complete' else ['No completed test results are available yet.']
    lines=[phase_line(name,phase) for name,phase in result.get('phases',{}).items()]
    if release_note(row):lines.append(release_note(row))
    elif row.get('state')=='review_required':lines.append('The candidate still needs independent review before release.')
    else:lines.append('The full candidate check has not passed; independent review is needed.')
    return lines

def case_title(row):
    return {'preparation':'preparation summaries','memory':'memory lookup','conversation':'conversation references','workspace':'development test wording'}.get(row.get('scope'),'development case')

def release_note(row):
    release=row.get('release')
    if row.get('state')!='released' or not isinstance(release,dict) or set(release)!={'version','commit','reviewed_by'}:return ''
    if release['reviewed_by']!='Codex' or not re.fullmatch(r'0\.45\.\d+',str(release['version'])) or not re.fullmatch(r'[0-9a-f]{40}',str(release['commit'])):return ''
    return 'Independently reviewed and released as Jarvis '+release['version']+'.'

def proposal_lines(row,kind):
    """Use persisted case evidence; never invent defects, coverage or approval."""
    citations=row.get('citations') or []
    target=', '.join(c['symbol'] for c in citations) or 'the selected code'
    patch=bool(row.get('diff'))
    released=release_note(row)
    if kind=='why':
        if not patch:return 'I have only inspected '+target+'. '+row.get('summary','')+' That is not evidence of a defect, and I have not produced a repair.'
        return 'The reported problem was: '+row['problem']+' '+('The released repair is: ' if released else 'My proposed change is: ')+row.get('summary','No explanation has been confirmed yet.')+' It targets '+target+'. '+(released or 'The proposal still needs independent review.')
    if kind=='risks':
        if not patch:return 'There is no candidate change to assess yet. The inspection of '+target+' has not changed production code or run tests.'
        phases=(row.get('result') or {}).get('phases',{})
        checked=phases.get('candidate_suite',{}).get('passed') is True
        return 'The change targets '+target+'. '+('Its recorded candidate tests passed, but they do not prove every behaviour is correct.' if checked else 'There is no passing full candidate check yet.')+(' Independent review has been recorded; real-world text checks can still reveal gaps.' if released else ' Existing behaviour outside those checks, unsupported answers and failure handling need independent review before release.')
    if not patch:return 'The next useful step is a concrete failing example for '+case_title(row)+', then a small candidate repair and a regression that reproduces it. This inspection alone has not established a defect.'
    if released:return 'Next, check this repair in real text conversations and investigate the next concrete failure from its source evidence. '+released+' Passing these tests does not establish a new defect to fix.'
    if row.get('state')=='review_required':return 'Next, independently review this candidate against the reported problem and test cases it may have missed. Passing generated tests alone is not enough to release it.'
    return 'First resolve the incomplete or failed checks for this candidate. '+ ' '.join(result_lines(row))+' I would finish that evidence before proposing another change.'
