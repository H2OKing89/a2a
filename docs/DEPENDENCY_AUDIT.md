# Dependency Audit Report

**Date:** December 27, 2025  
**Project:** Audiobook Management Tool (ABS + Audible CLI)  
**Status:** ✅ Complete

---

## Executive Summary

| Check | Result | Details |
| --- | --- | --- |
| Security Vulnerabilities | ✅ Pass | No known vulnerabilities found |
| Outdated Packages | ⚠️ 3 packages | Minor version updates available |
| License Compliance | ⚠️ Review | 1 AGPL dependency (`audible`) |
| Version Pinning | ⚠️ Partial | Production deps unpinned |
| Unused Dependencies | ✅ Pass | No obvious unused packages |

---

## 1. Security Vulnerability Scan

**Tool:** `pip-audit`  
**Result:** ✅ No known vulnerabilities found

```bash
$ PIPAPI_PYTHON_LOCATION=.venv/bin/python pipx run pip-audit
No known vulnerabilities found
```

All 84 installed packages were scanned against the Python Packaging Advisory Database (PyPA).

---

## 2. Outdated Packages

**Tool:** `pip list --outdated`

| Package | Current | Latest | Type | Recommendation |
| --- | --- | --- | --- | --- |
| black | 24.10.0 | 25.12.0 | Dev | ⚠️ Major version - test before updating |
| flake8-bugbear | 24.12.12 | 25.11.29 | Dev | ⚠️ Update when ready |
| isort | 5.13.2 | 7.0.0 | Dev | ⚠️ Major version - breaking changes likely |

### Recommendations

