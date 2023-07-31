import os, shutil, yaml, sys, time
from pathlib import Path
from liquid import Liquid

BASE_PATH     = Path.cwd()
CONFIG_PATH   = BASE_PATH/'_config.yml'
SITE_PATH     = BASE_PATH/"_site"
INCLUDES_PATH = BASE_PATH/"_includes"
LAYOUTS_PATH  = BASE_PATH/"_layouts"
CONTENT_PATH  = BASE_PATH/"_content"

def process_html(state, site_path, path, is_base_file, verbose):
    if verbose:
        if is_base_file:
            print("  - ", path)
        else:
            print("  - ", path)

    # Read in file.
    f = open(path)
    content = f.read()
    f.close()

    # Extract and parse YAML header surrounded by "---".
    delim = "---"
    a = content.find(delim)
    b = content.find(delim, a + len(delim))
    header = yaml.safe_load(content[a + len(delim):b])
    content = content[b + len(delim):] # File content without the YAML header.

    # Build liquid parameter dict.
    liquid_params = {
        "site": state["config"],
    }
    liquid_params["site"]["time"] = time.time()
    liquid_params["page"] = state["config"] if is_base_file else header
    for key, value in state["includes"].items():
        liquid_params[key] = value
    if is_base_file:
        liquid_params['site']['content'] = state['content']

    # Process main content of file.
    if not content.isspace():
        liq = Liquid(content, from_file=False)
        content = liq.render(liquid_params, mode="jekyll")
        liquid_params["content"] = content

        # Find the right layout file.
        if "layout" not in header:
            raise Exception(f"Error: Header of \"{path}\" did not contain \"layout\" tag.")
        liq = Liquid(state["layouts"][header["layout"]])
        output = liq.render(liquid_params, mode="jekyll")

        # Assemble the output path.
        outpath = None
        if is_base_file:
            outpath = site_path/path
        else:
            # Get requested path from file.
            if "url" not in header:
                raise Exception(f"Error: Header of \"{path}\" did not contain \"url\" tag.")
            outpath = site_path/header["url"]
            os.makedirs(outpath, exist_ok=True)
            outpath = outpath/"index.html"

        # And finally write file to the right place.
        with open(outpath, "w") as f:
            f.write(output)

    return header

def build_site(verbose):
    os.makedirs(SITE_PATH,     exist_ok=True)
    os.makedirs(INCLUDES_PATH, exist_ok=True)
    os.makedirs(LAYOUTS_PATH,  exist_ok=True)
    os.makedirs(CONTENT_PATH,  exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        print("No nanojekyll site found. Create an empty config file.")
        open(CONFIG_PATH, 'a').close()

    state = {}

    # Parse `_config.yml` file from disk.
    with open(CONFIG_PATH) as f:
        config = f.read()
        config = yaml.safe_load(config)
        state["config"] = config

    # Get all paths from `_includes` and `_layouts` for later use.
    state["includes"] = {}
    for item in os.listdir(INCLUDES_PATH):
        path = Path(INCLUDES_PATH/item)
        state["includes"][path.stem] = { 'html': str(path) }

    state["layouts"] = {}
    for item in os.listdir(LAYOUTS_PATH):
        path = Path(LAYOUTS_PATH/item)
        state["layouts"][path.stem] = str(path)

    # Copy over everything (non-nanojekyll related) to the `_site` output directory.
    for item in os.listdir(BASE_PATH):
        path = Path(BASE_PATH/item)
        if path.name[0] == "_":
            continue

        if path.is_dir():
            shutil.copytree(path, SITE_PATH/path.name, dirs_exist_ok=True)
        elif path.is_file():
            shutil.copy(path, SITE_PATH/path.name)

    # Process content files.
    if verbose:
        print("* Process content files ...")
    content = {}
    for p in Path(CONTENT_PATH).rglob("*"):
        if not p.is_file() or p.suffix != ".html": # Only look at files.
            continue

        # Only keep parts of the path between `_content` and the filename.
        parts = p.parts
        idx = 0
        for part in parts:
            if part == "_content":
                break
            idx += 1
        middle = parts[idx + 1 : -1]
        filename = parts[-1]

        # Insert middle parts into the `state` dict.
        cur = content
        for i, part in enumerate(middle):
            if part not in cur:
                if i < len(middle) - 1:
                    # Intermediate directories are going to be to keys.
                    cur[part] = {}
                else:
                    # The last directory is going to be a list.
                    cur[part] = []
            cur = cur[part]

        # Process the actual file.
        header = process_html(state, SITE_PATH, p, is_base_file=False, verbose=verbose)

        # Insert at the right position based on specified index.
        if "idx" not in header:
            raise Exception(f"Error: Header of \"{p}\" did not contain \"idx\" tag.")
        idx = 0
        for idx in range(len(cur)-1, -1, -1):
            if cur[idx]["idx"] > header["idx"]:
                idx += 1
                break
        cur.insert(idx, header)


    state["content"] = content

    # Process main files specified in config, e.g. `index.html` in the root.
    if "base_files" in state["config"]:
        if verbose:
            print("* Process base files ...")
        for p in state["config"]["base_files"]:
            process_html(state, SITE_PATH, p, is_base_file=True, verbose=verbose)

    if verbose:
        print("* Page built!")
    return True

help_text = """\
usage: nanojekyll.py [command]

A minimal static site generator. Certified free from Ruby.

commands:
    build    Build the site once.
    serve    Run a local server and continuously rebuild the site.
"""

def main():
    if len(sys.argv) <= 1:
        print(help_text)
        sys.exit(0)

    if len(sys.argv) > 2:
        print(help_text)
        sys.exit(1)

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
                build_site(verbose=False)
                return super().parse_request(*args, **kwargs)

        print("Running local server at http://localhost:8000 ... press ctrl-c to stop.")

        handler = partial(RebuildHTTPRequestHandle, directory=SITE_PATH)
        httpd = HTTPServer(('localhost', 8000), handler)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
