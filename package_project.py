import os

def package_project(output_file="project_package.txt"):
    """
    Empaqueta todo el proyecto en un solo archivo de texto.

    Esta función itera a través del directorio del proyecto, lee el contenido de
    cada archivo y lo anexa a un único archivo de salida. Agrega encabezados para
    separar el contenido de cada archivo.
    """
    excluded_dirs = ['.git', '__pycache__', '.pytest_cache', 'dist', 'build', '.venv', 'node_modules', '.idea']
    excluded_files = ['project_package.txt', 'package_project.py']
    included_filenames = ['Pipfile', 'Makefile', 'LICENSE', 'README', 'CHANGELOG']
    included_extensions = ['.md', '.py', '.json', '.toml', '.ini', '.cfg', '.lock', 'setup.py', '.gitignore']

    with open(output_file, 'w', encoding='utf-8') as f_out:
        for root, dirs, files in os.walk("."):
            # Excluir directorios especificados
            dirs[:] = [d for d in dirs if d not in excluded_dirs]

            for file in files:
                if file in excluded_files:
                    continue

                filepath = os.path.join(root, file)

                should_include = False
                # Check for exact filename matches
                if file in included_filenames:
                    should_include = True
                # Check for extension matches
                else:
                    for ext in included_extensions:
                        if file.endswith(ext):
                            should_include = True
                            break

                if should_include:
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f_in:
                            content = f_in.read()
                            f_out.write(f"--- {filepath} ---\n\n")
                            f_out.write(content)
                            f_out.write("\n\n")
                    except Exception as e:
                        f_out.write(f"--- Error al leer {filepath}: {e} ---\n\n")

if __name__ == "__main__":
    package_project()
