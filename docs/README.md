# Documentation Guide

Welcome to the A2A project documentation! This guide helps you navigate and maintain our docs.

---

## 📚 Quick Navigation

| What are you looking for? | Go here |
| --------------------------- | --------- |
| **Current project status** | [STATUS.md](STATUS.md) |
| **Active planning documents** | [planning/](planning/) |
| **Completed audit reports** | [archive/audits/](archive/audits/) |
| **Implementation history** | [archive/completed/](archive/completed/) |
| **API reference (ABS)** | [ABS/](ABS/) (upstream docs) |
| **API reference (Audible)** | [Audible/](Audible/) (upstream docs) |

---

## 🗂️ Folder Structure

```text
docs/
├── README.md                    # This file - documentation guide
├── STATUS.md                    # Master status tracker - START HERE
│
├── planning/                    # 🟢 Active planning documents
│   ├── AUDIT_PLANNING.md       # Future audit roadmap
│   ├── ENHANCED_UPGRADE_PLAN.md # Quality detection design
│   └── LIBATION_QUALITY_SCAN_ANALYSIS.md # External research
│
├── archive/                     # 📦 Historical/completed documents
│   ├── audits/                 # Completed audit reports
│   │   ├── AUDIT_REPORT.md     # Code quality audit (Dec 27, 2025)
│   │   ├── DEPENDENCY_AUDIT.md # Dependency audit (Dec 27, 2025)
│   │   ├── DESIGN_AUDIT.md     # Architecture audit (Dec 27, 2025)
│   │   └── SECURITY_AUDIT.md   # Security audit (Dec 28, 2025)
│   │
│   └── completed/              # Finished implementations
│       ├── AUDIBLE_ENRICHMENT_REFACTOR.md # Module refactoring
│       └── CLI_RESTRUCTURING.md           # CLI reorganization
│
├── ABS/                        # Audiobookshelf API reference
│   └── *.md                    # Endpoint documentation (upstream)
│
└── Audible/                    # Audible API reference
    └── *.md                    # Endpoint documentation (upstream)
```

---

## 📋 Document Types

### 🟢 Planning Documents (`planning/`)

Active design and planning documents for ongoing/future work.

- **When to create:** Starting a new feature or major refactoring
- **When to update:** As implementation progresses
- **When to archive:** After implementation is complete

**Example:** `ENHANCED_UPGRADE_PLAN.md` - tracks quality detection improvements

### 📦 Audit Reports (`archive/audits/`)

Point-in-time snapshots of code quality, security, dependencies, etc.

- **When to create:** Starting a comprehensive audit
- **When to archive:** After findings are addressed
- **Retention:** Keep indefinitely for historical reference

**Example:** `SECURITY_AUDIT.md` - security review from Dec 28, 2025

### ✅ Completed Implementations (`archive/completed/`)

Documentation for finished refactorings, restructurings, or major changes.

- **When to create:** Planning a major code change
- **When to archive:** After implementation is merged
- **Metadata required:** Completion date, commit hash, breaking changes

**Example:** `CLI_RESTRUCTURING.md` - CLI reorganization (commit 3798f4e)

### 📖 API Reference (`ABS/`, `Audible/`)

Upstream API documentation for external services.

- **Source:** Generated from external API specifications
- **Updates:** Refresh when upstream APIs change
- **Usage:** Reference during development

---

## 🔄 Document Lifecycle

```text
Planning → Implementation → Completion → Archive
   ↓            ↓              ↓           ↓
Create in    Update with    Add metadata  Move to
planning/    progress       & commit hash archive/
```

### Step-by-Step Guide

#### 1. Creating a Planning Document

```bash
# Create new planning doc
cd docs/planning/
touch MY_FEATURE_PLAN.md

# Template structure:
# - Overview / Problem Statement
# - Proposed Solution
# - Implementation Steps (with checkboxes)
# - Timeline / Status tracking
```

#### 2. Tracking Progress

- Use checkboxes for implementation steps: `- [ ]` → `- [x]`
- Add commit references when steps complete
- Update "Last Updated" date in header

#### 3. Archiving Completed Work

```bash
# After implementation is complete:
cd docs/

# 1. Add archive metadata header (see examples below)
# 2. Move to appropriate archive folder
mv planning/MY_FEATURE_PLAN.md archive/completed/

# 3. Update STATUS.md with completion info
```

#### 4. Archive Metadata Template

Add this header to documents before archiving:

```markdown
# Document Title - COMPLETED ✅

> **📦 ARCHIVED:** [Brief completion statement]  
> **Commit:** [hash] "[commit message]"  
> **Archived Date:** [date]  
> **Status:** [✅ Complete / 🟡 Partial / etc.]  
> **Reason:** [why archived - e.g., "Implementation complete"]  
> **See also:** [links to related current docs or code]

---
```

