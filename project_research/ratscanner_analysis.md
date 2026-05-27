# RatScanner Analysis — Lessons for Albion Online Overlay

> Date: 2026-04-16
> Source: https://github.com/RatScanner/RatScanner
> Game: Escape From Tarkov (uses BattlEye)

---

## What Is RatScanner

RatScanner is an open-source companion tool for Escape From Tarkov that lets players scan items in-game by clicking on them, then overlays price/quest data on top of the game. It has existed for **5+ years** with **1,000+ daily active users** and **zero confirmed bans caused by the tool**.

This is directly relevant to us because EFT uses **BattlEye** — the same anti-cheat as Albion Online.

---

## Key Architecture Takeaways

### 1. Purely External — No Game Interaction

```
RatScanner.exe ──→ OS-level hooks (WH_MOUSE_LL)
                   GDI screen capture (CopyFromScreen)
                   WebView2 overlay (transparent WPF window)
                   External APIs (GraphQL, REST)
```

**What it does NOT do:**
- No `ReadProcessMemory` / `WriteProcessMemory`
- No DLL injection into EFT
- No access to game memory or files (except reading config for resolution)
- No packet sniffing

**What it DOES do:**
- Low-level Windows hooks for mouse/keyboard (OS-level, not game-level)
- GDI screen capture of specific screen regions
- Tesseract OCR + template matching on screenshots
- Transparent overlay window rendered on top of game

### 2. Overlay Implementation

| Technique | Detail |
|---|---|
| **Framework** | WPF + Blazor WebView2 |
| **Window style** | `WindowStyle=None`, `Topmost=True`, `AllowsTransparency=True` |
| **Size** | Covers entire virtual screen (all monitors) |
| **Alt+Tab hiding** | `WS_EX_TOOLWINDOW` extended style |
| **Blur effect** | Undocumented `SetWindowCompositionAttribute` (Windows 10/11 acrylic) |
| **Input handling** | Separate interactable overlay for search functionality |

### 3. Detection Pipeline

```
User clicks item → Mouse hook fires → Screenshot captured
                    → Tesseract OCR reads item name
                    → Template matching identifies item icon
                    → RatStash fuzzy-matches name to item database
                    → TarkovDev API fetches price/quest data
                    → Overlay renders tooltip at screen position
```

Screenshot region is small and targeted:
- **Name scan**: ~50x650px (just the tooltip text region)
- **Icon scan**: ~896x896px (inventory area)

### 4. Hotkey System

Uses `SetWindowsHookEx` with `WH_KEYBOARD_LL` (13) and `WH_MOUSE_LL` (14). These are **documented Windows APIs** for system-wide input monitoring. Many legitimate apps use them (autohotkey, screen recorders, accessibility tools).

Key states read via `GetAsyncKeyState` (also a documented Win32 API).

---

## What This Proves About BattlEye

### BattlEye Tolerates:
1. **Low-level Windows hooks** (`SetWindowsHookEx`) — RatScanner uses these extensively
2. **Screen capture** (GDI CopyFromScreen) — used on every item scan
3. **Transparent overlay windows** — permanent full-screen transparent WPF window
4. **OCR on game screenshots** — Tesseract reading item names from game UI
5. **Image processing on game content** — template matching against icon database

### What RatScanner Confirms for Our Project:
- Running alongside a BattlEye game with an external tool is safe if it:
  - Does not access the game process memory
  - Does not inject into the game
  - Uses standard OS APIs (hooks, screen capture)
  - Provides informational overlay only (no input simulation)

---

## New Product Ideas / Enhancements

### Idea 1: "AlbionScan" — Point-and-Lookup Items in Game

**Inspired by:** RatScanner's item scanning

**Concept:** Click on any item in your inventory/stash/trade window, and instantly see:
- Current market price in all cities (via AO Data API)
- Crafting cost breakdown
- Black market buy price
- Profit potential if sold in other cities

**How it would work:**
| Step | Implementation |
|---|---|
| Click detection | `WH_MOUSE_LL` hook (same as RatScanner) |
| Screenshot | `Graphics.CopyFromScreen` of tooltip/inspection area |
| Item identification | **Option A:** OCR on item name (Tesseract) |
| | **Option B:** Icon template matching (item icons available at `render.albiononline.com`) |
| | **Option C:** Color/fingerprint matching (unique item icons) |
| Price lookup | AO Data REST API or cached NATS data |
| Overlay display | Transparent WPF/HTML window (WebView2) |

**Complexity:** Medium
**Ban risk:** Same as RatScanner — 3-4/10 (external only, no game injection)
**Value proposition:** Extremely high — players can instantly identify profitable loot during raids/dungeons

### Idea 2: "AlbionMinimapOverlay" — Market Data on World Map

**Inspired by:** RatScanner's overlay positioning and interactive search

**Concept:** When the player opens the Albion travel/map screen, overlay current market prices directly onto the map UI.

