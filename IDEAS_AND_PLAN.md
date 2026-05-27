# Albion Get Rich — Master Plan

> Last updated: 2026-04-18
> Status: ✅ MVP COMPLETE — Product Ready for Use

---

## 1. Money-Making Directions (Brainstormed)

### Direction 1: Smart City Flipping Scanner ✅ RECOMMENDED
**What:** A lightweight tool that queries the AO Data API + NATS stream to find the most profitable buy-low/sell-high routes between cities.

**Features to build:**
- Real-time price gap calculator between all city pairs
- Smart filters: travel distance, minimum volume thresholds, time-to-sell estimates
- Outlands focus: Outlands cities have lower supply → higher margins
- Batch calculation: Given X starting silver, calculate optimal set of items to buy+transport
- Price alerts when an item's gap exceeds threshold
- Profit-per-hour estimates (factoring in travel time)

**Why recommended:**
- Lowest ban risk (purely API/NATS-based, no game interaction)
- Fastest to build (logic exists in existing repos)
- Immediate actionable value
- NATS approach gives unlimited real-time data (no rate limits on push stream)

**Build time estimate:** 1-2 weeks for MVP

---

### Direction 2: Crafting Profit Optimizer
**What:** Real-time calculator that determines the most profitable item to craft RIGHT NOW, factoring in material costs, return rates, focus, and city bonuses.

**Features:**
- Scrape all crafting recipes
- For each craftable: `(sell price) - (sum of mat buy prices) - taxes`
- Account for Resource Return Rate (RRR)
- Factor in Focus usage and city specialization bonuses
- Output: "The most profitable thing to craft right now is T6 Assassin Shoes @ City A, profit = X silver/unit"

**Why viable:** Builds on albion-profit repo concept but makes it automated + real-time
**Constraint:** Requires high Destiny Board spec in crafting/refining to actually be profitable

---

### Direction 3: Outlands Trade Route Planner
**What:** Combine market data + map data to generate optimal trade loops through the Outlands.

**Features:**
- Build a graph of Outlands nodes using albiononline2d.com API
- Overlay current market prices on the map
- Generate optimal trade loops with profit estimates
- Show travel time estimates, danger zones, expected profit/hour
- Factor in Outlands-specific supply/demand dynamics

**Why viable:** Leverages the minimap overlay repo knowledge
**Build time:** 2-3 weeks (needs map graph construction + pathfinding)
**Blocker:** albiononline2d.com is behind Cloudflare protection — needs alternate data source or manual city mapping

---

### Direction 4: Black Market Flipper with Statistical Edge
**What:** Improves on the AlbionFlipper concept by adding historical analysis and statistical scoring to find consistent BM flips.

**Features:**
- Track historical price variance for items
- Moving averages to detect inflated/deflated BM buy orders
- Auto-calculate safe quantity based on market depth
- Filter out thin order book items (high risk of being filled before arrival)
- Score items by risk-adjusted profit

**Why viable:** BM flipping is one of the most consistent money-makers in Albion
**Build time:** 1-2 weeks

---

### Direction 5: Semi-Automated Trading Bot ⚠️ HIGH RISK
**What:** Full bot that automates travel, market interaction, buying/selling.

**Existing code:** AlbionTradeBot repo (nearly complete production bot with packet sniffing, OCR, market handlers, travel handlers)

**Risk assessment:** See BattlEye section below.

---

### Direction 6: AlbionTradeHUD — Persistent Market Overlay (RatScanner-Inspired)
**What:** A small, always-on-top ticker showing live prices for items you care about. Think stock ticker, but for Albion items.

**Inspired by:** RatScanner's transparent overlay pattern. Proven safe: 5+ years, 1,000+ users, 0 bans for Escape From Tarkov (also BattlEye).

**Features:**
- Pin items you care about (e.g., "T6 Cloth", "T7 Hide")
- Mini ticker shows current buy/sell prices in selected city
- Alerts flash when price crosses threshold
- Minimal, compact design — takes up corner of screen only
- Powered by NATS stream for real-time updates
- Transparent borderless window — same technique as RatScanner

**Implementation pattern:**
- Python backend subscribes to NATS stream
- `pywebview` or `PyQt5` transparent window renders ticker UI
- No game process hooks, no injection — purely external display

