from fabric.api import *
from fabric.contrib.console import confirm
from fabric.contrib import files
from fabric.colors import red, cyan, green
from sysconfig import *
import yaml
import os
import datetime

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

def get_host():
  host = env.host_string
  import pdb; pdb.set_trace()
  if host[:7] == 'vagrant':
    env.user = 'vagrant'
    env.password = 'vagrant'
    env.host_string = '127.0.0.1'
    host = 'vagrant'
  elif host.find('@') > -1:
    index = host.index('@')
    index = index + 1
    port = host.find(':')
    if port > -1 < len(host):
      host = host[index:port]
    else:
      host = host[index:]
  else:
    key = '%s_pass' % ( host )
    try:
      env.password = os.environ[key]
    except:
      puts(green('No password provided.'))
  return host

def get_settings():
  settings = file('settings.yaml')
  data = yaml.load(settings)
  return data

# Actual flannel
def check_for_wp_cli(host):
  servers = get_servers()
  server = servers[host]['wp-cli']
  
  if server is None:
    sys.exit('You should install wp-cli, it\'s damn handy.')
  else:
    return server

def install_wordpress(version, host):
  v = sudo('wp core version --allow-root')
  if version == v:
    puts(cyan('WordPress is okay!'))
  else:
    try:
      sudo('wp core update --version=%s --force --allow-root')
      # sudo('wp core download --version=%s --allow-root' % (version))
      print('WordPress installed successfully, moving on to configuration.')
    except SystemExit:
      print(red('WordPress failed to update!'))
      sys.exit(1)
  config = get_servers()
  wp_config = config[host]['wp-config']
  try:
    sudo('cp -R %s configurations' % (wp_config))
    # sudo('mv configurations/wp-config.php wp-config.php') # This is failing right now...
    sudo('chmod -R +x configurations')
    sudo('find . -iname \*.php | xargs chmod +x')
    print('WordPress fully configured.')
  except SystemExit:
    print(red('WordPress was not properly configured!'))
    sys.exit(1)

def install_extension(extn, host, environment):
  extension = plugin_or_theme(extn)
  failures = []
  for p in extension:
    v = extension[p]['version'][environment]
    if extension[p]['src'] != False:
      with cd('wp-content/%ss' % (extn)):
        src = extension[p]['src']
        if(not files.exists(p, use_sudo=True)):
          git_clone(extn, p, src)
        try:
          with cd(p):
            sudo('git stash')
            sudo('git fetch origin')
            sudo('git checkout origin/%s' % (v))
        except SystemExit:
          print(red('Failed to update %s' % p))
          failures.append(p)
    else:
      try:
        sudo('wp %s is-installed %s --allow-root' % (extn, p))
        if v != sudo('wp %s get %s --field=version' % (extn, p)):
          puts(cyan('Plugin not installed at correct version, reinstalling'))
          sys.exit(1)
      except SystemExit:
        path = sudo('wp %s path %s --allow-root' % (extn, p))
        index = path.rfind('/')
        path = path[:index]
        sudo('rm -rf %s' % path)
        if extn == 'plugin':
          url = 'http://downloads.wordpress.org/plugin/%s.%s.zip' % (p , v)
        elif extn == 'theme':
          url = 'http://wordpress.org/themes/download/%s.%s.zip' % (p, v)
        try:
          sudo('wp %s install %s --allow-root' % (extn, url))
        except SystemExit:
          puts(red('Failed to update %s' % p))
          failures.append(p)
  return failures

def activate_extensions(extn):
  extension = plugin_or_theme(extn)
  for p in extension:
    if extn == 'theme':
        if sudo('wp option get template --allow-root') == p:
          active = 'active'
    else:
      active = sudo('wp plugin get %s --field=status --allow-root' % (p))
    if str(active) != 'active':
      sudo('wp %s activate %s --allow-root' % (extn, p))

def git_clone(extn, p, src):
  extension = plugin_or_theme(extn)
  vcs = get_vcs()
  if extension[p].has_key('vcs_user'):
    origin = extension[p]['vcs_user']
  else:
    origin = vcs[src]['user']
  url = vcs[src]['url']
  sudo('git clone %s/%s/%s.git' % (url, origin, p))