**Implementation approaches:**
| Approach | Risk | Feasibility |
|---|---|---|
| **Second app, side-by-side** | 0/10 | ✅ Easy — just match the map UI visually |
| **Transparent overlay auto-positioning** | 3/10 | ⚠️ Medium — need to detect when map is open, position city markers |
| **Screen capture + map recognition** | 4/10 | ⚠️ Medium — need to identify which map/screen player is on |

**Feature ideas:**
- Color-coded city markers (green = good sell, red = bad sell)
- Route profit calculator drawn on map
- Quick city comparison: draw 2 cities, show best route

### Idea 3: "AlbionTradeHUD" — Persistent Price Ticker Overlay

**Inspired by:** RatScanner's minimal UI mode and persistent overlay

**Concept:** A small, always-on-top ticker showing live prices for items you care about. Think stock ticker, but for Albion items.

**Features:**
- Pin items you care about (e.g., "T6 Cloth", "T7 Hide")
- Mini ticker shows current buy/sell prices in selected city
- Alerts flash when price crosses threshold
- Minimal, compact design — takes up corner of screen only

**Ban risk:** 2/10 (purely informational, no screen capture needed, just overlay)

### Idea 4: "AlbionInsight" — Context-Aware Companion

**Inspired by:** RatScanner's TarkovTracker integration (quest/hideout data overlay)

**Concept:** Automatically detect what the player is doing in-game and show relevant data:

| Detected State | Show |
|---|---|
| Player at marketplace | Best buy/sell opportunities, price trends |
| Player at crafting station | Most profitable crafts right now |
| Player in inventory | Profit value of each item |
| Player on world map | Best trade routes from current city |

**Detection method:** Screen capture + ML/classification of current game state
**Value:** No need to switch apps — relevant data appears contextually

### Idea 5: RatScanner Architecture as Blueprint

**The entire RatScanner architecture is directly transferable:**

| RatScanner Component | Albion Equivalent |
|---|---|
| TarkovDev GraphQL API | AO Data REST API + NATS stream |
| Tesseract OCR on item names | OCR on Albion item names (simpler UI, should be easier) |
| Icon template matching | Icon library from `render.albiononline.com` |
| RatStash item database | Albion item database (exists in `repos/albion-profit`) |
| Blazor WebView2 UI | Same — use Blazor/WPF/HTML overlay |
| GDI screen capture | Same — `Graphics.CopyFromScreen` |
| Hotkey system (`WH_MOUSE_LL`) | Same |

---

## Risk Assessment Update

Based on RatScanner's 5-year, 1,000+ users, 0 bans track record:

**Our previous assessment: 4/10**
**Updated assessment: 3/10**

Reasoning: RatScanner is a real-world data point proving that BattlEye does not ban for:
- External screen capture
- Low-level input hooks
- Transparent overlay windows
- OCR on game content
- Template matching on game UI

The primary remaining risk factors are:
1. **Albion/SIG's specific enforcement policy** (different from Battlestate Games)
2. **ToS interpretation** — "modify gaming experience" is ambiguous
3. **False positive risk** — not targeted, but pattern-matching could theoretically trigger

---

## Recommended Technology Stack (Based on RatScanner)

| Component | Recommendation | Rationale |
|---|---|---|
| **UI Framework** | Blazor + WebView2 (or pure HTML/JS) | RatScanner proves this works well |
| **Overlay** | Transparent borderless window | Proven pattern, hides from Alt+Tab |
| **Screen Capture** | GDI `CopyFromScreen` or `Graphics.CopyFromScreen` | Simple, works, no DirectX needed |
| **OCR** | Tesseract via `tesseract-dotnet` or Python `pytesseract` | RatScanner uses it successfully |
| **Icon Matching** | OpenCV template matching | RatScanner uses template matching via RatEye |
| **Hotkeys** | Windows hooks via `user32.dll` | Standard API, no injection needed |
| **Config** | INI file or JSON | Simple, no registry needed |

### Python Alternative (Our Current Stack)

Since we're using Python/uv:

| Component | Python Equivalent |
|---|---|
| Overlay | `PyQt5/PySide6` transparent window, or `customtkinter` |
| WebView2 | `pywebview` (hosts web content in native window) |
| Screen Capture | `PIL.ImageGrab` or `mss` (faster than GDI) |
| OCR | `pytesseract` |
| Icon Matching | `opencv-python` (`cv2.matchTemplate`) |
| Hotkeys | `keyboard` library or `pynput` or direct `user32.dll` via `ctypes` |

---

## Actionable Next Steps

### Immediate (Low Effort)
1. **Build a simple HTML/JS overlay** — no screen capture, just displays market data from our existing NATS/REST pipeline
2. **Make it a transparent borderless window** — use `pywebview` or a browser in borderless mode
3. **Position it beside the game** — 0/10 ban risk, proves the concept

### Short-term (Medium Effort)
4. **Add item icon scanning** — capture screen on hotkey, match against Albion icon library
5. **Integrate AO Data API** — fetch prices for identified items
6. **Display in overlay** — show price, crafting profit, city comparison

### Long-term (High Effort)
7. **Context detection** — classify game state to show relevant data
8. **Trade route overlay on minimap** — detect map screen, overlay route data
9. **Persistent HUD mode** — stock ticker for tracked items
