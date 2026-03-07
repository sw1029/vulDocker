When the vulnerability family is weakly specified:

- Keep the service minimal: one vulnerable endpoint, one health endpoint, one clear PoC path.
- Make the vulnerable data flow explicit in code. Prefer obvious request input -> sink code over subtle framework magic.
- Align the implementation with three semantic buckets:
  - input_vector: where attacker-controlled input enters
  - sink: the dangerous API or resource access
  - exploit_precondition: what unsafe composition or missing validation enables exploitation
- Print the exact success marker required by the contract on PoC success.
- Respect executor constraints: read-only root filesystem, only `/tmp` writable at runtime, no reliance on runtime OS binaries unless explicitly installed.
