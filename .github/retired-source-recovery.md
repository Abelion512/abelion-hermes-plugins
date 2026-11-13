# Retired source recovery

Retired Shield, tool-context, RSI source and earlier cross-plugin tests are no longer shipped in this checkout. They remain in Git at pinned revision `0fa17829691bcab8db7e7a6a29e88e6604860f46`:

```sh
git show 0fa17829691bcab8db7e7a6a29e88e6604860f46:rollback/pre-native-cleanup-source.tgz > /tmp/pre-native-cleanup-source.tgz
printf '%s\n' 'eae0c7ed9491575d7cff02ba65da48fea98f4880b09c0081c6be1ac9b1038236  /tmp/pre-native-cleanup-source.tgz' | sha256sum -c -
```

Fetch that revision first if your clone lacks it. Do not extract into a running profile. This is source recovery, not an installed-profile backup. Stop the disposable profile and restore pinned plugins, configuration and user data together; required privacy keeps its matching core and owner. Existing lesson files, metrics and installed copies are untouched.
