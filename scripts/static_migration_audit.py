"""
Static Migration Chain & Database Schema Audit Script
Phase 7 Stage 3A Pre-Flight
"""

import glob
import os
import re
from collections import Counter

BASE_DIR = r"C:\VSPL_MM\Material managment system"
MIGRATIONS_DIR = os.path.join(BASE_DIR, r"backend\migrations\versions")

def audit_migrations():
    print("="*70)
    print("VSPL STATIC MIGRATION CHAIN AUDIT")
    print("="*70)
    
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.py")))
    revisions = []
    
    for f in files:
        with open(f, "r", encoding="utf-8") as py_file:
            content = py_file.read()
            
        # Extract revision, down_revision, tables created
        rev_match = re.search(r"^revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
        down_match = re.search(r"^down_revision(?:\s*:\s*[^=]+)?\s*=\s*(?:['\"]([^'\"]+)['\"]|None)", content, re.MULTILINE)
        
        rev_id = rev_match.group(1) if rev_match else None
        down_rev = down_match.group(1) if down_match and down_match.group(1) else None
        
        # Extract tables created in upgrade()
        tables_created = re.findall(r"op\.create_table\(\s*['\"]([^'\"]+)['\"]", content)
        # Extract unique constraints
        unique_constraints = re.findall(r"op\.create_unique_constraint\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*(\[[^\]]+\])", content)
        # Extract indexes
        indexes = re.findall(r"op\.create_index\(\s*[^,]+,\s*['\"]([^'\"]+)['\"]\s*,\s*(\[[^\]]+\])", content)
        # Check downgrade implementation
        has_downgrade = "def downgrade()" in content and "raise NotImplementedError" not in content and "pass" not in content.split("def downgrade()")[1][:100]
        
        # Check PostgreSQL-specific constructs
        pg_enums = re.findall(r"postgresql\.ENUM", content)
        pg_jsonb = re.findall(r"postgresql\.JSONB", content)
        pg_uuid = re.findall(r"postgresql\.UUID", content)
        
        # Check numeric and date columns
        numerics = re.findall(r"sa\.Numeric\(([^)]+)\)", content)
        
        revisions.append({
            "file": os.path.basename(f),
            "revision": rev_id,
            "down_revision": down_rev,
            "tables": tables_created,
            "unique_constraints": unique_constraints,
            "indexes": indexes,
            "has_downgrade": has_downgrade,
            "pg_enums": len(pg_enums),
            "pg_jsonb": len(pg_jsonb),
            "pg_uuid": len(pg_uuid),
            "numerics": set(numerics),
            "lines": len(content.splitlines())
        })
        
    print(f"\nTotal Migration Files: {len(revisions)}")
    for i, r in enumerate(revisions):
        print(f"\n[{i+1}] {r['file']}")
        print(f"    Revision: {r['revision']} | Down Revision: {r['down_revision']}")
        print(f"    Tables Created ({len(r['tables'])}): {r['tables']}")
        print(f"    Indexes ({len(r['indexes'])}), Unique Constraints ({len(r['unique_constraints'])})")
        print(f"    Reversible Downgrade: {r['has_downgrade']}")
        print(f"    PG Types: ENUM={r['pg_enums']}, JSONB={r['pg_jsonb']}, UUID={r['pg_uuid']}")
        print(f"    Numeric Precisions: {r['numerics']}")

    # Chain Validation
    print("\n" + "="*70)
    print("CHAIN TOPOLOGY & INTEGRITY VALIDATION")
    print("="*70)
    
    rev_map = {r['revision']: r for r in revisions}
    errors = []
    
    # 1. Check duplicate revision IDs
    rev_counts = Counter([r['revision'] for r in revisions])
    dups = [k for k, v in rev_counts.items() if v > 1]
    if dups:
        errors.append(f"Duplicate revision IDs found: {dups}")
    else:
        print("  [PASS] All revision IDs are strictly unique.")
        
    # 2. Check root revision
    roots = [r for r in revisions if r['down_revision'] is None]
    if len(roots) != 1:
        errors.append(f"Expected exactly 1 root revision, found {len(roots)}")
    else:
        print(f"  [PASS] Single root revision identified: {roots[0]['revision']} ({roots[0]['file']})")
        
    # 3. Check lineage integrity (every child points to an existing parent)
    current = roots[0]
    visited = [current['revision']]
    for _ in range(len(revisions) - 1):
        children = [r for r in revisions if r['down_revision'] == current['revision']]
        if len(children) == 0:
            errors.append(f"Broken chain at revision {current['revision']}: no child found")
            break
        elif len(children) > 1:
            errors.append(f"Branching detected at revision {current['revision']}: multiple children {[c['revision'] for c in children]}")
            break
        current = children[0]
        visited.append(current['revision'])
        
    if len(visited) == len(revisions):
        print(f"  [PASS] Linear chain verified: {' -> '.join(visited)}")
    else:
        errors.append(f"Chain incomplete: visited {len(visited)} of {len(revisions)} revisions")

    if errors:
        print(f"  [FAIL] Errors detected: {errors}")
    else:
        print("  [SUCCESS] Migration chain is 100% topologically consistent and linear.")

if __name__ == "__main__":
    audit_migrations()
