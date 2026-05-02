# AGENTS.md - Backend Guide

## Security

- Never serialize exception objects, `str(exc)`, `repr(exc)`, traceback text, or raw upstream error details into DRF/API responses. GitHub Advanced Security CodeQL rule `py/stack-trace-exposure` flags this even when the exception type is custom or expected.
- For API error payloads, return fixed public messages plus stable `error_code` values. Log detailed exception information server-side only.
