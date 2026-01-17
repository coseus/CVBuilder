# Contributing

Thanks for your interest in contributing!

## Quick start
1. Fork the repo and create a feature branch.
2. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Guidelines
- Keep the **Modern** export single-column and ATS-friendly (avoid tables/columns).
- Prefer small, deterministic heuristics over complex NLP.
- New ATS profiles should live in `ats_profiles/*.yaml` and be user-editable.
- Keep UI changes behind a clear section or expander.

## Pull Requests
- Describe the motivation + user impact.
- Include screenshots for UI changes.
- Mention any new files and why they are needed.

## Code style
- Simple, readable Python.
- Avoid heavy dependencies unless necessary.