**Example:**

```markdown
# CLI Restructuring Plan - COMPLETED ✅

> **📦 ARCHIVED:** This restructuring was completed on December 26, 2025.  
> **Commit:** 3798f4e "feat: restructure CLI with uniform command hierarchy"  
> **Archived Date:** January 2, 2026  
> **Reason:** Implementation complete - CLI now has symmetric abs/audible sub-apps  
> **Breaking Changes:** Command paths changed (e.g., `status` → `abs status`)

---
```

---

## 🎯 Best Practices

### For Planning Documents

- ✅ **DO:** Use clear, actionable checkboxes for implementation steps
- ✅ **DO:** Reference commit hashes when marking steps complete
- ✅ **DO:** Keep "Last Updated" date current
- ❌ **DON'T:** Leave documents in planning/ after implementation is done

### For Audit Reports

- ✅ **DO:** Include completion criteria upfront
- ✅ **DO:** Track findings with severity levels
- ✅ **DO:** Link to commits that address findings
- ❌ **DON'T:** Update archived audits (create new audit instead)

### For Archive Maintenance

- ✅ **DO:** Add archive metadata headers before moving
- ✅ **DO:** Include commit hash and completion date
- ✅ **DO:** Document breaking changes or deprecations
- ❌ **DON'T:** Delete completed docs (archive them instead)

---

## 🔍 Finding Information

### "I want to know what's currently being worked on"

→ Check [STATUS.md](STATUS.md) → Active Planning Documents section

### "I want to see past audit results"

→ Browse [archive/audits/](archive/audits/)

### "I want to understand why something was changed"

→ Check [archive/completed/](archive/completed/) for implementation docs  
→ Look for commit hash in archive metadata, then: `git show <hash>`

### "I want to know what's deprecated"

→ Check [STATUS.md](STATUS.md) → Look for 📦 Archived items  
→ Each archived doc has deprecation details in header

### "I want to plan a new feature"

→ Create new doc in [planning/](planning/)  
→ Update [STATUS.md](STATUS.md) to add it to tracking

---

## 📊 Status Indicators

Documents and sections use these emoji indicators:

| Emoji | Meaning | Usage |
| ------- | --------- | ------- |
| 🟢 | Active / In Progress | Currently being worked on |
| 🟡 | Pending / Partially Complete | Waiting or partially done |
| 🔴 | Blocked / Needs Attention | Has blockers or issues |
| ✅ | Complete | Finished successfully |
| 📦 | Archived | Historical reference only |
| ⚠️ | Warning / Caution | Important note or caveat |

---

## 🛠️ Maintenance Tasks

### Monthly Review (First of month)

1. Review active planning docs in `planning/`
2. Archive any completed implementations
3. Update [STATUS.md](STATUS.md) completion dates
4. Check for stale documents (>3 months without updates)

### Per-Release Review

1. Update relevant docs with changes from release
2. Archive completed planning docs
3. Document any deprecations or breaking changes
4. Add commit hashes to completed work

### Annual Review (January)

1. Archive old audits (>1 year)
2. Consider re-running key audits (security, dependencies)
3. Review and consolidate planning docs
4. Update this README if structure has changed

---

## 📝 Document Templates

### Planning Document Template

```markdown
# [Feature Name] Implementation Plan

**Created:** [date]  
**Status:** 🟢 Active  
**Last Updated:** [date]

---

## Overview

[Brief description of feature/refactoring]

## Problem Statement

[What problem are we solving?]

## Proposed Solution

[High-level approach]

## Implementation Steps

- [ ] Step 1: [description]
- [ ] Step 2: [description]
- [ ] Step 3: [description]

## Timeline

- **Started:** [date]
- **Target Completion:** [date]
- **Actual Completion:** [date or TBD]

## Commits

- [hash] - [description]
```

### Audit Report Template

```markdown
# [Audit Type] Report

**Date:** [date]  
**Status:** [🟢 Active / ✅ Complete]  

---

## Executive Summary

[High-level findings]

## Findings

### Finding 1: [title]

**Severity:** [High/Medium/Low]  
**Status:** [Open/Fixed/Accepted]  

[Description and recommendations]

## Action Items

- [ ] Item 1
- [ ] Item 2

## Conclusion

[Summary]
```

---

## 🤝 Contributing to Docs

When adding or updating documentation:

1. **Follow the structure** - put docs in the right folder
2. **Use templates** - consistency helps everyone
3. **Update STATUS.md** - keep the tracker current
4. **Add metadata** - dates, commits, status indicators
5. **Link related docs** - help future you (and others!)

Questions? Check [STATUS.md](STATUS.md) or review archived examples.

---

**Last Updated:** January 2, 2026  
**Maintainer:** Project team  
**Version:** 1.0
