from __future__ import with_statement
from fabric.api import *
from fabric.contrib.console import confirm
from sysconfig import *
import yaml

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

# Set servers dynamically
servers = get_servers()
for s in servers:
	print(s)
	address = s
	user = servers[s]['user']
	full_addr = "%s@%s" % (user, address)
	if servers[s].has_key('port'):
		full_addr += ':%s' % servers[s]['port']
	env.hosts.append(full_addr)

# Actual flannel
def check_for_wp_cli(host):
	servers = get_servers()
	server = servers[host]['wp-cli']
	
	if server is None:
		sys.exit('You should install wp-cli, it\'s damn handy.')
	else:
		server

def check_wp_version(wp_dir):
	with cd(wp_dir):
		v = run('wp core version')
	config = get_config()
	version = config['Application']['WordPress']['version'] 
	if v == version:
		puts('WordPress is okay!')
	else:
		upgrade_wordpress(wp_dir, version)

def check_wp_extensions(wp_dir, extn):
	extension = plugin_or_theme(extn)
	for p in extension:
		root_dir = "%s/wp-content/%ss" % (wp_dir, extn)
		extension_dir = "%s/%s" % (root_dir, p)
		version = extension[p]['version']
		with cd(wp_dir):
			try:
				run('wp %s is-installed %s' % (extn, p))
			except SystemExit:
				install_extension(wp_dir, version, p, extn, extension_dir)
			v = run('wp %s get %s --field=version' % (extn, p))
			if str(v) == str(version):
				print('%s %s is okay!' % (extn, p))
			elif v > version:
				downgrade_extension(wp_dir, version, p, extn, extension_dir)
			else:
				upgrade_extension(wp_dir, version, p, extn, extension_dir)
			if extn == 'theme':
				if run('wp option get template') == p:
					active = 'active'
			else:
				active = run('wp plugin get %s --field=status' % (p))
			if str(active) != 'active':
				activate_extension(extn, p)

def activate_extension(extn, p):
	run('wp %s activate %s' % (extn, p))

def upgrade_wordpress(wp_dir, version):
	with cd(wp_dir):
		sudo('wp core update --version=%s --force' % version)

def upgrade_extension(wp_dir, version, p, extn, extension_dir):
	extension = plugin_or_theme(extn)
	with cd(wp_dir):
		if extension[p].has_key('src') == False:
			url = 'http://wordpress.org'
			run('wp %s install %s/%s/%s.%s.zip' % (extn, url, extn, p, version))
		else:
			with cd("%s/%s" % (extension_dir, p)):
				if is_git_repo() == False:
					add_git_remotes(p)
				run('git fetch origin')
				run('git checkout origin/%s' % version)
				# install_extension(wp_dir, version, p, extn)

def downgrade_extension(wp_dir, version, p, extn, extension_dir):
	extension = plugin_or_theme(extn)
	with cd(wp_dir):
		if extension[p].has_key('src') == False:
			url = 'http://wordpress.org'
			if extn != 'theme':
				run('wp %s deactivate %s' % (extn, p))
				run('wp %s uninstall %s' % (extn, p))
			run('wp %s install %s/%s/%s.%s.zip' % (extn, url, extn, p, version))

def install_extension(wp_dir, version, p, extn, extension_dir):
	extension = plugin_or_theme(extn)
	if extension[p].has_key('src'):
		with cd('%s/wp-content/%ss' % (wp_dir, extn)):
			src = extension[p]['src']
			git_clone(extn, p, src)
			with cd(extension_dir):
				run('git fetch origin')
				run('git checkout origin/%s' % (version))
	else:
		with cd(wp_dir):
			run('wp %s install %s' % (extn, p))

def git_clone(extn, p, src):
	extension = plugin_or_theme(extn)
	vcs = get_vcs()
	if extension[p].has_key('vcs_user'):
		origin = extension[p]['vcs_user']
		upstream = vcs[src]['user']
	else:
		origin = vcs[src]['user']
	url = vcs[src]['url']
	run('git clone git@%s:%s/%s.git' % (url, origin, p))
	if upstream is not None:
		try:
			run('git remote add upstream %s/%s/%s.git' % (url, upstream, p))
		except SystemExit:
			pass

def is_git_repo():
	try:
		run('git status')
		return True
	except SystemExit:
		return False

def set_git_remotes(p, extn):
	extension = get_plugin_or_theme(extn)
	src = extension[p]['src']
	vcs = get_vcs()
	url = vcs[src]['url']
	if extension[p].has_key('vcs_user'):
		origin = extension[p]['vcs_user']
		upstream = vcs[src]['user']
	else:
		origin = vcs[src]['user']
	run("git remote add origin git@%s:%s/%s" % (url, origin, p))
	if upstream:
		run("git remote add upstream git@%s:%s/%s" % (url, upstream, p))

def build_full_addr(src, p, version, extn):
	extension = plugin_or_theme(extn)
	vcs = get_vcs()
	if extension[p].has_key('url') is False:
		vcs_url = vcs[src]['url']
		if extension[p].has_key('vcs_user'):
			vcs_user = extension[p]['vcs_user']
		else:
			vcs_user = vcs[src]['user']
		if vcs[src] == vcs['GitHub']:
			full_addr = "%s/%s/%s/archive/%s.zip" % ( vcs_url, vcs_user, p, version)
		elif vcs[src] == vcs['GitHubEnterprise']:
			full_addr = "%s/%s/%s/zip/%s" % (vcs_url, vcs_user, p, version)
	else:
		full_addr = extension[p]['url']
	return full_addr

def plugin_or_theme(extn):
	if extn == 'plugin':
		extension = get_plugins()
	elif extn == 'theme':
		extension = get_themes()
	else:
		sys.exit('Either plugin or theme must be set to True.')
	return extension

def deploy():
	data = get_servers()
	host = env.host_string
	index = host.index('@')
	index = index + 1
	port = host.find(':')
	if port > -1 < len(host):
		host = host[index:port]
	else:
		host = host[index:]
	wp_dir = data[host]['wordpress']
	wp_cli = check_for_wp_cli(host)
	themes = get_themes()
	plugins = get_plugins()
	with settings(path=wp_cli, behavior='append'), settings(sudo_user=data[host]['sudo_user']):
		sudo('whoami')
		check_wp_version(wp_dir)
		if plugins is not None:
			check_wp_extensions(wp_dir, extn = 'plugin')

		if themes is not None:
			check_wp_extensions(wp_dir, extn = 'theme')
