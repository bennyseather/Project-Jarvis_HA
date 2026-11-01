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
      'tests':r'(?:(?:did|have) the tests (?:pass|passed)|what are the test results|show (?:me )?(?:the )?test results)'}
    return next((kind for kind,pattern in patterns.items() if re.fullmatch(pattern,value)),None)

def resumed(text):
    match=re.fullmatch(r'(?:back to|return to|about) (?:the )?(?:development workspace|development|inspection)\s*[:,]\s*(.+)',text.strip(),re.I)
    return match[1] if match else None

def state_words(state):
    return {'selecting':'choosing the relevant helper','inspecting':'reading the source','drafting':'checking the source and preparing a response','regression':'drafting a regression test','submitting':'sending the isolated test job','testing':'running isolated tests','inspection_complete':'inspection complete','review_required':'candidate ready for independent review','needs_revision':'candidate needs revision','no_candidate':'no justified change found','needs_review':'needs a manual check','source_changed':'source changed; needs a fresh snapshot','interrupted':'interrupted before completion','cancelled':'cancelled','baseline_failed':'existing tests did not pass','timeout':'test time limit reached','output_limit':'test output limit reached','runner_error':'runner could not complete'}.get(state,'status needs checking')

def result_lines(row):
    result=row.get('result') or {}
    if not result:
        return ['This was an inspection; no tests were run.'] if row.get('mode')=='inspect' and row.get('state')=='inspection_complete' else ['No completed test results are available yet.']
    lines=[phase_line(name,phase) for name,phase in result.get('phases',{}).items()]
    if row.get('state')=='review_required':lines.append('The candidate still needs independent review before release.')
    else:lines.append('The full candidate check has not passed; independent review is needed.')
    return lines

def case_title(row):
    return {'preparation':'preparation summaries','memory':'memory lookup','conversation':'conversation references','workspace':'development test wording'}.get(row.get('scope'),'development case')
