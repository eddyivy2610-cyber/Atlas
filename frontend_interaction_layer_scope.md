# UMLdoc — Live Presentation/Interaction Layer: Scope Document

**Purpose:** define the minimal, defensible scope for the live web-facing layer that satisfies the course's "live presentation" requirement, without threatening remaining timeline before write-up submission.

**Guiding principle:** this layer is a thin wrapper around the existing, already-validated pipeline (extraction → verification → drift → bundling). It should demonstrate the pipeline running, not reimplement or extend it. Any feature that adds new *analytical* capability belongs in the core engine and Phase 7 write-up, not here.

---

## ✅ Include

### 1. Browse mode
- Landing page listing pre-generated bundles (TinyDB, Click) with summary KPIs (class count, precision/recall, drift status) pulled from existing `verification_metrics.json` / `document_ir.json`.
- Clicking a repo opens its existing `index.html` dossier (already built in Phase 6) — reused as-is, not rebuilt.
- **Why:** near-zero new work, immediately satisfies "a running application a user interacts with."

### 2. Live-run mode (the actual demo)
- A form to select from a **small, fixed allowlist** of pre-vetted repos (TinyDB at minimum — fast, fully validated, cheap on API calls).
- "Run" button triggers the existing pipeline server-side: static extraction → dynamic trace → LLM distillation → verification → drift (if applicable) → bundle.
- Simple progress feedback (polling or WebSocket): text-based stage updates ("Extracting classes… Tracing… Calling LLM… Verifying… Packaging…") — no need for elaborate progress bars.
- On completion, redirect to or embed the resulting dossier `index.html`.
- **Why:** this is the part that proves the pipeline works live, not just that pre-baked output looks good.

### 3. Pan/zoom on the SVG architecture diagram
- Lightweight (~40-line) inline JS handler for mouse-drag pan and scroll-wheel zoom on the native SVG diagram, especially valuable for dense diagrams (Click, 81 classes).
- **Why:** cheap, directly improves demo usability, no new dependencies, already scoped as a near-term improvement.

### 4. Basic run history / status
- A simple list of past runs in the current session (repo name, timestamp, pass/fail) — in-memory is fine, no persistence needed.
- **Why:** minor, gives the live layer a sense of being a real tool rather than a single-shot demo page, costs almost nothing.

---

## ❌ Do Not Include

### 1. Arbitrary repo input (e.g., "paste any GitHub URL")
- **Why not:** unpredictable size/cost (LLM token spend), unknown failure modes (recall the Click token-truncation bug), demo-reliability risk right before a defense. Constrain to pre-tested repos only.

### 2. User accounts, auth, multi-user session handling
- **Why not:** irrelevant to the thesis's actual contribution (verification/drift/generation), pure infrastructure overhead.

### 3. Persistent storage / database backend
- **Why not:** existing bundles and JSON artifacts on disk are sufficient. Adding a DB layer is scope creep with no analytical payoff.

### 4. Rebuilding the dossier UI from scratch in a JS framework (React/Vue/etc.)
- **Why not:** `html_report.py`'s output is already interactive, tested, and self-contained. Re-implementing it as a SPA duplicates work for no new capability and risks introducing new bugs in an already-validated component.

### 5. Real-time collaborative features, comments, annotations
- **Why not:** out of scope for the thesis entirely; not implied by "live presentation."

### 6. Editing diagrams or IR data through the UI
- **Why not:** UMLdoc's contribution is generation + verification + drift detection, not diagram authoring. Editable diagrams would contradict the "faithful to the code" premise the whole verifier is built around.

### 7. New diagram types or new verifier logic surfaced only in the frontend
- **Why not:** any new analytical capability belongs in the core engine (and its own evaluation pass), not bolted onto the presentation layer late in the project. If it's not validated the way class/sequence diagrams are, it shouldn't appear in a live demo implying equal rigor.

### 8. Deployment to a public host / cloud infrastructure
- **Why not:** unless explicitly required by the course, a local demo (`localhost`, run during defense) satisfies "live" without adding deployment, security, and hosting-cost concerns.

### 9. Streaming raw LLM token output to the UI
- **Why not:** interesting but purely cosmetic; adds complexity (SSE/WebSocket token streaming) for a feature that doesn't strengthen any thesis claim. Stage-level progress text is sufficient.

---



## Pre-Defense Checklist
- [ ] Confirm existing CLI logic is importable as functions (not locked in `argparse`/`__main__` blocks) — determines whether wrapping is trivial or needs refactoring.
- [ ] Test the live-run path end-to-end **at least 3 times** before defense — this is the path with external API calls (Gemini) that can fail or vary.
- [ ] Have a fallback: if live API call fails during the actual defense, be ready to show the pre-generated bundle instead without breaking demo flow.
- [ ] Add a short "Live Presentation Layer" section to the architecture chapter, explicitly distinguishing it from the core extraction/verification engine.
