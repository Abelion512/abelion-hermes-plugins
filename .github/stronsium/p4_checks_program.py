"""Frozen trusted checks for the comment-triggered producer. Literals and plain functions only.
Positive evidence comes from p4_semantic (trusted application code); these checks bind its inputs."""
def classify_unused(context):
    raise ValueError('semantic_lane_required')

def check_diff_covers_exactly_the_changed_files(context, assertions):
    paths = sorted([f['filename'] for f in context['paths']])
    headers = sorted([l[len('diff --git a/'):].split(' b/')[0] for l in context['diff'].split('\n') if l.startswith('diff --git ')])
    assertions.require(paths == headers, 'diff headers equal the changed file set')
    assertions.require(sorted(context['sources']) == paths, 'sources cover exactly the changed files')
    assertions.require(len(context['finding_ids']) == 0, 'no open review findings')