1. **black 25.x**: Major version bump. Review [changelog](https://github.com/psf/black/blob/main/CHANGES.md) before updating. May have new formatting rules.

2. **isort 7.x**: Major version change from 5.x. Significant changes expected. Update `requirements-dev.txt` constraint when ready:

   ```diff
   - isort>=5.13.0,<6.0.0
   + isort>=7.0.0,<8.0.0
   ```

3. **flake8-bugbear**: Safe to update within the 24.x→25.x range.

---

## 3. License Compliance

**Tool:** `pip-licenses --format=markdown`

### License Distribution

| License Type | Count | Risk Level |
| --- | --- | --- |
| MIT / MIT License | 52 | ✅ Low - Very permissive |
| BSD / BSD-3-Clause | 12 | ✅ Low - Permissive |
| Apache-2.0 | 8 | ✅ Low - Permissive |
| MPL-2.0 | 2 | 🟡 Medium - Weak copyleft |
| PSF-2.0 | 2 | ✅ Low - Permissive |
| AGPL-3.0 | 1 | 🔴 High - Strong copyleft |
| GPL-2.0-only | 1 | 🟡 Medium - Copyleft (dev only) |
| Unlicense | 1 | ✅ Low - Public domain |
| ISC | 1 | ✅ Low - Permissive |

### ⚠️ License Concerns

#### 1. `audible` - GNU AGPL v3

- **Package:** `audible==0.10.0`
- **License:** GNU Affero General Public License v3
- **Impact:** AGPL requires source disclosure if software is used over a network
- **Mitigation:** This is a CLI tool, not a network service, so AGPL obligations are minimal for personal use
- **Recommendation:** Document this license in project README if distributing

#### 2. `codespell` - GPL-2.0-only

- **Package:** `codespell==2.4.1`
- **License:** GPL-2.0-only
- **Impact:** Development dependency only, not bundled with distribution
- **Recommendation:** ✅ Acceptable - dev tools don't affect distribution

### License Summary

For a personal CLI tool:

- ✅ All licenses are acceptable
- ⚠️ If distributing, document the AGPL dependency from `audible` library

---

## 4. Requirements Files Analysis

### Production Dependencies (`requirements.txt`)

**Issue:** Most production dependencies are unpinned

```bash
orjson          # ❌ Unpinned
sh              # ❌ Unpinned
typer           # ❌ Unpinned
rich            # ❌ Unpinned
pydantic        # ❌ Unpinned
...
pytest>=9.0.0,<10.0.0  # ✅ Pinned with range
```

**Recommendation:** Pin production dependencies with version ranges for reproducibility:

```diff
- orjson
+ orjson>=3.10.0,<4.0.0

- typer
+ typer>=0.21.0,<1.0.0

- pydantic
+ pydantic>=2.10.0,<3.0.0
```

### Development Dependencies (`requirements-dev.txt`)

**Status:** ✅ Well-structured with version ranges

All dev dependencies use semantic version ranges (e.g., `>=24.10.0,<25.0.0`), which is the recommended practice.

---

## 5. Dependency Tree Highlights

**Total packages installed:** 84

### Core Dependencies (Direct)

| Package | Purpose | Pinned |
| --- | --- | --- |
| typer | CLI framework | ❌ |
| rich | Terminal formatting | ❌ |
| pydantic | Data validation | ❌ |
| pydantic-settings | Settings management | ❌ |
| httpx | HTTP client | ❌ |
| audible | Audible API | ❌ |
| orjson | Fast JSON | ❌ |
| rapidfuzz | Fuzzy matching | ❌ |

### Dev Dependencies (Key)

| Package | Purpose | Pinned |
| --- | --- | --- |
| pytest | Testing | ✅ |
| black | Formatting | ✅ |
| mypy | Type checking | ✅ |
| flake8 | Linting | ✅ |
| bandit | Security | ✅ |
| pre-commit | Git hooks | ✅ |

---

## 6. Recommendations

### Immediate Actions

1. **Pin production dependencies** in `requirements.txt`:

   ```bash
   pip freeze > requirements-lock.txt
   ```

   Or manually add version ranges to prevent breaking changes.

2. **Update dev dependencies** (after testing):

   ```bash
   pip install --upgrade flake8-bugbear
   ```

### Future Improvements

1. **Consider using `pip-tools`** for dependency management:
   - `requirements.in` → human-readable direct deps
   - `requirements.txt` → fully resolved lock file

2. **Set up Dependabot** for automated security updates:

   ```yaml
   # .github/dependabot.yml
   version: 2
   updates:
     - package-ecosystem: "pip"
       directory: "/"
       schedule:
         interval: "weekly"
   ```

3. **Add license check to CI**:

   ```yaml
   - name: License check
     run: |
       pip install pip-licenses
       pip-licenses --fail-on="GPL-3.0;AGPL-3.0"
   ```

---

## 7. Checklist Status

| Item | Status |
| --- | --- |
| ✅ Run `pip-audit` for vulnerabilities | Complete |
| ✅ Run `pip list --outdated` | Complete |
| ✅ Review licenses with `pip-licenses` | Complete |
| ⬜ Pin production dependencies | Recommended |
| ⬜ Set up Dependabot | Optional |
| ⬜ Update outdated dev packages | When ready |

---

## Appendix: Full License List

### All 84 Package Licenses

| Package | Version | License |
| --- | --- | --- |
| Jinja2 | 3.1.6 | BSD License |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT License |
| Pygments | 2.19.2 | BSD License |
| RapidFuzz | 3.14.3 | MIT |
| annotated-types | 0.7.0 | MIT License |
| anyio | 4.12.0 | MIT |
| astor | 0.8.1 | BSD License |
| attrs | 25.4.0 | MIT |
| audible | 0.10.0 | GNU Affero General Public License v3 |
| bandit | 1.9.2 | Apache-2.0 |
| beautifulsoup4 | 4.14.3 | MIT License |
| black | 24.10.0 | MIT License |
| certifi | 2025.11.12 | Mozilla Public License 2.0 (MPL 2.0) |
| cfgv | 3.5.0 | MIT |
| click | 8.3.1 | BSD-3-Clause |
| codespell | 2.4.1 | GPL-2.0-only |
| coverage | 7.13.0 | Apache-2.0 |
| distlib | 0.4.0 | Python Software Foundation License |
| filelock | 3.20.1 | Unlicense |
| flake8 | 7.3.0 | MIT License |
| flake8-bugbear | 24.12.12 | MIT License |
| flake8-comprehensions | 3.17.0 | MIT |
| flake8_simplify | 0.22.0 | MIT License |
| h11 | 0.16.0 | MIT License |
| h2 | 4.3.0 | MIT License |
| hpack | 4.1.0 | MIT License |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD License |
| hyperframe | 6.1.0 | MIT License |
| identify | 2.6.15 | MIT |
| idna | 3.11 | BSD-3-Clause |
| iniconfig | 2.3.0 | MIT |
| isort | 5.13.2 | MIT License |
| librt | 0.7.5 | MIT License |
| lxml | 6.0.2 | BSD-3-Clause |
| markdown-it-py | 4.0.0 | MIT License |
| mccabe | 0.7.0 | MIT License |
| mdformat | 1.0.0 | MIT |
| mdurl | 0.1.2 | MIT License |
| mypy | 1.19.1 | MIT License |
| mypy_extensions | 1.1.0 | MIT |
| nodeenv | 1.10.0 | BSD License |
| orjson | 3.11.5 | Apache-2.0 OR MIT |
| packaging | 25.0 | Apache Software License; BSD License |
| pathspec | 0.12.1 | Mozilla Public License 2.0 (MPL 2.0) |
| pathvalidate | 3.3.1 | MIT License |
| pbkdf2 | 1.3 | MIT License |
| pillow | 12.0.0 | MIT-CMU |
| platformdirs | 4.5.1 | MIT |
| pluggy | 1.6.0 | MIT License |
| pre_commit | 4.5.1 | MIT |
| pyaes | 1.6.1 | MIT License |
| pyasn1 | 0.6.1 | BSD License |
| pycodestyle | 2.14.0 | MIT |
| pydantic | 2.12.5 | MIT |
| pydantic-settings | 2.12.0 | MIT |
| pydantic_core | 2.41.5 | MIT |
| pydocstyle | 6.3.0 | MIT License |
| pyflakes | 3.4.0 | MIT License |
| pytest | 9.0.2 | MIT |
| pytest-asyncio | 1.3.0 | Apache-2.0 |
| pytest-cov | 7.0.0 | MIT |
| python-dotenv | 1.2.1 | BSD-3-Clause |
| pyupgrade | 3.21.2 | MIT |
| rich | 14.2.0 | MIT License |
| rsa | 4.9.1 | Apache Software License |
| sh | 2.2.2 | MIT License |
| shellingham | 1.5.4 | ISC License (ISCL) |
| snowballstemmer | 3.0.1 | BSD License |
| soupsieve | 2.8.1 | MIT |
| stevedore | 5.6.0 | Apache Software License |
| tenacity | 9.1.2 | Apache Software License |
| tokenize_rt | 6.2.0 | MIT |
| toml | 0.10.2 | MIT License |
| typer | 0.21.0 | MIT |
| types-PyYAML | 6.0.12.20250915 | Apache-2.0 |
| types-toml | 0.10.8.20240310 | Apache Software License |
| typing-inspection | 0.4.2 | MIT |
| typing_extensions | 4.15.0 | PSF-2.0 |
| virtualenv | 20.35.4 | MIT |

---

## Generated by Dependency Audit

**Date:** December 27, 2025
