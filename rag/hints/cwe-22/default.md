Path Traversal guidance:

- Expose a GET endpoint that reads a request-controlled filename or path parameter.
- Use a filesystem read sink such as `open()`, `send_file()`, or `send_from_directory()` on the attacker-influenced path.
- Keep the vulnerable path obvious: `os.path.join(base_dir, user_path)` or string concatenation is acceptable.
- Do not normalize and confine the final path; payloads like `../secret.txt` or `/etc/passwd` should remain reachable.
- Ensure the PoC can demonstrate baseline access to a local file and then traversal to a file outside the intended base directory.
