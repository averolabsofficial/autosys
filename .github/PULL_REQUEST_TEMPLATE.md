## Summary
<!-- What does this PR do, and why? One or two sentences. -->

## Changes
<!-- Bullet list of concrete changes. -->

-

## Testing
<!-- How did you verify? Paste key output. Include TTY + `-y` + piped runs for prompt changes. -->

```bash
python -m py_compile autosys.py
python -m pytest -q
```

- [ ] `py_compile` passes
- [ ] `autosys --help` renders
- [ ] Tests pass / added for the change
- [ ] README.md + MANUAL.md updated if the command surface changed
- [ ] CHANGELOG.md entry added under `[Unreleased]`

## Related
<!-- Fixes #issue -->
