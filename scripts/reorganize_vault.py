import os
import re
import shutil
from datetime import datetime
from pathlib import Path

VAULT_BASE = Path("/app/vault/Agent-Research") if os.environ.get("OBSIDIAN_VAULT_PATH") else Path(__file__).parent.parent / "vault" / "Agent-Research"
if not VAULT_BASE.exists():
    VAULT_BASE = Path.home() / "personal-agent" / "vault" / "Agent-Research"

CATEGORIES = ["Papers", "Ideas", "YouTube", "FB-Marketplace"]

def extract_date(content: str) -> str | None:
    # Try to find date: or created: in frontmatter
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx != -1:
            frontmatter = content[:end_idx]
            match = re.search(r"^(?:date|created):\s*['\"]?(\d{4}-\d{2}-\d{2})", frontmatter, re.MULTILINE)
            if match:
                return match.group(1)
    return None

def main():
    print(f"Reorganizing vault at: {VAULT_BASE}")
    
    if not VAULT_BASE.exists():
        print("Vault not found.")
        return

    moved_count = 0

    for category in CATEGORIES:
        category_dir = VAULT_BASE / category
        if not category_dir.exists():
            continue
            
        for file_path in category_dir.glob("*.md"):
            if not file_path.is_file():
                continue
                
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            date_str = extract_date(content)
            
            if not date_str:
                # Extract date from filename if possible (e.g., deals-2026-03-10.md)
                match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
                if match:
                    date_str = match.group(1)
                else:
                    # Fallback to last modified time
                    mtime = file_path.stat().st_mtime
                    date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

            target_dir = category_dir / date_str
            target_dir.mkdir(parents=True, exist_ok=True)
            
            target_path = target_dir / file_path.name
            
            if file_path != target_path:
                shutil.move(str(file_path), str(target_path))
                print(f"Moved: {file_path.name} -> {date_str}/")
                moved_count += 1
                
    print(f"Total files reorganized: {moved_count}")

if __name__ == "__main__":
    main()
