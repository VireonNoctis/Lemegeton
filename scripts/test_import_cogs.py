import os
import sys
import importlib
import traceback

# Ensure project root is on sys.path
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)

cogs_dir = os.path.join(root, 'cogs')
if not os.path.exists(cogs_dir):
    print('Cogs directory not found:', cogs_dir)
    sys.exit(2)

results = []

for root_dir, dirs, files in os.walk(cogs_dir):
    for f in files:
        if not f.endswith('.py'):
            continue
        if f == '__init__.py':
            continue
        full_path = os.path.join(root_dir, f)
        rel_path = os.path.relpath(full_path, cogs_dir)
        module_rel = rel_path.replace(os.path.sep, '.')[:-3]
        module_name = f'cogs.{module_rel}'

        try:
            importlib.import_module(module_name)
            results.append((module_name, 'OK', ''))
            print(f'[OK]   {module_name}')
        except Exception:
            tb = traceback.format_exc()
            results.append((module_name, 'FAIL', tb))
            print(f'[FAIL] {module_name}')
            print(tb)

# Summary
ok = [r for r in results if r[1] == 'OK']
fail = [r for r in results if r[1] == 'FAIL']
print('\nSUMMARY:')
print(f'  Total modules scanned: {len(results)}')
print(f'  OK: {len(ok)}')
print(f'  FAIL: {len(fail)}')

if fail:
    print('\nFailed modules:')
    for m, _, tb in fail:
        print('-' * 80)
        print(m)
        print(tb)

# Exit non-zero if any failures
if fail:
    sys.exit(1)
else:
    sys.exit(0)
