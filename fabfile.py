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
	return data['Plugins']

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
	env.hosts.append(full_addr)

# Actual flannel
def check_for_wp_cli(host):
	servers = get_servers()
	server = servers[host]['wp-cli']
	cli = run('which wp')
	if cli != server:
		sys.exit('You should install wp-cli, it\'s damn handy.')

def show_themes(data):
	config = file(data)
	data = yaml.load(config)
	for y in data['Themes']:
		name = y['name']
		print(name)

def check_wp_version(wp_dir):
	with cd(wp_dir):
		v = run('wp core version')
	config = get_config()
	version = config['Application']['WordPress']['version'] 
	if v == version:
		run('echo WordPress is okay!')
	else:
		upgrade_wordpress(wp_dir, version)

def check_wp_extensions(wp_dir, extn):
	extensions = plugin_or_theme(extn)
	for p in extensions:
		version = extensions[p]['version']
		with cd(wp_dir):
			try:
				run('wp %s is-installed %s' % (extn, p))
				v = run('wp %s get %s --field=version' % (extn, p))
				if v == version:
					print('%s %s is okay!' % (extn, p))
				else:
					upgrade_extension(wp_dir, version, p, extn)
			except SystemExit:
				install_extension(wp_dir, version, p, extn)

def upgrade_wordpress(wp_dir, version):
	with settings(sudo_user):
		with cd(wp_dir):
			sudo('wp core update --version=%s --force' % version)

def upgrade_extension(wp_dir, version, p, extn):
	extension = plugin_or_theme(extn)
	with cd(wp_dir):
		if extension[p]['src'] == False:
			run('wp %s install %s --version=%s --force' % (extn, p, version))
		else:
			install_extension(wp_dir, version, p, extn)

def install_extension(wp_dir, version, p, extn):
	extension = plugin_or_theme(extn)
	if extn == 'plugin':
		extension_dir = '%s/wp-content/plugins' % (wp_dir)
	if extn == 'theme':
		extension_dir = '%s/wp-content/themes' % (wp_dir)
	with cd(wp_dir):
		if extension[p]['src']:
			src = extension[p]['src']
			full_addr = build_full_addr(src, p, version, extn)
			if full_addr[:4] != '.zip':
				run('wget %s -O %s.zip' % (full_addr, p))
			else:
				run('wget %s -O %s.zip')
			run('wp %s install %s.zip' % (extn, p))
			run('cp -r %s/%s-%s %s/%s' % (extension_dir, p, version, extension_dir, p))
			run('rm -rf %s/%s-%s' % (extension_dir, p, version))
			run('rm -rf %s.zip' % (p))
		else:
			run('wp %s install %s' % (extn, p))
		if extension[p]['state'] == 'active':
			run('wp %s activate %s' % (extn, p))

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
	host = host[index:]
	wp_dir = data[host]['wordpress']
	check_for_wp_cli(host)
	check_wp_version(wp_dir)
	check_wp_extensions(wp_dir, extn = 'plugin')
	check_wp_extensions(wp_dir, extn = 'theme')
