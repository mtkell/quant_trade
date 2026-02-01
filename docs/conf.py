# Configuration file for Sphinx documentation builder

project = "Quant Trade"
copyright = "2026, Trading System Team"
author = "Trading System Team"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "analytics_id": "",
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
}
html_static_path = ["_static"]

# Napoleon settings for docstring parsing
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_private_names = False
napoleon_include_special_members = False

# Autodoc settings
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# Suppress warnings
suppress_warnings = ["autodoc.import_error"]
