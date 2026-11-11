"""OFFLINE TEST FIXTURE ONLY. Not a production P4 classifier or policy.
Exact synthetic bytes and findings are deliberately frozen to test plumbing.
"""
EXPECTED_SOURCE='# Synthetic note\r\nCafé 😀\nno-final-newline'
EXPECTED_DIFF='diff --git a/docs/猫.md b/docs/猫.md\r\n+Synthetic note\n'

def classify_fixture(context):
    if (context['sources']!={'docs/猫.md':EXPECTED_SOURCE}
            or context['diff']!=EXPECTED_DIFF
            or context['paths']!=[{'filename':'docs/猫.md','status':'modified'}]
            or context['finding_ids'] not in ([],['review:4'])):
        raise ValueError('offline_fixture_scope_only')
    return {'scope':{'classification':'P4_python_ast_equivalent','ast_equivalent_only':True,
        'coverage_complete':True,'reasons':['Exact synthetic offline case; never a production classification']},
        'findings':[{'id':identifier,'head_sha':context['sha'],'disposition':'verified_fixed',
            'test_id':'synthetic-source','source_refs':['docs/猫.md:1']} for identifier in context['finding_ids']]}

def check_source(context,assertions):
    assertions.require(context['sources']=={'docs/猫.md':EXPECTED_SOURCE},'exact frozen synthetic source bytes')
    assertions.require(context['diff']==EXPECTED_DIFF,'exact frozen synthetic diff bytes')
    assertions.require(context['paths']==[{'filename':'docs/猫.md','status':'modified'}],'complete synthetic path set')

def check_fails(context,assertions):
    assertions.require(False,'intentional failing trusted check')

def check_no_assertions(context,assertions):
    return True
