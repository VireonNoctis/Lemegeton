"""
Upload local data files to Railway persistent volume.
Run this script via: railway run python upload_to_railway.py
"""
import os
import shutil
from pathlib import Path

def upload_data():
    """Copy local data directory to Railway volume."""
    source = Path("data")
    destination = Path("/app/data")
    
    print("🚀 Starting data upload to Railway volume...")
    print(f"📂 Source: {source.absolute()}")
    print(f"📁 Destination: {destination}")
    
    if not source.exists():
        print("❌ Error: data/ directory not found locally!")
        return False
    
    # Create destination if it doesn't exist
    destination.mkdir(parents=True, exist_ok=True)
    print("✅ Destination directory ready")
    
    # Copy all files and subdirectories
    files_copied = 0
    errors = 0
    
    for item in source.rglob("*"):
        if item.is_file():
            # Skip backup files
            if ".backup" in item.name or item.name.endswith(".backup"):
                print(f"⏭️  Skipping backup: {item.name}")
                continue
            
            # Calculate relative path
            rel_path = item.relative_to(source)
            dest_file = destination / rel_path
            
            # Create parent directories
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                # Copy file
                shutil.copy2(item, dest_file)
                files_copied += 1
                print(f"✅ Copied: {rel_path} ({item.stat().st_size} bytes)")
            except Exception as e:
                errors += 1
                print(f"❌ Error copying {rel_path}: {e}")
    
    print("\n" + "="*60)
    print(f"📊 Upload Summary:")
    print(f"   ✅ Files copied: {files_copied}")
    print(f"   ❌ Errors: {errors}")
    print("="*60)
    
    if errors == 0:
        print("🎉 Data upload completed successfully!")
        return True
    else:
        print("⚠️  Upload completed with some errors")
        return False

if __name__ == "__main__":
    success = upload_data()
    exit(0 if success else 1)
