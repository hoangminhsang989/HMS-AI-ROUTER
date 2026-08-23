# HMS-AI-ROUTER

Private source repository for HMS-AI-ROUTER.

## Repository authority

- `main` is the authoritative development source after migration.
- Product branding is **HMS-AI-ROUTER**.
- `Cockpit Tools` wording is retained only where it identifies the external parity/baseline reference.
- Historical v25.74 evidence remains immutable and may still contain the former product name.
- Legacy compatibility identifiers/data namespaces are preserved where changing them could break existing credentials or configuration.

## Migration baseline

Source baseline: **v25.74**.

The repository contains the verified migration bootstrap, launcher, project overview, and frozen v25.74 evidence. The one-time runtime-source importer verifies the transfer archive SHA-256 before extracting it into `main`.

Expected one-time transfer archive:

`HMS_AI_ROUTER_RUNTIME_SOURCE.tar.xz`

SHA-256:

`28a3ca7bb0b66e1945db91f2368159b114a20c0b5a57d6ddc44b3f30972eb60d`

After a valid archive is uploaded to the repository root, GitHub Actions extracts the runtime/source files, removes the transfer archive, and commits the extracted files back to `main`.
