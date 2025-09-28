import os
import shutil
import time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
old_path = os.path.join(root, 'news_cog.db')
new_dir = os.path.join(root, 'data')
new_path = os.path.join(new_dir, 'news_cog.db')

print(f"Root: {root}")
print(f"Old path: {old_path}")
print(f"New path: {new_path}")

if not os.path.exists(old_path):
    print("No top-level news_cog.db found; nothing to migrate.")
    exit(0)

os.makedirs(new_dir, exist_ok=True)

if os.path.exists(new_path):
    ts = time.strftime('%Y%m%d-%H%M%S')
    backup_path = new_path + f'.backup.{ts}'
    print(f"Target already exists at {new_path}; creating backup {backup_path}")
    shutil.copy2(new_path, backup_path)

print(f"Moving {old_path} -> {new_path}")
shutil.move(old_path, new_path)
print("Migration complete")
