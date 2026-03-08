import os
import sys
import importlib
from ast import parse, Import, ImportFrom

def find_imported_modules(directory='.'):
    """Scan Python files and extract all imported module names."""
    modules = set()
    extensions = ['.py', '.pyi']

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(tuple(extensions)):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()

                    tree = parse(content, filename=file_path)

                    # Extract import names
                    for node in tree.body:
                        if isinstance(node, Import):
                            modules.update(alias.name.split('.')[0] for alias in node.names)
                        elif isinstance(node, ImportFrom):
                            if node.module:
                                modules.add(node.module.split('.')[0])
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    return modules

def check_module_installed(module_name):
    """Check if a module is installed using importlib."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

def install_missing_dependencies(modules, exclude=None):
    """Install modules that are missing from requirements."""
    if exclude is None:
        exclude = set()

    missing = [mod for mod in modules if mod not in exclude and not check_module_installed(mod)]

    if not missing:
        print("No dependencies need installation.")
        return True

    print(f"
Found {len(missing)} missing dependencies:")
    print('-' + '-'*80)
    print('\n'.join(missing))
    print('-'*92)

    if input('Install these? (y/n): ').lower() != 'y':
        return False

    try:
        import subprocess
        result = subprocess.run(
            ['pip', 'install'] + missing,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Installation failed: {e}")
        print(e.stdout)
        return False

if __name__ == "__main__":
    project_dir = os.getcwd()
    print(f"Scanning project: {project_dir}")
    modules = find_imported_modules(project_dir)

    if modules:
        print(f"
Found {len(modules)} modules in code:")
        print('-' * 50)
        for mod in sorted(modules):
            status = '✓ Installed' if check_module_installed(mod) else '✗ Missing'
            print(f"{mod}: {status}")

        install_missing_dependencies(modules, exclude={'os', 'sys', 'math'})
    else:
        print("No import statements found in project.")