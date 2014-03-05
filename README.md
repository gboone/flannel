# Flannel: Automated Deployments in Fabric

This is a fabric-based automated deployment tool using a YAML file to store information about your configuration. It is very much a work in progress.

TOC:
1. Requirements
2. Your YAML File
3. Running the deployment

Requirements
------------

Flannel requires the pyyaml package and fabric. Installing them is as easy as:

```python
pip install -r requirements.txt
```

On the server end, fabric relies on a tool called [wp-cli](https://github.com/wp-cli/wp-cli) to administer WordPress. If you haven't installed it on your system yet, you definitely should. It's way cool. Deployments will fail and instruct you to install it if it's missing.

The YAML File
-------------
The included YAML file is a enough to get you started. There are five main sections:

- Servers: with fields for address, user, application directories (so far just WordPress), and the path to wp-cli
- VCS: for any version control systems you're using. Fields here include url, username, and type (git, svn, hg, etc.)
- Application: The only application supported by flannel so far is WordPress, and the only field so far is version. There may be others as Flannel develops.
- Themes: names of themes that should be loaded, which version they should be installed at, which VCS to find them in, and whether they are active or inactive. You should have multiple themes here if you use a child theme.
- Plugins: same as themes but for plugins.

If you have a fairly complicated website, this file can get long.

Running the deployment
----------------------

Simple: `fab deploy`

You can see what's going on behind the scenes in the code, but here's the gist:

1. Grabs some information from the yaml file
2. Checks for WP-CLI
3. Checks the WordPress version and upgrades if it is not the same as the config.yaml

Right now it will try to run deploy() on each server defined in your YAML.