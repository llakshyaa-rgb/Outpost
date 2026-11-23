# OUTPOST offline security review playbooks

These compact, offline-first checklists are inspired by the workflow categories in Claude-BugHunter. They are **review guides**, not exploit scripts. Use them only on systems, code and accounts you own or are explicitly authorised to assess. Do not scan third-party targets.

## 1. Source-code review
- [ ] Identify the application entry points, trust boundaries and sensitive data.
- [ ] Trace authentication and authorization checks to every sensitive operation.
- [ ] Check whether object identifiers are authorized server-side for the current user.
- [ ] Review input validation at the point data enters the system.
- [ ] Check output encoding for HTML, JavaScript, URL, SQL and shell contexts.
- [ ] Search for hard-coded credentials, private keys, tokens and debug secrets.
- [ ] Inspect dependency manifests and lockfiles for unpinned or abandoned packages.
- [ ] Review error handling for stack traces, secrets and internal paths.
- [ ] Record file path, line range, impact, evidence and remediation for each finding.

## 2. Authentication and session review
- [ ] Confirm password storage uses a modern adaptive password hash, not plaintext or fast hashes.
- [ ] Check login, reset and recovery flows for rate limits and generic failure messages.
- [ ] Verify MFA enrollment, recovery and factor replacement require appropriate re-authentication.
- [ ] Confirm session identifiers rotate after login and privilege changes.
- [ ] Check logout and password reset invalidate relevant sessions.
- [ ] Review cookie Secure, HttpOnly and SameSite attributes where cookies are used.
- [ ] Verify authorization is checked on every sensitive server-side action.

## 3. Web application input and output
- [ ] Inventory parameters, headers, uploads, JSON fields and imported files.
- [ ] Confirm server-side validation uses allowlists and sensible length/type limits.
- [ ] Review SQL queries for parameter binding.
- [ ] Check template rendering and DOM updates for context-appropriate output encoding.
- [ ] Review file upload type checks, size limits, generated names and storage location.
- [ ] Verify archive extraction rejects traversal paths, symlinks and oversized expansion.
- [ ] Check redirects and URL fetch features against open-redirect and SSRF risks.
- [ ] Review CSRF protections for state-changing browser requests.

## 4. API authorization and data exposure
- [ ] Inventory routes and methods, including hidden/admin endpoints.
- [ ] Map each route to required identity, role and object-level permission.
- [ ] Test authorization using a local test account matrix only.
- [ ] Check mass assignment and unexpected JSON properties.
- [ ] Verify pagination and response sizes are bounded.
- [ ] Check errors and logs for secrets, personal data and internal implementation details.
- [ ] Confirm CORS and cache headers match the intended access model.

## 5. Secrets and configuration
- [ ] Search source and build artifacts for tokens, keys, passwords and connection strings.
- [ ] Check that secrets are not committed in sample environment files.
- [ ] Verify production debug mode is disabled.
- [ ] Check file permissions for configuration, backups and private keys.
- [ ] Review default credentials and first-run setup.
- [ ] Ensure logs redact credentials and authorization headers.
- [ ] Confirm backups are protected and restore procedures are documented.

## 6. Android application review
- [ ] Review AndroidManifest exported components and intent filters.
- [ ] Check cleartext traffic policy and network security configuration.
- [ ] Inspect app backup rules for sensitive local data.
- [ ] Review WebView JavaScript bridges and file access settings.
- [ ] Check local storage for tokens and personal data.
- [ ] Verify runtime permissions are minimal and requested only when needed.
- [ ] Review deep links and exported activities for authorization gaps.

## 7. Dependency and supply-chain review
- [ ] Record direct and transitive dependencies from lockfiles.
- [ ] Identify abandoned, duplicated or unexpectedly large dependencies.
- [ ] Check package names, registries and integrity hashes.
- [ ] Review install/build scripts before execution.
- [ ] Compare generated artifacts against expected release contents.
- [ ] Document upgrade, pinning and vulnerability-response plans.

## 8. Finding report template
For each finding record:
- Title and affected component
- Severity and rationale
- Preconditions and affected trust boundary
- Reproducible evidence from an authorised local test
- Impact and realistic attack scenario
- Recommended fix and verification step
- Date, reviewer and scope approval

## Safety boundary
OUTPOST does not run these checklists against remote targets. It does not execute imported scripts, exploit code, brute-force credentials, probe networks or contact reputation services. Keep all testing within an explicitly approved scope.