**Build time:** 1 week (after MVP of Direction #1 is done)
**Ban risk:** 2/10 (based on RatScanner evidence: screen capture + overlay + external hooks are tolerated)

---

### Direction 7: AlbionScan — Point-and-Lookup Items in Game (RatScanner-Inspired)
**What:** Hover over any item in your inventory/stash, press a hotkey, and instantly see its market value, crafting cost, and profit potential.

**Inspired by:** RatScanner's core functionality. Exact same pattern: click → screenshot → OCR/template matching → overlay price data.

**Features:**
- Hotkey triggers screenshot of item tooltip area
- OCR identifies the item name (Albion UI is simpler than EFT's — should be easier)
- Alternative: Icon template matching using icons from `render.albiononline.com`
- Instant price lookup from cached NATS data or REST API
- Overlay pops up showing: best buy/sell city, crafting cost, BM buy price

**How it maps to RatScanner:**
| RatScanner | AlbionScan |
|---|---|
| TarkovDev GraphQL API | AO Data REST API + NATS |
| Tesseract OCR on item names | Same (Albion text is simpler UI) |
| Icon template matching | Same (icons at `render.albiononline.com`) |
| RatStash item database | Albion item database (in repos/albion-profit) |
| WPF + Blazor WebView2 UI | pywebview / PyQt5 |
| GDI screen capture | `mss` or `PIL.ImageGrab` |
| `WH_MOUSE_LL` hotkeys | Same (via `ctypes` or `pynput`) |

**Build time:** 2 weeks (after MVP + overlay done)
**Ban risk:** 3/10 (same as RatScanner — external screen capture, OCR, hooks, overlay)

---

### Direction 8: AlbionInsight — Context-Aware Companion (RatScanner-Inspired)
**What:** Automatically detect what screen the player is on and show relevant data contextually.

**Features:**
| Detected Screen | Shows |
|---|---|
| Marketplace UI | Best buy/sell opportunities, price trends |
| Crafting station UI | Most profitable crafts right now |
| Inventory/stash | Profit value of each item |
| World map | Best trade routes from current city |

**Detection method:** Periodic screenshot + screen classification (can use simple OpenCV template matching on distinctive UI elements, or lightweight ML)
**Value:** No need to switch apps — relevant data appears when you need it
**Build time:** 3-4 weeks
**Ban risk:** 3/10 (periodic screenshots are same pattern as RatScanner)

---

## 2. Albion Online Destiny Board — Key Findings

### How It Works
- **Action-based progression** (level by doing, not skill points)
- You gain Fame (XP) by performing activities: crafting, gathering, killing mobs, etc.
- Each branch is independent — combat, gathering, refining, crafting can all be leveled separately
- Quick Learn system: toggle nodes, Learning Points (from Premium) auto-spend at 5x rate

### Refining Tree
| Specialization | Refines | Unlocks By |
|---|---|---|
| Fiber Weaver | Fiber → Cloth | Crafting Simple Cloth |
| Ore Smelter | Ore → Metal Bars | Crafting Copper Bars |
| Hide Tanner | Hides → Leather | Crafting Stiff Leather |
| Wood Planer | Wood → Planks | Crafting Birch Planks |
| Stone Cutter | Stone → Blocks | (similar pattern) |

Refining tiers give: Increased Resource Return Rate (RRR), reduced costs, ability to refine higher tiers.

### Crafting Tree
- Each item type has its own specialization branch
- Must unlock "Journeyman" generic node before specialized sub-branches
- Crafting levels unlock higher tiers:
  - Level 1 → T4, Level 10 → T5, Level 30 → T6, Level 70 → T7

### Resource Return Rate (RRR) — THE KEY METRIC
- Formula: `RRR = 1 - 1/(1 + Production_Bonus/100)` (diminishing returns)
- Base in Royal Cities (18% production bonus): ~15.2%
- With Focus + specialization: can reach ~53-54%

| Source | Bonus |
|---|---|
| Royal city baseline | 18% production = 15.2% RRR |
| City specialization (refining) | +40% production |
| City specialization (crafting) | +15% production |
| Using Focus | +30% production |
| Hideouts (Power Cores) | Up to 26% general + 30% specialization |

**Key insight:** Royal cities have highest refining bonuses but lower crafting bonuses. Outlands hideouts have higher crafting bonuses but lower refining. This creates a transport/trade loop.

### Focus Points
- Premium gives 10,000 Focus Points/day (cap: 30,000)
- Using Focus when crafting/refining significantly increases RRR (often tripling it)
- Focus also increases chance of rolling higher Quality items
- **Without Focus, refining/crafting are often breakeven or losing**

### Money-Making Accessibility
| Method | New Account | Established Account |
|---|---|---|
| Gathering T3-T4 | ✅ Yes | ✅ Yes |
| Expedition quests | ✅ Yes | ✅ Yes |
| Basic crafting | ⚠️ Low profit | ⚠️ Low profit |
| Focus Refining | ❌ Need spec | ✅ Very profitable |
| Focus Crafting | ❌ Need spec | ✅ Very profitable |
| Black Market selling | ❌ Need transport/spec | ✅ Major money maker |
| High-tier Gathering | ❌ Need survival skills | ✅ Very profitable |
| Market flipping | ✅ Yes! | ✅ Yes! |

---

## 3. Anti-Cheat Analysis — BattlEye / EAC

### What Albion Uses
- **PC: BattlEye** (integrated ~August 2023, replacing Easy Anti-Cheat)
- **Mobile:** Easy Anti-Cheat (EAC) — different from PC

### BattlEye Detection Methods
BattlEye is one of the most aggressive anti-cheats in gaming (used by PUBG, Fortnite, R6 Siege). It:

1. **Kernel-level driver (BEDaisy.sys)** — has ring-0 access, can scan entire system memory
2. **Process enumeration** — scans all running processes for known cheat signatures
3. **Memory anomaly detection** — scans game's virtual address space for executable memory outside known modules
4. **Input pattern analysis** — can detect non-human input timing (fixed intervals, perfect precision)
5. **Screenshot/screen capture** — can take screenshots of your desktop to detect overlays/cheats
6. **Behavioral analysis** — Some community claims of AnyBrain AI integration for gameplay behavior analysis

### Real-World Evidence: RatScanner (Escape From Tarkov, also uses BattlEye)

**RatScanner** (https://github.com/RatScanner/RatScanner) is a companion tool for Escape From Tarkov that:
- Takes screenshots of the game UI using GDI `CopyFromScreen`
- Uses Tesseract OCR to read item names from screenshots
- Uses OpenCV template matching to identify item icons
- Uses `SetWindowsHookEx` with `WH_MOUSE_LL` and `WH_KEYBOARD_LL` (low-level input hooks)
- Renders a transparent full-screen WPF overlay window on top of the game
- Displays real-time price/quest data over the game

**Track record:** 5+ years, 1,000+ daily active users, **zero confirmed bans caused by the tool.**

### What This Proves BattlEye Tolerates:
| Technique | Evidence | Risk |
|---|---|---|
| Screen capture of game UI | RatScanner screenshots every item scan | ✅ Safe |
| OCR on game screenshots | RatScanner uses Tesseract on game text | ✅ Safe |
| Template matching on UI | RatScanner uses OpenCV on game icons | ✅ Safe |
| Low-level input hooks (`WH_MOUSE_LL`) | RatScanner hooks keyboard/mouse globally | ✅ Safe |
| Transparent overlay windows | RatScanner has permanent transparent overlay | ✅ Safe |
| External data APIs | RatScanner queries external GraphQL API | ✅ Safe |
| **Injection into game process** | — | 🔴 DANGEROUS |
| **Reading game memory** | — | 🔴 DANGEROUS |
| **Input simulation/automation** | — | 🔴 DANGEROUS |

### What This Means For Our Project

| Approach | Ban Risk | Why |
|---|---|---|
| **Pure API/NATS calls** | 🟢 NONE | External HTTP requests and WebSocket connections. BattlEye monitors the game process, not your browser/terminal. |
| **Running alongside game (python.exe + overlay)** | 🟢 LOW | RatScanner proves BattlEye doesn't ban for: external screen capture, input hooks, transparent overlays. Same pattern. |
| **OCR-based screen reading (pyautogui + Tesseract)** | 🟢 LOW | RatScanner does exactly this successfully for 5+ years with no bans. |
| **Transparent overlay showing market data** | 🟢 LOW | RatScanner does this permanently while running alongside BattlEye game. |
| **Simulated input (pyautogui.click, pyautogui.type)** | 🔴 HIGH | Detectable input patterns. If timing is too regular, easy to flag. |
| **Packet sniffing/injection** | 🔴 VERY HIGH | Directly interferes with game networking — BattlEye specifically monitors for this. |
| **DLL injection / memory hacking** | 🔴 CERTAIN BAN | This is what BattlEye was literally designed to catch. |

### Game Rules (From Terms & Conditions)
The ToS explicitly prohibits:
- "Modify the gaming experience by using software or mechanisms that may affect the function and the game play"
- "Use software playing in place of the player (such as scripts or bots)"
- "Create or use cheats, mods and/or hacks"
- "Abuse any errors in the software of the Game"

**Penalty:** Extraordinary termination, data retention to prevent new account creation, **permanent ban**.

### Mobile Platform
- Uses Easy Anti-Cheat instead of BattlEye
- Less information available about its exact capabilities
- Mobile OS sandboxing limits what EAC can do vs. kernel-level BattlEye on PC
- **Unknown if mobile anti-cheat is more or less permissive**

---

## 4. Strategic Decision: What To Build

### ✅ Green Light — Safe To Build

Based on **RatScanner's 5-year, 0-ban track record** in a BattlEye game (Escape From Tarkov):

| # | Tool | Risk | Notes |
|---|---|---|---|
| 1 | **Smart City Flipping Scanner** | 0/10 | Pure external API/NATS calls. No game interaction. |
| 2 | **Crafting Profit Optimizer** | 0/10 | Pure calculation tool. |
| 3 | **BM Flipper with Statistics** | 0/10 | Data analysis only. |
| 4 | **AlbionTradeHUD** (see Direction 6) | 2/10 | Transparent overlay, no game hooks. RatScanner proves this pattern is safe. |
| 5 | **AlbionScan** (see Direction 7) | 3/10 | Screen capture + OCR for item identification. RatScanner does exactly this. |

### ⚠️ Yellow Light — Use Caution
6. **Desktop overlay with auto-positioning on game window** — Still safe pattern, but more complex positioning logic might look suspicious if behavior is anomalous.

### 🚫 Red Light — Don't Touch
7. **Any bot that interacts with the game client** — input simulation, packet sniffing, memory reading. The Ban is permanent and there's no appeal.

### Recommended Approach
Build Direction #1 (Smart City Flipping Scanner) as the **MVP**, then layer on overlay functionality (Direction 6/7) once the data pipeline is proven.

**Phase 1:** Smart City Flipping Scanner (web or terminal)
- Pure external API/NATS calls
- No game interaction
- Gives you a list: "Buy X in City A at price Y, transport to City B, sell at price Z. Expected profit: W silver. Travel time: T minutes."
- You manually execute the trades in-game

**Phase 2:** Overlay companion (builds on Phase 1 data)
- Transparent borderless window using `pywebview` or `PyQt5`
- Shows real-time best flips, item prices, trade routes
- No game hooks, no injection — just external data display
- Based on RatScanner's proven overlay pattern

---

## 5. Data Sources Available (VERIFIED 2026-04-15)

### ✅ WORKING

| Source | URL/Endpoint | Type | Status | Details |
|---|---|---|---|---|
| AO Data REST API | `west.albion-online-data.com/api/v2/stats/prices/` | REST | ✅ LIVE | Returns real-time data. Supports multi-item, multi-city, multi-quality queries. Rate limited (~100 req/min estimated). |
| AO Item Icons | `render.albiononline.com/v1/item/{name}.png` | Static | ✅ LIVE | Returns item icons at various sizes. |
| **NATS Stream** | `www.albion-online-data.com:4222` | NATS/PubSub | ✅ LIVE | Topic: `marketorders.deduped.bulk`. Credentials: `public / thenewalbiondata`. Returns JSON arrays of market order objects with fields: Id, ItemTypeId, ItemGroupTypeId, LocationId, QualityLevel, EnchantmentLevel, UnitPriceSilver, Amount, AuctionType, Expires. Messages arrive in real-time, ~3-5 sec intervals. **NO RATE LIMITS** |

### ❌ BLOCKED

| Source | URL/Endpoint | Status | Reason |
|---|---|---|---|
| albiononline2d.com | `/en/map/api/nodes/{mapId}` | ❌ BLOCKED | Cloudflare challenge page. Requires browser cookies/captcha. |

### ⚠️ UNVERIFIED

| Source | URL/Endpoint | Status | Notes |
|---|---|---|---|
| AO Data East Server API | `east.albion-online-data.com/api/v2/stats/prices/` | Not tested | Same format as west, for EU servers |
| AO Data Gold API | `west.albion-online-data.com/api/v2/stats/gold/` | ❌ 404 | Deprecated or moved |

---

## 6. Existing Code To Reuse

| Repo | Reusable Parts |
|---|---|
| `repos/albion-market-analysis-v2` | NATS subscriber pattern (`marketorders.deduped.bulk`), MongoDB models, profit calculation logic, React frontend |
| `repos/albion-profit` | Item data (items.js with all item definitions), crafting calculation logic, location data |
| `repos/AlbionFlipper` | BM flip calculation algorithm, UI patterns |
| `repos/AlbionTradeBot` | Market title parsing, item name ↔ unique name conversion, settings structure, LocationId mapping (numeric → name) |
| `external-repos/albion-minimap-overlay` | Map node data structure, coordinate mapping for Outlands (blocked API) |
| `external-repos/RatScanner` | Proven overlay architecture for BattlEye games: transparent WPF window, GDI screen capture, Tesseract OCR, OpenCV template matching, low-level input hooks. See `project_research/ratscanner_analysis.md` for full analysis. |

---

## 7. NATS Stream Data Format (Verified)

Each message is a JSON array of order objects:

```json
[
  {
    "Id": 14846388981,
    "ItemTypeId": "T6_ORE_LEVEL3@3",
    "ItemGroupTypeId": "T6_ORE_LEVEL3",
    "LocationId": 1002,
    "QualityLevel": 1,
    "EnchantmentLevel": 3,
    "UnitPriceSilver": 34941,
    "Amount": 2,
    "AuctionType": "offer",
    "Expires": "2026-05-15T15:06:52.371973"
  }
]
```

Key mapping:
- **LocationId → City Name**: Numeric IDs. From existing code (AlbionTradeBot): 1002=Fort Sterling, etc.
- **AuctionType**: "offer" = sell order, "request" = buy order
- **ItemTypeId**: Standard format (T{tier}_{name}@{enchant})

---

## 8. Built & Verified Components

| Component | File | Status | Notes |
|---|---|---|---|
| NATS stream connection | `test_nats.py` | ✅ VERIFIED | Connects to `www.albion-online-data.com:4222`, receives real-time market data |
| Zone map + pathfinding | `albion_route_finder.py` | ✅ VERIFIED | Dijkstra's algorithm on zone graph, travel time estimation, zone type weights |
| Zone type detection | `check_zone_types.py` | ✅ VERIFIED | Identifies zone types (safe, PvP, dungeon, Outlands towns) |
| Zone data extraction | `albion_map_pathfinder/` | ✅ VERIFIED | Parses zone JSON from map files |
| Map downloading | `download_all_maps.py`, `download_maps.py` | ✅ VERIFIED | Downloads and extracts map data |
| **Web API v0.4.0** | `web/api.py` | ✅ COMPLETE | FastAPI backend with SSE streaming, WebSocket, NATS auto-start, scan job management |
| **Enhanced Scanner** | `albion_market_scanner_enhanced.py` | ✅ COMPLETE | 11K+ items, batch scanning with progress, smart filters, premium profit calc |
| **Real-Time Monitor** | `albion_nats_monitor.py` | ✅ COMPLETE | NATS subscription, in-memory cache, flip detection on every update |
| **Web Dashboard** | `web/static/index.html` | ✅ COMPLETE | 4 tabs: Global Scanner, Real-Time, Route Finder, Item Lookup |

---

## 9. Open Questions

1. What is the user's account age/level in Albion? (determines what activities are accessible)
2. Premium status? (affects Focus availability → crafting profitability)
3. Which server cluster? (West/East/Asia — affects API URL and NATS server)
4. What programming language preference for the tool? (Python + web overlay recommended based on RatScanner)
5. Desktop app, web app, or CLI? (Web + overlay recommended for zero ban risk, then layer overlay)
