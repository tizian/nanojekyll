import markdown, os, shutil, sys, time, yaml
from pathlib import Path
from liquid import Liquid

VERSION = "0.1.0"

BASE_PATH     = Path.cwd()
CONFIG_PATH   = BASE_PATH/"_config.yml"
SITE_PATH     = BASE_PATH/"_site"
INCLUDES_PATH = BASE_PATH/"_includes"
LAYOUTS_PATH  = BASE_PATH/"_layouts"
ROOT_PATH     = BASE_PATH/"_root"

HELP_TEXT = f"""\
nanojekyll version {VERSION}
A minimal static site generator. Certified free from Ruby.

Usage: nanojekyll.py [command]

commands:
    new      Create a new site.
    build    Build the site.
    serve    Run a local server and continuously rebuild the site.
"""

NEW_CONFIG_STR = """\
title: "nanojekyll site"

files:
    - "index.html"
"""

NEW_HTML_STR = """\
---
text: "Hello World!"
---
<html>
  <head></head>
  <body><h1>{{ site.title }}</h1>{{ page.text }}</body>
</html>
"""

INVALID_SITE_STR = """\
No nanojekyll site found at this location.
Create one by running `nanojekyll new` instead.\
"""

SERVER_STR = """
Running local server at http://localhost:8000 ... press ctrl-c to stop.\
"""

def create_paths():
    os.makedirs(SITE_PATH,     exist_ok=True)
    os.makedirs(INCLUDES_PATH, exist_ok=True)
    os.makedirs(LAYOUTS_PATH,  exist_ok=True)
    os.makedirs(ROOT_PATH,     exist_ok=True)

def new_site():
    if os.path.exists(CONFIG_PATH):
        print("nanojekyll site already exists at this location.")
        return False

    with open(CONFIG_PATH, "a") as f:
        f.write(NEW_CONFIG_STR)

    if not os.path.exists(BASE_PATH/"index.html"):
        with open(BASE_PATH/"index.html", "a") as f:
            f.write(NEW_HTML_STR)

    create_paths()

    return True

def read_file(path):
    if path.suffix != ".html" and path.suffix != ".md":
        raise Exception("nanojekyll can only process .html or .md files.")

    # Read in file.
    with open(path) as f:
        content = f.read()

    # Extract and parse YAML header surrounded by "---".
    header = {}
    delim = "---"
    a = content.find(delim)
    if a >= 0:
        b = content.find(delim, a + len(delim))
        header = yaml.safe_load(content[a + len(delim):b])

        # The remainder is the main content.
        content = content[b + len(delim):]

    # If necessary, convert markdown into html.
    if path.suffix == ".md":
        content = markdown.markdown(content)

    return header, content

def process_file(state, site, file):
    if not file["header"].get("create_page", True):
        return # Skip files that should not be processed.

    # Build liquid parameter dict.
    liquid_params = {
        "site": site,
        "page": file["header"]
    }
    for key, value in state["includes"].items():
        liquid_params[key] = value

    # First liquid pass: process content itself.
    liq = Liquid(file["content"], from_file=False)
    output = liq.render(liquid_params, mode="jekyll")

    # Second liquid pass: insert content into a layout, if specified.
    if "layout" in file["header"]:
        liquid_params["content"] = output
        liq = Liquid(state["layouts"][file["header"]["layout"]])
        output = liq.render(liquid_params, mode="jekyll")

    # Assemble the output path.
    if "path" in file["header"]:
        # Override specified in file header.
        outpath = state["site_path"]/file["header"]["path"]
        outpath = outpath/"index"
    else:
        outpath = (state["site_path"]/file["path"])
        if "index" not in str(outpath):
            outpath = outpath/"index"

    os.makedirs(outpath.parent, exist_ok=True)
    outpath = outpath.with_suffix(".html")

    # And finally write file to the right place.
    with open(outpath, "w") as f:
        f.write(output)

