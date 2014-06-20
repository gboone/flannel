from fabric.api import *
from fabric.contrib.console import confirm
from fabric.contrib import files
from fabric.colors import red, cyan, green
from fabtools.vagrant import vagrant
from sysconfig import *
import yaml
import os
import datetime

# Set up Flannel
env.roledefs.update({
  'vagrant': ['127.0.0.1'], 
  'build': [],
  'content' : [],
  'prod' : []
})
# Read from YAML
def get_config():
  config = file('config.yaml')
  data = yaml.load(config)
  return data

def get_servers():
  data = get_config()
  return data['Servers']

def get_plugins():
  data = get_config()
  if data.has_key('Plugins'):
    return data['Plugins']
  else:
    return None

def get_vcs():
  data = get_config()
  return data['VCS']

def get_themes():
  data = get_config()
  return data['Themes']

def get_current_role(host):
  roles = get_roles()
  for r in roles:
    try:
      roles[r]['Hosts'].index(host)
      return r
    except:
      pass

def get_host(servers):
  """ 
  Returns the server information from config.yaml for the 
  hostname specified on the command line.  If the hostnaem 
  is in the format "user@hostname" then separate the 
  hostname first
  """

  host = env.host_string
  if host.find('@') > -1:
    index = host.index('@')
    index = index + 1
    port = host.find(':')
    if port > -1 < len(host):
      host = host[index:port]
    else:
      host = host[index:]
  return servers[host]

@task
def set_hosts():
  role_env = env.roles
  roles = get_roles()
  for role in roles:
    try:
      roles[role]['Hosts'].index(env.host)
      env.roledefs[role].append(env.host)
    except:
      pass
  env.dedupe_hosts = True
  return

def get_settings():
  settings = file('settings.yaml')
  data = yaml.load(settings)
  return data

@task
def hello():
  servers = get_roles()
  env.user = servers['user'] # 'vagrant'
  env.use_ssh_config = True
  run('echo hello')

# Actual flannel
def check_for_wp_cli(host):
  cli = host['wp-cli']
  if cli is None:
    return sys.exit(red('No wp-cli specified in config.yaml. Please add the path to wp for this server.'))
  if not files.exists(cli):
    return sys.exit(red('WP does not exist in the %s directory. Please install wp-cli, it\'s damn handy!' % server))
  return True

def install_wordpress(version, host):
  if version == 'latest':
    try:
      sudo("wp core update --allow-root")
      print(cyan('WordPress installed successfully, moving on to configuration.'))
    except SystemExit:
      return sys.exit(red('WordPress core failed to install. Usually this is a network problem.'))
  else:
    v = sudo("wp core version --allow-root")
    if version == v:
      puts(cyan('WordPress is installed at the correct version, no need to update.'))
    else:
      try:
        sudo("wp core update --version=%s --force --allow-root" % version)
        v = sudo('wp core version --allow-root')
        if v == version:
          print('WordPress installed successfully at version %s, moving on to configuration.' % v)
        else:
          sys.exit(red('Something went wrong. Exepcted WordPress at %s but was %s.' % (version, v)))
      except SystemExit:
        return sys.exit(red('WordPress failed to update!'))
  wp_config = host['wp-config']
  try:
    sudo('cp -R %s configurations' % (wp_config))
    sudo('chmod -R +x configurations')
    sudo('find . -iname \*.php | xargs chmod +x')
    print('WordPress fully configured.')
  except SystemExit:
    return red('WordPress was not properly configured!')

def git_stash_and_fetch(branch):
  sudo('git stash')
  sudo('git fetch origin')
  sudo('git checkout origin/%s' % (branch))

def install_extension(extn, host):
  extension = plugin_or_theme(extn)
  failures = []
  for p in extension:
    if host.has_key('version'):
      v = host['version']
    else:
      v = extension[p]['version']
    if extension[p]['src'] != False:
      with cd('wp-content/%ss' % (extn)):
        src = extension[p]['src']
        if(not files.exists(p, use_sudo=True)):
          puts(cyan("Cloning %s" % p))
          git_clone(extn, p, src)
        try:
          with cd(p):
            git_stash_and_fetch(v)
        except SystemExit:
          print(red('Failed to update %s' % p))
          failures.append(p)
    else:
      install_extension_from_wp(extn, p, v)
  return failures

