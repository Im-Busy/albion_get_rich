# Overlay Risk Assessment — BattlEye & Albion Online

> Date: 2026-04-16
> Subject: Risk of account ban when running a companion app with screen overlay

---

## Risk Rating: 4/10 (Low-Moderate)

### Summary
A **read-only, external overlay** (separate window/process) that displays market/trade data alongside the game carries **low-moderate** ban risk. The primary concern is BattlEye's desktop screenshot capability, not the overlay itself.

---

## BattlEye Capabilities (as of 2026)

| Capability | Relevant to Overlays? | Notes |
|---|---|---|
| Kernel-level driver (BEDaisy.sys) | Indirect | Ring-0 access to entire system |
| Desktop screenshots | **YES** | Can screenshot desktop to detect cheats/overlays |
| Process enumeration | Partial | Scans running processes for known signatures |
| Memory scanning | NO | Only if injecting into game process |
| Input pattern analysis | NO | Only if simulating input |
| Behavioral analysis | Indirect | Gameplay anomalies, not overlay detection |

---

## Risk Factors

### What INCREASES Risk 🔴
| Factor | Additional Risk |
|---|---|
| Injecting overlay into game process | +4 (high) |
| Using screen capture/OCR to read game state | +2 |
| Simulating mouse/keyboard input | +5 (very high) |
| Reading game memory | +4 (high) |
| Using known cheat libraries/frameworks | +3 |
| Running alongside packet sniffers | +3 |

### What DECREASES Risk 🟢
| Factor | Effect |
|---|---|
| Separate window/process (external) | Minimal risk |
| Read-only (no game interaction) | Minimal risk |
| No hooks into game process | Minimal risk |
| Uses approved APIs only (AO Data, NATS) | Safe |
| Resembles legitimate apps (Discord, browser overlays) | Lower probability of targeting |

---

## Comparison to Legitimate Software

| Software | Overlay Type | Ban Risk | Why |
|---|---|---|---|
| Discord | In-game overlay (injected) | 0/10 | Whitelisted |
| OBS | Screen capture | 0/10 | Whitelisted, common |
| MSI Afterburner | Overlay (injected) | 0/10 | Whitelisted |
| Browser (dual monitor) | External window | 0/10 | Not detectable as overlay |
| **Our overlay** | External window | **4/10** | Detectable, but not targeted |
| **Our overlay** | Injected overlay | **7/10** | Matches cheat behavior |

---

## Recommended Approaches (Lowest → Highest Risk)

### 1. Second Monitor / Browser (0/10) ✅ SAFEST
Run the companion app on a second monitor or beside the game window.
- **Zero BattlEye interaction**
- **Zero detection risk**
- Requires: second monitor or windowed mode

### 2. Borderless Window Overlay (3/10)
Transparent borderless window positioned over the game.
- Detectable via screenshot
- But looks like any other window overlay
- No game process interaction

### 3. Game Injection Overlay (7/10) ⚠️ DANGEROUS
Inject rendering code into the game process.
- **Matches cheat behavior exactly**
- High probability of detection
- **DO NOT DO THIS**

---

## Albion Online Terms of Service

The ToS prohibits:
> "Modify the gaming experience by using software or mechanisms that may affect the function and the game play"

**Key question:** Does a read-only overlay "modify the gaming experience"?

**Argument for safe:** Overlay doesn't modify game function or gameplay — it's an external information display, similar to having a spreadsheet open.

**Argument for risk:** If the overlay provides real-time actionable data (e.g., "buy here, sell there"), it could be argued to "modify the gaming experience" — though this is a gray area.

---

## Community Context

- Albion Online players commonly use **browser-based tools** alongside the game — no widespread ban reports
- **Discord overlay** is heavily used without issues
- **BattlEye bans** in Albion are primarily reported for:
  - Botting/automation
  - Packet manipulation
  - Third-party clients
  - Macros for PvP
- **No confirmed reports** of bans purely for informational overlays (as of 2026-04)

---

## Final Recommendation

**Build overlay as a separate window/process. DO NOT inject into game.**

If maximum safety is desired, use a second monitor or side-by-side windowed mode approach (0/10 risk).

For in-game overlay with minimal risk:
- Use transparent borderless window
- No hooks into game process
- No screen capture of game
- Pure external data (API/NATS only)
- Position beside game, not fully obscuring

**Acceptable risk for most users: 3-4/10**
**For accounts with significant investment: 1-2/10 (use dual monitor instead)**
