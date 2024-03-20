"""Configure QRDM Sphinx Documentation."""

from importlib import metadata

# -- Project information -----------------------------------------------------

project = "QR Data Manager"
copyright = "Massachusetts Institute of Technology"
author = "MIT Lincoln Laboratory"
# The full version, including alpha/beta/rc tags.
release = metadata.version("qrdm")
# The short X.Y version.
version = release.rsplit(".", 1)[0]

# -- General configuration ---------------------------------------------------

# Numpydoc is better in HTML, but doesn't look great on PDF output
extensions = [
    "sphinx.ext.autosummary",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.githubpages",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "myst_parser",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# The reST default role (used for this markup: `text`) to use for all
# documents.
default_role = "literal"

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "default"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.

html_theme = "furo"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_theme_options = {
    "dark_logo": "LL_Logo_alone_white.png",
    "light_logo": "LL_Logo_alone_blue.png",
    "top_of_page_button": None,
    # GitHub icon embedded as SVG
    # See https://pradyunsg.me/furo/customisation/footer/#using-embedded-svgs
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/mit-ll/qrdm",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        }
    ],
}

# -- Extension configuration -------------------------------------------------
autosummary_generate = True
napoleon_google_docstring = False
myst_enable_extensions = ["colon_fence", "smartquotes", "deflist"]
doctest_global_setup = "import qrdm\n"