def activate_extensions(extn):
  extension = plugin_or_theme(extn)
  for p in extension:
    if extn == 'theme':
        if sudo('wp option get template --allow-root') == p:
          active = 'active'
        else:
          active = False
    else:
      active = sudo('wp plugin get %s --field=status --allow-root' % (p))
    if str(active) != 'active':
      sudo('wp %s activate %s --allow-root' % (extn, p))

def install_extension_from_wp(extn, name, version):
  if version == 'master':
    try:
      sudo('wp %s is-installed %s --allow-root' % (extn, name))
      sudo('wp %s update %s --allow-root' % (extn, name))
    except:
      try:
        sudo('wp %s install %s --allow-root' % (extn, name))
        puts(cyan('%s %s installed successfully.'))
      except:
        puts(red('%s %s could not install.' % (extn, name)))
  else:
    try:
      sudo('wp %s is-installed %s --allow-root' % (extn, name))
      if version != sudo('wp %s get %s --field=version --allow-root' % (extn, name)):
        puts(cyan('Plugin not installed at correct version, reinstalling'))
        sys.exit(1)
    except SystemExit:
      path = sudo('wp %s path %s --allow-root' % (extn, name))
      index = path.rfind('/')
      path = path[:index]
      sudo('rm -rf %s' % path)
      if extn == 'plugin':
        url = 'http://downloads.wordpress.org/plugin/%s.%s.zip' % (name, version)
      elif extn == 'theme':
        url = 'http://wordpress.org/themes/download/%s.%s.zip' % (name, version)
      try:
        sudo('wp %s install %s --allow-root' % (extn, url))
      except SystemExit:
        puts(red('Failed to update %s' % p))
        failures.append(p)

def git_clone(extn, p, src):
  extension = plugin_or_theme(extn)
  vcs = get_vcs()
  if extension[p].has_key('vcs_user'):
    origin = extension[p]['vcs_user']
  else:
    origin = vcs[src]['user']
  url = vcs[src]['url']
  puts(cyan("[%s] vcs_user: %s" % (p, origin)))
  sudo('git clone %s/%s/%s.git' % (url, origin, p))

def plugin_or_theme(extn):
  if extn == 'plugin':
    extension = get_plugins()
  elif extn == 'theme':
    extension = get_themes()
  else:
    sys.exit('Either plugin or theme must be set to True.')
  return extension

def export_local_settings():
  with local('cd %s' % host['path-to-vagrant']):
    export_settings()

@task
def export_settings():
  data = get_settings()
  config = get_config()
  host = get_host()
  servers = get_roles()
  sudoer = servers[host]['sudo_user']
  wp = servers[host]['wordpress']
  wp_cli = check_for_wp_cli(role)
  settings_url = config['Application']['WordPress']['settings']
  environment = servers[host]['environment']
  if (not files.exists('/tmp/wp-settings')):
    with cd('/tmp/'):
      sudo('git clone %s wp-settings' % settings_url)
  with cd('/tmp/wp-settings'):
    try:
      sudo('git pull origin %s' % environment)
    except:
      puts(red('Could not reach the origin server.'))

  with settings(path=wp_cli, behavior='append', sudo_user=sudoer), cd(wp):
    for d in data:
      sudo('wp option get %s --format=json > /tmp/wp-settings/%s.json --allow-root' % (d, d))
  with settings(sudo_user=sudoer), cd('/tmp/wp-settings'):
    sudo('git config core.fileMode 0')
    if (not files.exists('.git/refs/heads/%s' % environment) ):
      sudo('git checkout -b %s' % environment)
    else:
      sudo('git checkout %s' % environment)
    sudo('git add .')
    sudo('git commit -a -m "Settings update: %s"' % (datetime.date.today()))
    try:
      sudo('git push origin %s' % environment)
    except:
      puts(red('Could not communicate with origin server'))

