# Flannel: Automated Deployments in Fabric

This is a fabric-based automated deployment tool using a YAML file to store information about your configuration. It is very much a work in progress.

TOC:

1. [Requirements](#requirements)
2. [The YAML File](#the-yaml-file)
3. [The Fabric File](#the-fabric-file)
3. [Running the deployment](#running-the-deployment)

Requirements
------------

_Flannel_ requires python 2.7, pyyaml, and fabric.

1. Clone this repo (or your fork)
2. `mkvirtualenv flannel`
3. `pip install -r requirements.txt`

We recommend you do that inside a virtual environment. On the server end, fabric relies on a tool called [wp-cli](https://github.com/wp-cli/wp-cli) to administer WordPress. If you haven't installed it on your system yet, you definitely should. It's way cool. Also, make sure it is installed so it can be run as `wp`, not `wp.phar` or some other way. If it is missing, deployments will fail and instruct you to install it.

The YAML File
-------------
The included YAML file is a enough to get you started. There are five main sections:

- Servers: each key in this section should correspond to the address for your server. Inside each server, you need to supply a few values:
    - user: the name of the user you log in to the server as
    - environment: a name for the version-set you will apply to this server
    - sudo_user: the name of the user commands should run as
    - wordpress: the fully qualified path to your wordpress install, eg., `/var/www/`
    - wp-config: the fully qualified path to the directory containing a wp-config.php file that already exists on your server, eg., `/var/www/wp-config`, you can also put any other configuration files in here, these will go into a directory called `configurations` relative to the root of your WordPress install
    - wp-cli: the fully qualified path to wp-cli, must be set or the script will fail. Find it with `which wp`
    - port: (optional) the port used to ssh into the server (if not 22)

Example server entry:

```yaml
Servers:
    1.1.1.1:
        environment: env-name
        wordpress: /var/www
        wp-config: /home/gboone/wp-config
        user: gboone
        sudo_user: apache
        wp-cli: /usr/bin/wp
        port: 2202
```

- VCS: for any version control systems you're using. Fields here include url, username. Some day we will support other vcs's but for now only git repos may be used.

Example VCS entry:

```yaml
VCS:
    GitHub:
        url: https://github.com
        user: gboone
```

- Application: The only application supported by _Flannel_ so far is WordPress, and the only field so far is version. Specify environment versions under the version key.

```yaml
Application:
    WordPress:
        version:
            env-name: 3.8.1
```

- Themes: names of themes that should be loaded as they are named by WordPress. For example the Twenty Fourteen theme is loaded with 'twentyfourteen'. Keys for each theme include:
    - version: this can either be a numeric version for themes in the WordPress theme repository or a branch if loading from a VCS 
    - src: which VCS to find them in, set this to false if loading from the WP theme repository
    - state: if set to active, will mark this as the active theme for your site. You should have multiple themes here if you use a child theme. If more than one theme is set to active, the last one _Flannel_ iterates through will be loaded.
    - vcs_user: if a different user than the default for that VCS owns this theme, you can override it with this key

Example theme entry:
```yaml
Themes:
    twentyfourteen:
        src: False
        version:
            env-name: 1.0
        state: active
```

- Plugins: same as themes but for plugins. You can have as many as you want set to active.

If you have a fairly complicated website, this file can get long.

The fabric file
---------------
Better known as `fabfile.py`, the fabric file contains methods that make the final deploy() method go. It is broken into 3 sections: 1. Read from YAML, 2. Set servers dynamically, and 3. `Actual flannel`. The last section contains the methods that communicate with your server.

Running the deployment
----------------------

Simple: 
1. `workon flannel`
2. `fab deploy`

You can see what's going on behind the scenes in the code, but here's the gist:

1. Grabs some information from the yaml file
2. Checks for WP-CLI
2. Copies your existing install to /tmp/build  (if it exists, otherwise it creates /tmp/build)
3. Copies your wp-config held at your configuation directory
3. Checks the WordPress version and upgrades if it is not the same as the config.yaml (Warning: it uses `wp core update` with `--force` and will go backward if your version is ahead.)
4. Checks all your plugins and upgrades if they are not at the correct version
5. Checks all your themes and upgrades if they are not at the correct version
6. If everything is successful, it will copy back to your WordPress directory, delete /tmp/build, and activate all plugins that are supposed to be active. IF it fails it will leave /tmp/build in place in case you want to inspect things. Definitely delete this when you're done or it might screw up your next deployment.

By default it will try to run deploy() on each server defined in your YAML. If you want to specify a server, use the standard `fab -H <server>` to do that. Use the server names from config.yaml. If there are any problems connecting to vcs  servers, installing plugins, etc. it will fail and leave your current build untouched.

Add a vagrant box as a server
----------------------------

_Flannel_ has a few tasks available to vagrant boxes. They are: `deploy`, `export_settings`, `update_settings`, and `migrate_settings`. _Flannel_ will use the `~/.ssh/config` file to parse out how to connect to your vagrant box. Just make sure you have a Server in `config.yaml` set to whatever `vagrant ssh-config` tells you is Host and then set all the other appropriate parameters. Fabric and _Flannel_ takes care of the rest.

Example:

Given the following ssh-config:

```bash
$ vagrant ssh-config
Host default
  HostName 127.0.0.1
  User vagrant
  Port 2222
  UserKnownHostsFile /dev/null
  StrictHostKeyChecking no
  PasswordAuthentication no
  IdentityFile "/path/to/.vagrant.d/insecure_private_key"
  IdentitiesOnly yes
  LogLevel FATAL
```

Make an entry in config.yaml like this:

```yaml
Servers:
  default:
    environment: dev
    wordpress: /pah/to/wordpress
    user: vagrant
    wp-config: /var/www/config
    sudo_user: root
    wp-cli: /path/to/wp
```