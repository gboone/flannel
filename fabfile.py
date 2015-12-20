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
env.use_ssh_config = True
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
    print data['Plugins']
    return data['Plugins']
  else:
    print 'I got nothing!'
    return None

def get_vcs():
  data = get_config()
  return data['VCS']

def get_themes():
  data = get_config()
  return data['Themes']

def get_s3():
  data = get_config()
  return data['s3']

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
  import pdb; pdb.set_trace()
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
    # Update wordpress to the latest version
    try:
      sudo("wp core update --allow-root")
      print(green('WordPress installed successfully, moving on to configuration.'))
    except SystemExit:
      return sys.exit(red('WordPress core failed to install. Usually this is a network problem.'))
  else:
    if is_correct_wordpress_version(version):
      puts(green('WordPress is installed at the correct version, no need to update.'))
    else:
      # Not the correct version, so upgrade/downgrade to the correct version
      try:
        sudo("wp core update --version=%s --force --allow-root" % version)
        # recheck version now, since we have no way of knowing if the update ended successfully
        if is_correct_wordpress_version(version):
          print(green('WordPress installed successfully at version %s, moving on to configuration.' % version))
        else:
          sys.exit(red('Something went wrong. Exepcted WordPress at %s but did not upgrade successfully.' % version))
      except SystemExit:
        return sys.exit(red('WordPress failed to update!'))

  # Move the configurations into the new wordpress installation
  wp_config = host['wp-config']
  try:
    sudo('cp -R %s configurations' % (wp_config))
    sudo('chmod -R +x configurations')
    sudo('find . -iname \*.php | xargs chmod +x')
    print(green('WordPress fully configured.'))
  except SystemExit:
    return red('WordPress was not properly configured!')

def is_correct_wordpress_version(version):
  return version == sudo("wp core version --allow-root")

def install_all_extensions(extensions_list, type, host):
  failures = []
  for extension, config in extensions_list.iteritems():
    # If a specific version is specified in config, use that. Otherwise
    # default to the version in the host (typically master)
    if 'version' in config:
      version = config['version']
    else:
      version = host['version']
    src = config['src']

    if 'vcs_user' in config:
      user = config['vcs_user']
    else:
      user = ''

    try:
      install_extension(extension, type, src, version, user)
      activate_extension(extension, type)
    except SystemExit:
      print(red('Failed to update %s' % extension))
      failures.append(extension)
  return failures

def install_extension(name, type, src, version, user=''):
    if src == 'wordpress':
      install_extension_from_wp(type, name, version)
    else:
      vcs = get_vcs()
      url = vcs[src]['url']
      if user != '':
        vcs_user = user
      else:
        vcs_user = vcs[src]['user']
      install_extension_from_repo(name, type, url, version, vcs_user)
    puts(green("Successfully installed %s %s" % (type, name)))


def install_extension_from_repo(name, type, url, version, vcs_user):
  with cd('wp-content/%ss' % (type)):
    if(not files.exists(name, use_sudo=True)):
      puts(cyan("Cloning %s" % name))
      git_clone(type, name, url, vcs_user)

    with cd(name):
      git_stash_and_fetch(version)

def git_clone(type, repo_name, url, user):
  puts(cyan("[%s] vcs_user: %s" % (repo_name, user)))
  sudo('git clone %s/%s/%s.git' % (url, user, repo_name))

def git_stash_and_fetch(branch):
  sudo('git stash')
  sudo('git fetch origin')
  sudo('git checkout origin/%s' % (branch))

def install_extension_from_wp(type, name, version):
  if version == 'master':
    if is_extension_installed(type, name):
      sudo('wp %s update %s --allow-root' % (type, name))
    else:
      install_cmd = sudo('wp %s install %s --allow-root' % (type, name))
      if install_cmd.return_code == 0:
        puts(green('%s %s installed successfully.'))
      else:
        puts(red('%s %s could not install.' % (type, name)))
  else:
    if not is_extension_installed(type, name) or version != get_extension_version(type, name):
      puts(cyan('Plugin not installed or installed at the incorrect version, reinstalling'))
      uninstall_extension(type, name)
      if type == 'plugin':
        url = 'http://downloads.wordpress.org/plugin/%s.%s.zip' % (name, version)
      elif type == 'theme':
        url = 'http://wordpress.org/themes/download/%s.%s.zip' % (name, version)

      try:
        install_cmd = sudo('wp %s install %s --allow-root' % (type, url))
        if install_cmd.return_code == 0:
          puts(green('%s %s installed successfully.' % (type, name)))
        else:
          puts(red('Failed to update %s' % name))
      except SystemExit:
        puts(red('Failed to update %s' % name))

def is_extension_installed(type, name):
  try:
    result = sudo('wp %s is-installed %s --allow-root' % (type, name))
    return result.return_code == 0
  except SystemExit:
    return False