def plugin_or_theme(extn):
  if extn == 'plugin':
    extension = get_plugins()
  elif extn == 'theme':
    extension = get_themes()
  else:
    sys.exit('Either plugin or theme must be set to True.')
  return extension

def export_settings():
  data = get_settings()
  config = get_config()
  servers = get_servers()
  host = get_host()
  sudoer = servers[host]['sudo_user']
  wp = servers[host]['wordpress']
  wp_cli = check_for_wp_cli(host)
  settings_url = config['Application']['WordPress']['settings']
  nick = servers[host]['nickname']
  if (not files.exists('/tmp/wp-settings')):
    with cd('/tmp/'):
      sudo('git clone %s wp-settings' % settings_url)
  with cd('/tmp/wp-settings'):
    try:
      sudo('git pull origin %s' % nick)
    except:
      puts(red('Could not reach the origin server.'))

  with settings(path=wp_cli, behavior='append', sudo_user=sudoer), cd(wp):
    for d in data:
      sudo('wp option get %s --format=json > /tmp/wp-settings/%s.json --allow-root' % (d, d))
  with settings(sudo_user=sudoer), cd('/tmp/wp-settings'):
    sudo('git config core.fileMode 0')
    if (not files.exists('.git/refs/heads/%s' % nick) ):
      sudo('git checkout -b %s' % nick)
    else:
      sudo('git checkout %s' % nick)
    sudo('git add .')
    sudo('git commit -a -m "Settings update: %s"' % (datetime.date.today()))
    try:
      sudo('git push origin %s' % nick)
    except:
      puts(red('Could not communicate with origin server'))

def update_settings(setting='all'):
  host = get_host()
  servers = get_servers()
  sudoer = servers[host]['sudo_user']
  nick = servers[host]['nickname']
  wp_dir = servers[host]['wordpress']
  if not setting == 'all':       # if we're only updating some settings, parse
    targets = setting.split(',') # the parameter as a tuple
  else:
    targets = get_settings() # if we're updating all the settings, grab them all
  with settings(sudo_user=sudoer), cd('/tmp/wp-settings/'):
    sudo('git checkout %s' % nick)
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

def migrate_settings(target):
  # Migrate this server's settings to another environment
  config = get_config()
  servers = get_servers()
  host = get_host()
  sudoer = servers[host]['sudo_user']
  nick = servers[host]['nickname']
  settings_url = config['Application']['WordPress']['settings']
  puts(cyan('It is recommended you export settings from %s first.' % nick))
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
        sudo('git merge origin/%s %s' % (nick, target))
      except:
        puts(red('The origin server could not be reached.'))
    else:
      sudo('git checkout -b %s origin/%s' % (target, nick))
    try:
      sudo('git push origin %s' % target)
    except SystemExit:
      puts(red('The origin server could not be reached.'))
    sudo('git checkout %s' % nick)

def deploy():
  servers = get_servers()
  host = get_host()
  environment = servers[host]['environment']
  wp_dir = servers[host]['wordpress']
  wp_cli = check_for_wp_cli(host)
  themes = get_themes()
  plugins = get_plugins()
  config = get_config()
  sudoer = servers[host]['sudo_user']
  with settings(path=wp_cli, behavior='append', sudo_user=sudoer):
    try:
      sudo('cp -R %s /tmp/build' % wp_dir)
    except SystemExit:
      sudo('mkdir /tmp/build')
    with cd('/tmp/build'):
      wp_version = config['Application']['WordPress']['version'][environment]
      try:
        install_wordpress(wp_version, host)
      except SystemExit:
        pass
      if plugins is not None:
        plugins_f = install_extension(extn='plugin', host=host, environment=environment)
      if themes is not None:
        themes_f = install_extension(extn='theme', host=host, environment=environment)
  failures = plugins_f + themes_f
  if len(failures) > 0:
    print(red('The following extensions failed to update:'))
    for f in failures:
      puts(red(f))
  else:
    puts('All done, ready to copy!')
    with cd('/tmp/build/'):
      sudo('cp -RfT . %s' % wp_dir)
    # with cd(wp_dir):
    #   toggle_extensions()
    sudo('rm -rf /tmp/build')
    with cd(wp_dir):
      activate_extensions(extn='plugin')
      activate_extensions(extn='theme')