@task
def update_settings(setting='all'):
  host = get_host()
  servers = get_roles()
  sudoer = servers[host]['sudo_user']
  environment = servers[host]['environment']
  wp_dir = servers[host]['wordpress']
  if not setting == 'all':       # if we're only updating some settings, parse
    targets = setting.split(',') # the parameter as a tuple
  else:
    targets = get_settings() # if we're updating all the settings, grab them all
  with settings(sudo_user=sudoer), cd('/tmp/wp-settings/'):
    sudo('git checkout %s' % environment)
  s_counter = 0
  updated = []
  for t in targets:
    name = '/tmp/wp-settings/%s.json' % t
    if files.exists(name):
      with cd(wp_dir):
        current = sudo('wp option get %s --format=json --allow-root' % t)
        expected = sudo('cat %s' % name)
        if current == expected:
          puts(green('%s did not change!') % (t))
        else:
          sudo('wp option update %s --format=json --allow-root < %s' % (t, name))
          puts(cyan('%s was %s and is now %s' % (t, current, expected)))
          s_counter += 1
          updated.append(t)
    else:
      puts(red('%s cannot be updated with this method.' % t))
      puts(red('Either the JSON does not exist, or it is an invalid option.'))
  if s_counter > 0:
    puts(cyan('%i options updated successfully.' % s_counter))
    puts('Options updated:')
    for u in updated:
      puts(cyan(u))
  else:
    puts(cyan('No options updated!'))

@task
def migrate_settings(target):
  # Migrate this server's settings to another environment
  config = get_config()
  servers = get_roles()
  host = get_host()
  sudoer = servers[host]['sudo_user']
  environment = servers[host]['environment']
  settings_url = config['Application']['WordPress']['settings']
  puts(cyan('It is recommended you export settings from %s first.' % environment))
  if not target:
    sys.exit(red('How am I supposed to migrate if I don\'t know to go?'))
  with settings(sudo_user=sudoer), cd('/tmp/wp-settings'):
    try:
      sudo('git fetch origin')
    except:
      puts(red('The origin server could not be reached.'))
    if files.exists('.git/refs/heads/%s' % target):
      sudo('git checkout %s' %  target)
      try:
        sudo('git merge origin/%s %s' % (environment, target))
      except:
        puts(red('The origin server could not be reached.'))
    else:
      sudo('git checkout -b %s origin/%s' % (target, environment))
    try:
      sudo('git push origin %s' % target)
    except SystemExit:
      puts(red('The origin server could not be reached.'))
    sudo('git checkout %s' % environment)

@task
def deploy(wp_version='', plugin_override=False, theme_override=False):
  servers = get_servers()
  host = get_host(servers)
  wp_dir = host['wordpress']
  env.user = host['user']
  env.use_ssh_config = True
  wp_cli = check_for_wp_cli(host)
  themes = get_themes()
  plugins = get_plugins()
  config = get_config()
  sudoer = host['sudo_user']
  failures = []
  with settings(path=wp_cli, behavior='append', sudo_user=sudoer):
    try:
      sudo('cp -R %s /mnt/local/tmp/build/wordpress' % wp_dir)
    except SystemExit:
      sudo('mkdir -p /mnt/local/tmp/build')
      sudo('cp -R %s /mnt/local/tmp/build/wordpress' % wp_dir)
    with cd('/mnt/local/tmp/build/wordpress'):
      if wp_version != 'latest':
        wp_version = config['Application']['WordPress']['version']  
      install_wordpress(wp_version, host)
      if plugins is not None:
        plugins_f = install_extension(extn='plugin', host=host)
      if themes is not None:
        themes_f = install_extension(extn='theme', host=host)
  if len(plugins_f) > 0:
    failures.append(plugins_f)
  if len(themes_f) > 0:
    failures.append(themes_f)
  if len(failures) > 0:
    sys.exit(red('Deployment encountered the following problems:'))
    for f in failures:
      puts(red(f))
  else:
    puts('All done, ready to copy!')
    with cd('/mnt/local/tmp/build/wordpress'):
      sudo('cp -RfT . %s' % wp_dir)
    # with cd(wp_dir):
    #   toggle_extensions()
    
    #sudo('rm -rf /mnt/local/tmp/build')
    with cd(wp_dir):
      activate_extensions(extn='plugin')
      activate_extensions(extn='theme')

@task
def build(wp_version=''):
  deploy(wp_version='')