def get_extension_version(type, name):
  return sudo('wp %s get %s --field=version --allow-root' % (type, name))

def get_extension_path(type, name):
  try:
    path = sudo('wp %s path %s --allow-root' % (type, name))
    index = path.rfind('/')
    path = path[:index]
    return path
  except SystemExit:
    return None

def uninstall_extension(type, name):
  path = get_extension_path(type, name)
  if path is not None:
    sudo('rm -rf %s' % path)

# def activate_all_extensions(type):
#   extensions_list = get_plugin_or_theme_list(type)
#   for extension in extensions_list:
#     activate_extension(extension, type)

def activate_extension(name, type):
  if not is_extension_active(name, type):
    sudo('wp %s activate %s --allow-root' % (type, name))

def is_extension_active(name, type):
  if type == 'theme':
    return sudo('wp option get template --allow-root') == name
  else:
    return sudo('wp plugin get %s --field=status --allow-root' % (name)) == 'active'

# def get_plugin_or_theme_list(extn):
#   if extn == 'plugin':
#     extensions_list = get_plugins()
#   elif extn == 'theme':
#     extensions_list = get_themes()
#   else:
#     sys.exit('Either plugin or theme must be set to True.')
#   return extensions_list

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
def deploy_from_config(wp_version='', plugin_override=False, theme_override=False):
  servers = get_servers()
  host = get_host(servers)
  wp_dir = host['wordpress']
  tmp_write_dir = host['tmp_write_dir'] if 'tmp_write_dir' in host else '/tmp/build'
  env.user = host['user']
  env.use_ssh_config = True
  wp_cli = check_for_wp_cli(host)
  themes = get_themes()
  plugins = get_plugins()
  config = get_config()
  sudoer = host['sudo_user']
  failures = []
  with settings(path=wp_cli, behavior='append', sudo_user=sudoer):
    # create the directory in case it doesn't exist
    sudo('mkdir -p %s' % tmp_write_dir)

    # copy the contents to a temporary working directory
    sudo('rsync -ra --exclude=wordpress/f %s %s' % (wp_dir, tmp_write_dir))
    with cd('%s/wordpress' % tmp_write_dir):
      if wp_version != 'latest':
        wp_version = config['Application']['WordPress']['version']
      install_wordpress(wp_version, host)
      if plugins is not None:
        plugins_f = install_all_extensions(plugins, 'plugin', host)
      if themes is not None:
        themes_f = install_all_extensions(themes, 'theme', host)
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
    with cd('%s/wordpress' % tmp_write_dir):
      #sudo('cp -RfT . %s' % wp_dir)
      sudo('rsync -ra . %s' % wp_dir)
    # with cd(wp_dir):
    #   toggle_extensions()

    sudo('rm -rf %s' % tmp_write_dir)
    # with cd(wp_dir):
    #   activate_all_extensions(type='plugin')
    #   activate_all_extensions(type='theme')

@task
def deploy_extension(extension_name, type, src, version, owner='', state='active'):
  servers = get_servers()
  host = get_host(servers)
  wp_dir = host['wordpress']
  tmp_write_dir = host['tmp_write_dir'] if 'tmp_write_dir' in host else '/tmp/build'
  env.user = host['user']
  env.use_ssh_config = True
  wp_cli = check_for_wp_cli(host)
  sudoer = host['sudo_user']
  with settings(path=wp_cli, behavior='append', sudo_user=sudoer):
    with cd(wp_dir):
      try:
        install_extension(extension_name, type, src, version, owner)
        activate_extension(extension_name, type)
      except SystemExit:
        sys.exit(red('Failed to install %s:' % extension_name))

@task
def deploy_wordpress(version):
  servers = get_servers()
  host = get_host(servers)
  wp_dir = host['wordpress']
  env.user = host['user']
  env.use_ssh_config = True
  sudoer = host['sudo_user']
  wp_cli = check_for_wp_cli(host)

  with settings(path=wp_cli, behavior='append', sudo_user=sudoer):
    with cd(wp_dir):
      install_wordpress(version, host)

@task
def build(wp_version=''):
  deploy(wp_version='')

@task
def backup():
  servers = get_servers()
  today = datetime.date.today()
  time = "%s%s%s" % (today.year, today.month, today.day)
  bucket = get_s3()['sql']
  for server in servers:
    host = servers[server]
    # name file timestamp-backup.sql
    backupfile = "%s-backup.sql" % time
    with cd(host['wp-config']):
      run('wp db export ~/%s' % backupfile)
    with cd('/home/%s' % host['user']):
      # put timestamp-backup.sql to <bucket>/<server>/2015/05/
      s3 = "s3://%s/%s/%s/%s/" % (bucket, server, today.year, today.month)
      run('s3cmd put %s %s' % (backupfile, s3))
      run('rm %s' % backupfile)
