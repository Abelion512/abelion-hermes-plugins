# Review-before-merge — repeating checklist template

Run this before calling a plugin change complete. It is a checklist, not a promise; fill in the relevant items for the change you actually made.

## Scope

- [ ] I know which plugin(s) this change touches
- [ ] I know whether it is code, docs, skills, tests, shared infra, or more than one

## Plugin code

- [ ] The change does what it claims in the plugin code
- [ ] Host/API guards are still correct for older and newer hosts
- [ ] No new hidden behavior that the docs do not mention

## Docs

- [ ] README still accurate
- [ ] USAGE updated if behavior/hooks/skills/config changed
- [ ] VALIDATION still matches the current paths
- [ ] Any status table / "UNRUN" / "Not covered" item is still honest

## Skills

- [ ] Skill frontmatter is valid
- [ ] Skill is registered in `__init__.py`
- [ ] Skill text matches the current plugin behavior

## Tests

- [ ] Unit layer updated if relevant
- [ ] E2E layer updated if relevant
- [ ] No real credentials/tokens/cookies in test data
- [ ] Any skip reason is named, not silent

## Shared infra

- [ ] `hermes.json` synced if plugin set changed
- [ ] `update-plugins.sh` synced if plugin set changed
- [ ] Root README table synced if plugin set changed
- [ ] Labeler updated if plugin set or priority taxonomy changed
- [ ] CI still makes sense for the new shape

## Security and hygiene

- [ ] No new credentials, keys, tokens, cookies, or session IDs in the diff
- [ ] No new secret-shaped test data that could be confused with a real credential
- [ ] No new machine-local hardcoded paths that should be documentation, not literals
- [ ] No weakened secret scan or CI gate

## Proof, not vibes

- [ ] Any "works" claim is backed by a test or an explicit doc note saying it is not yet proven
- [ ] Any "proven by E2E" claim is actually backed by an E2E test

If any box is unclear, say so in the change instead of pretending it is done.
