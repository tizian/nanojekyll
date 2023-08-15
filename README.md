# nanojekyll

A minimal static site generator used to build my [personal website](https://tizianzeltner.com/). It's design is strongly influenced by [Jekyll](https://jekyllrb.com/) that I used for many years, but there are no plans for feature parity or general compatibility.

This project has grown out of increasing frustrations with maintaining a working Ruby developer environment only to run Jekyll. In contrast, *nanojekyll* is implemented as a simple Python package and is *certified free from Ruby*.

## Documentation

### Installation

```
git clone git@github.com:tizian/nanojekyll.git
cd nanojekyll
pip3 install .
```
This also automatically installs the non-standard Python dependencies [liquidpy](https://pypi.org/project/liquidpy/), [Python-Markdown](https://pypi.org/project/Markdown/), and [PyYAML](https://pypi.org/project/PyYAML/).

### Command line interface

Create a new site:
```
mkdir my_site
cd my_site
nanojekyll build
```
This generates the following directory structure that will be explained below.
```
my_site/
├─ _config.yml
├─ _includes/
├─ _layouts/
├─ _root_/
├─ _site/
├─ index.html
```

Build the site:
```
nanojekyll build
```

Continuously (re)build the site and serve it locally:
```
nanojekyll serve
```
Then navigate to `http://localhost:8000`. Refreshing the browser will automatically re-build the site in the background.

### Functionality

* Everything inside the root directory (e.g. `my_site/` in the example above) will get copied over into the `_site/` directory that will contain the generated site ready for publishing. The same is true for contents of the special `_root/` directory. This is useful to avoid cluttering the actual root directory with various files or folders.

<br>

* Files listed under `files` in `_config.yml` will be processed by nanojekyll. By default, this is *at least* `index.html`, but others (either in `.html` or `.md` format) can be added as well.
    * `index.html` will generate a corresponding file `_site/index.html`.
    * Any other file will generate an `index.html` file in a subdirectory with the corresponding name, i.e. `test.md` -> `_site/test/index.html`.
    * For markdown (`.md`) files, their content will be converted to HTML at this point.

<br>

* *Processing* here means that the [*Liquid*](https://shopify.github.io/liquid/basics/introduction/) template language can be used to generate the final HTML output.
    * Global properties in `_config.yml` (such as the default `title`) can be accessed via Liquid's `{{ site.<name of property> }}` syntax.
    
        For example, when specifying `title: "nanojekyll site"`, the string `{{ site.title }}` will be replaced by `nanojekyll site` in the final HTML.

        By default, the property `site.time` is always available and returns the UNIX timestamp when building the site.

    * Each file can also have an individual YML header in the style of `_config.yml`, separated by "`---`" before and after the header. For example:

        ```
        ---
        title: "Test page"
        ---

        Actual file content.
        ```
        
        Properties from that header can similarly be accessed in Liquid using `{{ page.<name of property> }}`. 

        By default, the property `page.url` is always available and returns the URL relative to the base URL of the site.

    * Complete HTML snippets can be included via `{% include <name of snippet>.html %}`, provided a corresponding file is found in the `_includes/` directory.

    * Page headers can specify a property `layout: <name of layout>`, which means nanojekyll will look for a HTML template in `_layouts/<name_of_layout>.html`, and the file content below the header will be substituted into the template at a location specified by `{{ content }}`.

    * The output path of the file (e.g. `_site/test/index.html` in the example above) can be overwritten by specifying a `path: <path to output>` property in the header. The generated page will then be located at `_site/<path to output>/index.html` instead.

<br>

* The `files` property in `_config.yml` can additionally specify a number of subdirectories with their own pages inside. E.g.
    ```
    files:
        - "index.html"

        - blog_posts:
            - "first_post.html"
            - "second_post.md"
    ```

    In this case, nanojekyll expects these files to be found inside a root subdirectory called `_blog_posts/`. Such files will be processed into outputs `_site/blog_posts/first_post/index.html` and `_site/blog_posts/second_post/index.html` (unless this is overwritten via a `path` property).

    The main advantage of these subdirectories is that they can be accessed globally from any page via the `site.blog_posts` property. For instance, one can loop over all posts and display their titles as a list of links:

    ```
    <ul>
    {% for post in site.blog_posts %}
    <li><a href="post.url">{{ page.title }}</a></li>
    {% endfor %}
    </ul>
    ```

    Alternatively, a wildcard "`*`" can be used to indicate that all such files (`.html` or `.md`) inside the directory should be added:

    ```
    files:
        - "index.html"

        - blog_posts:
            - "*.html"
            - "*.md"
    ```

    This will however add them in an unspecified ordering to the `site.blog_posts` list.

<br>

* Creation of an output page can be skipped by specifying `create_page: False` in a file header. Processing of a file can be skipped entirely with `process_file: False`, in which case the page also won't be accessible via properties such as `site.blog_posts`.
