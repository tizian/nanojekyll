import markdown, os, shutil, sys, time, yaml
from pathlib import Path
from liquid import Liquid

BASE_PATH     = Path.cwd()
CONFIG_PATH   = BASE_PATH/'_config.yml'
SITE_PATH     = BASE_PATH/"_site"
INCLUDES_PATH = BASE_PATH/"_includes"
LAYOUTS_PATH  = BASE_PATH/"_layouts"
CONTENT_PATH  = BASE_PATH/"_content"

HELP_TEXT = """\
usage: nanojekyll.py [command]

A minimal static site generator. Certified free from Ruby.

commands:
    build    Build the site once.
    serve    Run a local server and continuously rebuild the site.
"""

def read_file(path):
    if path.suffix != ".html" and path.suffix != ".md":
        raise Exception("nanojekyll can only process .html or .md files.")

    # Read in file.
    with open(path) as f:
        content = f.read()

    # Extract and parse YAML header surrounded by "---".
    delim = "---"
    a = content.find(delim)
    b = content.find(delim, a + len(delim))
    header = yaml.safe_load(content[a + len(delim):b])

    # The remainder is the main content.
    content = content[b + len(delim):]

    # If necessary, convert markdown into html.
    if path.suffix == ".md":
        content = markdown.markdown(content, extensions=['extra'])
        print(content)

    return header, content

def process_file(state, site, file):
    if file["content"].isspace():
        return # Skip files that only have a header.

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
    outpath = state["site_path"]/file["path"]
    if "path" in file["header"]:
        # Override specified in file header.
        outpath = state["site_path"]/file["header"]["path"]
        os.makedirs(outpath, exist_ok=True)
        outpath = outpath/"index"
    outpath = outpath.with_suffix(".html")

    # And finally write file to the right place.
    with open(outpath, "w") as f:
        f.write(output)

def build_site(verbose):
    os.makedirs(SITE_PATH,     exist_ok=True)
    os.makedirs(INCLUDES_PATH, exist_ok=True)
    os.makedirs(LAYOUTS_PATH,  exist_ok=True)
    os.makedirs(CONTENT_PATH,  exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        print("No nanojekyll site found. Create an empty config file.")
        open(CONFIG_PATH, 'a').close()

    site  = {}  # Dict that keeps parameters accessible through liquid.
    state = {}  # Dict for keeping internal data such as includes/layouts.
    state["base_path"]     = BASE_PATH
    state["site_path"]     = SITE_PATH
    state["includes_path"] = INCLUDES_PATH
    state["layouts_path"]  = LAYOUTS_PATH
    state["content_path"]  = CONTENT_PATH

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

    # Copy over everything to the `_site` output directory.
    for item in os.listdir(BASE_PATH):
        path = Path(BASE_PATH/item)
        if path.name[0] == "_":
            # Skip nanojekyll specific items inside the root directory.
            continue

        if path.is_dir():
            shutil.copytree(path, SITE_PATH/path.name, dirs_exist_ok=True)
        elif path.is_file():
            shutil.copy(path, SITE_PATH/path.name)

    # Do a first pass through all files specified in `_config.yml` to parse
    # their YAML headers and populate the `site` dictionary.
    files = []
    for item in config["files"]:
        if type(item) == str:
            # This item must be a file directly inside the root directory.

            header, content = read_file(BASE_PATH/item)
            if header.get("hidden", False):
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
                if header.get("hidden", False):
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

    if sys.argv[1] == "build":
        # Build the site once.
        success = build_site(verbose=True)
        sys.exit(0 if success else 1)
    elif sys.argv[1] == "serve":
        # Run a local server and continuously rebuild the site.
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        from functools import partial

        class RebuildHTTPRequestHandle(SimpleHTTPRequestHandler):
            def parse_request(self, *args, **kwargs):
                ret = super().parse_request(*args, **kwargs)
                suffix = Path(self.path).suffix
                if suffix == ".html" or suffix == "":
                    print("nanojekyll rebuild ...", end='')
                    build_site(verbose=False)
                    print(" done.")
                return ret

        print("Running local server at http://localhost:8000 ... press ctrl-c to stop.")

        handler = partial(RebuildHTTPRequestHandle, directory=SITE_PATH)
        httpd = HTTPServer(('localhost', 8000), handler)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
