# CLI Restructuring Plan

```bash
  ██████╗ ██████╗ ███╗   ███╗██████╗ ██╗     ███████╗████████╗███████╗
 ██╔════╝██╔═══██╗████╗ ████║██╔══██╗██║     ██╔════╝╚══██╔══╝██╔════╝
 ██║     ██║   ██║██╔████╔██║██████╔╝██║     █████╗     ██║   █████╗  
 ██║     ██║   ██║██║╚██╔╝██║██╔═══╝ ██║     ██╔══╝     ██║   ██╔══╝  
 ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║     ███████╗███████╗   ██║   ███████╗
  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚══════╝╚══════╝   ╚═╝   ╚══════╝
```

> **📦 ARCHIVED:** This restructuring was completed on December 26, 2025.  
> **Commit:** 3798f4e "feat: restructure CLI with uniform command hierarchy and fix Audible model validation"  
> **Archived Date:** January 2, 2026  
> **Reason:** Implementation complete - CLI now has symmetric abs/audible sub-apps  
> **Breaking Changes:** Command paths changed (e.g., `status` → `abs status`, `libraries` → `abs libraries`)

---

## Overview

Restructure the CLI to provide a uniform, consistent command hierarchy where both ABS and Audible commands are organized under their respective sub-apps, with truly global commands at the root level.

## Problem Statement

The current CLI structure is inconsistent:

- `cli.py status` shows only ABS status (misleading - feels global)
- ABS commands are at root level (`libraries`, `items`, `search`, etc.)
- Audible commands are under `audible` sub-app
- This asymmetry is confusing and doesn't scale well

## Proposed Structure

### Root Level (Global Commands)

Commands that affect the entire system or span multiple services:

| Command | Description |
| --- | --- |
| `status` | **NEW** - Combined status: ABS + Audible + Cache |
| `cache` | Manage unified SQLite cache (shared by both) |

### ABS Sub-App (`cli.py abs ...`)

All Audiobookshelf-specific commands:

| Command | Description | Current Location |
| --- | --- | --- |
| `status` | ABS connection status | `cli.py status` (root) |
| `libraries` | List all libraries | `cli.py libraries` (root) |
| `stats` | Library statistics | `cli.py stats` (root) |
| `items` | List library items | `cli.py items` (root) |
| `item` | Item details | `cli.py item` (root) |
| `search` | Search library | `cli.py search` (root) |
| `export` | Export to JSON | `cli.py export` (root) |
| `sample` | Collect golden samples | `cli.py sample-abs` (root) |

### Audible Sub-App (`cli.py audible ...`)

All Audible-specific commands (already organized):

| Command | Description | Status |
| --- | --- | --- |
| `status` | Audible connection status | ✅ Already exists |
| `login` | Login/authenticate | ✅ Already exists |
| `library` | List library items | ✅ Already exists |
| `item` | Item details | ✅ Already exists |
| `search` | Search catalog | ✅ Already exists |
| `export` | Export to JSON | ✅ Already exists |
| `cache` | Cache statistics | ✅ Already exists |
| `sample` | Collect golden samples | `cli.py sample-audible` → move |

### Quality Sub-App (`cli.py quality ...`)

Cross-system quality analysis (no changes needed):

| Command | Description |
| --- | --- |
| `scan` | Scan library for quality analysis |
| `low` | Show low-quality items |
| `item` | Single item quality check |
| `upgrades` | Find upgrade candidates |

## Implementation Steps

### Phase 1: Create ABS Sub-App

1. Create `abs_app = typer.Typer(help="Audiobookshelf API commands")`
2. Register with `app.add_typer(abs_app, name="abs")`

### Phase 2: Move ABS Commands

Move these commands from `@app.command()` to `@abs_app.command()`:

- `status` → `abs status`
- `libraries` → `abs libraries`
- `stats` → `abs stats`
- `items` → `abs items`
- `item` → `abs item`
- `search` → `abs search`
- `export` → `abs export`
- `sample-abs` → `abs sample`

### Phase 3: Create Global Status

New `@app.command("status")` that shows:

- ABS connection + library count
- Audible connection + library count
- Cache summary (entries, size)
- Overall health indicator

### Phase 4: Move Sample Commands

- `sample-abs` → `abs sample`
- `sample-audible` → `audible sample`

## Before/After Comparison

### Before

```bash
$ cli.py --help
Commands:
  status           Check connection status to ABS server.  # CONFUSING!
  cache            Manage unified SQLite cache.
  libraries        List all libraries.                     # ABS but at root
  stats            Show library statistics.                # ABS but at root
  items            List library items.                     # ABS but at root
  item             Show details for a specific item.       # ABS but at root
  search           Search a library.                       # ABS but at root
  export           Export all library items to JSON.       # ABS but at root
  sample-abs       Collect golden samples from ABS API.
  sample-audible   Collect golden samples from Audible API.
  audible          Audible API commands
  quality          Audio quality analysis commands
```

### After

```bash
$ cli.py --help
Commands:
  status    Show global status (ABS + Audible + Cache)
  cache     Manage unified SQLite cache
  abs       Audiobookshelf API commands
  audible   Audible API commands
  quality   Audio quality analysis commands

$ cli.py abs --help
Commands:
  status     Check ABS connection status
  libraries  List all libraries
  stats      Show library statistics
  items      List library items
  item       Show details for a specific item
  search     Search a library
  export     Export all library items to JSON
  sample     Collect golden samples from ABS API
```

## Benefits

1. **Symmetry**: `abs` and `audible` sub-apps mirror each other
2. **Clear scoping**: Obvious which API each command uses
3. **Global status**: Single command shows full system health
4. **Discoverability**: `--help` at each level shows relevant commands
5. **Scalability**: Easy to add more sub-apps (e.g., `cli.py sync ...`)

## Migration Notes

- No changes to command functionality, but command paths have changed (breaking for existing scripts/aliases)
- Users will need to update scripts/aliases to use new command paths
- Consider adding deprecation warnings for direct root commands (optional)
