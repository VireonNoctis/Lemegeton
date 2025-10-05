"""
Railway Volume Initialization Script
Run this once after deploying to Railway to populate the volume with local data
"""
import os
import shutil
from pathlib import Path

def init_volume():
    """Copy local data files to Railway volume"""
    
    # Source and destination paths
    local_data = Path("data")
    volume_data = Path("/app/data")
    
    print("📦 Starting Railway volume initialization...")
    print(f"📁 Source: {local_data.absolute()}")
    print(f"📁 Destination: {volume_data}")
    
    # Check if we're on Railway
    if not volume_data.exists():
        print("⚠️  Not running on Railway - volume path doesn't exist")
        print("ℹ️  This script should be run on Railway deployment")
        return
    
    # Check if database already exists in volume
    db_path = volume_data / "database.db"
    if db_path.exists():
        print(f"✅ Database already exists in volume ({db_path.stat().st_size:,} bytes)")
        print("ℹ️  Skipping initialization (volume already populated)")
        print("💡 To force re-initialization, delete the volume and redeploy")
        return
    
    # Files to copy
    files_to_copy = [
        "database.db",
        "profile_cache.json",
        "cover_cache_index.json"
    ]
    
    # Copy individual files
    for filename in files_to_copy:
        source = local_data / filename
        dest = volume_data / filename
        
        if source.exists():
            print(f"📄 Copying {filename}...")
            shutil.copy2(source, dest)
            print(f"✅ {filename} copied ({source.stat().st_size} bytes)")
        else:
            print(f"⚠️  {filename} not found locally")
    
    # Copy cover_cache directory
    source_cache = local_data / "cover_cache"
    dest_cache = volume_data / "cover_cache"
    
    if source_cache.exists() and source_cache.is_dir():
        print(f"📁 Copying cover_cache directory...")
        
        if dest_cache.exists():
            shutil.rmtree(dest_cache)
        
        shutil.copytree(source_cache, dest_cache)
        
        # Count files
        cache_files = list(dest_cache.glob("*.png"))
        print(f"✅ Cover cache copied ({len(cache_files)} images)")
    
    # List volume contents
    print("\n📊 Volume contents:")
    for item in volume_data.iterdir():
        if item.is_file():
            size = item.stat().st_size
            print(f"  📄 {item.name}: {size:,} bytes")
        elif item.is_dir():
            file_count = len(list(item.glob("*")))
            print(f"  📁 {item.name}/: {file_count} files")
    
    print("\n🎉 Volume initialization complete!")

if __name__ == "__main__":
    init_volume()