def build_site(verbose):
    if not os.path.exists(CONFIG_PATH):
        print(INVALID_SITE_STR)
        return False

    create_paths()

    site  = {}  # Dict that keeps parameters accessible through liquid.
    state = {}  # Dict for keeping internal data such as includes/layouts.
    state["base_path"]     = BASE_PATH
    state["site_path"]     = SITE_PATH
    state["includes_path"] = INCLUDES_PATH
    state["layouts_path"]  = LAYOUTS_PATH

    # Add `_config.yml` contents to the `site` dictionary.
    with open(CONFIG_PATH) as f:
        config = f.read()
        config = yaml.safe_load(config)
        site = config

    # Also provide additional parameters.
    site["time"] = time.time() # Unix timestamp.

    # Get all paths from `_includes` and `_layouts` for later use.
    state["includes"] = {}
    for item in os.listdir(INCLUDES_PATH):
        path = Path(INCLUDES_PATH/item)
        state["includes"][path.stem] = { "html": str(path) }

    state["layouts"] = {}
    for item in os.listdir(LAYOUTS_PATH):
        path = Path(LAYOUTS_PATH/item)
        state["layouts"][path.stem] = str(path)

    # Copy over everything from the root to the `_site` output directory, except
    # file that will be processed later.
    excludes = [BASE_PATH/file for file in config["files"] if type(file) == str]
    for item in os.listdir(BASE_PATH):
        path = Path(BASE_PATH/item)

        def copy(src, dst):
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            elif src.is_file() and src not in excludes:
                shutil.copy(src, dst)

        if path.is_dir() and path == ROOT_PATH:
            # Root directory special case, copy over contents to `_site/`.
            for nested_item in os.listdir(path):
                nested_path = Path(path/nested_item)
                copy(nested_path, SITE_PATH/nested_path.name)
        elif path.name[0] == "_":
            # Skip other nanojekyll specific items inside the root directory.
            continue
        else:
            # Otherwise, copy item over.
            copy(path, SITE_PATH/path.name)

    # Do a first pass through all files specified in `_config.yml` to parse
    # their YAML headers and populate the `site` dictionary.
    files = []
    for item in config["files"]:
        if type(item) == str:
            # This item must be a file directly inside the root directory.

            header, content = read_file(BASE_PATH/item)
            if not header.get("process_file", True):
                continue # File should be skipped.

            # Add to list of files to process.
            files.append({
                "name": item,
                "path": Path(item).with_suffix(""),
                "header": header,
                "content": content
            })
        else:
            # This item is a directory that potentially contains many files.
            dirname = list(item.keys())[0]
            site[dirname] = [] # Ordered list of specified files.
            unique_dict = {}   # To check that there will be no duplicates.

            def add_file(item):
                name = dirname + "/" + item
                if name in unique_dict:
                    return # Skip duplicates.
                unique_dict[name] = True

                header, content = read_file(BASE_PATH/("_" + name))
                if not header.get("process_file", True):
                    return # File should be skipped.

                # Add to list of files to process.
                files.append({
                    "name": name,
                    "path": Path(name).with_suffix(""),
                    "header": header,
                    "content": content
                })

                # Add header to `site` dictionary for other pages to access
                # through liquid.
                site[dirname].append(header)

            # Check all specified files.
            for nested_item in item[dirname]:
                if nested_item == "*.html" or nested_item == "*.md":
                    # Wildcard special case. Add all files with right suffix.
                    suffix = "." + nested_item.split(".")[-1]
                    for item in os.listdir("_" + dirname):
                        path = Path("_" + dirname)/item
                        if path.suffix == suffix:
                            add_file(path.name)
                else:
                    # Normally, just add the specified file.
                    add_file(nested_item)

    # Make sure that all files have a valid `url` property in their header.
    for file in files:
        if "path" in file["header"]:
            file["header"]["url"] = file["header"]["path"]
        else:
            file["header"]["url"] = str(Path(file["name"]).with_suffix(""))

    # Now do a second pass that actually processes everything.
    if verbose:
        print("* Process files ...")
    for file in files:
        if verbose:
            print("  -", file["name"])
        process_file(state, site, file)

    if verbose:
        print("* Page built!")
    return True

def main():
    if len(sys.argv) <= 1 or len(sys.argv) > 2:
        print(HELP_TEXT)
        sys.exit(len(sys.argv) != 1)

    if sys.argv[1] == "new":
        # Create an empty nanojekyll site.
        success = new_site()
        sys.exit(0 if success else 1)
    if sys.argv[1] == "build":
        # Build the site once.
        success = build_site(verbose=True)
        sys.exit(0 if success else 1)
    elif sys.argv[1] == "serve":
        # Build once explicitly, e.g. to see if there even is a site here.
        if not build_site(verbose=True):
            sys.exit(1)

        # Run a local server and continuously rebuild the site.
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        from functools import partial

        class RebuildHTTPRequestHandle(SimpleHTTPRequestHandler):
            def parse_request(self, *args, **kwargs):
                ret = super().parse_request(*args, **kwargs)
                suffix = Path(self.path).suffix
                if suffix == ".html" or suffix == "":
                    print("nanojekyll rebuild ...", end="")
                    build_site(verbose=False)
                    print(" done.")
                return ret

        print(SERVER_STR)

        handler = partial(RebuildHTTPRequestHandle, directory=SITE_PATH)
        httpd = HTTPServer(("localhost", 8000), handler)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
