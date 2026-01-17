# Security Policy

## Reporting a vulnerability
If you discover a security issue, please open a **private** report (if your platform supports it) or create an issue with minimal details and request a secure contact.

## Scope
This project is a local Streamlit app. Main risks are:
- Malicious file uploads (images)
- Unsafely loading untrusted YAML

We use `yaml.safe_load` to reduce YAML risks, and we treat uploaded images as untrusted.
