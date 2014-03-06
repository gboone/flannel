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

def check_wp_plugins(wp_dir):
	plugins = get_plugins()
	for p in plugins:
		import pdb; pdb.set_trace;
		version = plugins[p]['version']
		with cd(wp_dir):
			try:
				run('wp plugin is-installed %s' % (p))
				v = run('wp plugin get %s --field=version' % (p))
				if v == version:
					print('Plugin is okay!')
				else:
					upgrade_plugin(wp_dir, version, p)
			except SystemExit:
				install_plugin(wp_dir, version, p)

def check_themes(wp_dir):
	themes = get_themes()

def upgrade_wordpress(wp_dir, version):
	with settings(sudo_user):
		with cd(wp_dir):
			sudo('wp core update --version=%s --force' % version)

def upgrade_plugin(wp_dir, version, p):
	plugins = get_plugins()
	with cd(wp_dir):
		if plugins[p]['src'] == False:
			run('wp plugin update %s --version=%s' % (p, version))
		else:
			install_plugin(wp_dir, version, p)

def install_plugin(wp_dir, version, p):
	plugins = get_plugins()
	plugin_dir = '%s/wp-content/plugins' % wp_dir
	with cd(wp_dir):
		if plugins[p]['src']:
			src = plugins[p]['src']
			full_addr = build_full_addr(src, p, version)
			if full_addr[:4] != '.zip':
				run('wget %s -O %s.zip' % (full_addr, p))
			else:
				run('wget %s -O %s.zip')
			run('wp plugin install %s.zip' % (p))
			run('mv %s/%s-%s %s/%s' % (plugin_dir, p, version, plugin_dir, p))
			run('rm -rf %s.zip' % (p))
		else:
			run('wp plugin install %s' % (p))
		if plugins[p]['state'] == 'active':
			run('wp plugin activate %s' % (p))

def build_full_addr(src, p, version):
	plugins = get_plugins()
	vcs = get_vcs()
	import pdb; pdb.set_trace()
	if plugins[p].has_key('url') is False:
		vcs_url = vcs[src]['url']
		if plugins[p].has_key('vcs_user'):
			vcs_user = plugins[p]['vcs_user']
		else:
			vcs_user = vcs[src]['user']
		if vcs[src] == vcs['GitHub']:
			full_addr = "%s/%s/%s/archive/%s.zip" % ( vcs_url, vcs_user, p, version)
		elif vcs[src] == vcs['GitHubEnterprise']:
			full_addr = "%s/%s/%s/zip/%s" % (vcs_url, vcs_user, p, version)
	else:
		full_addr = plugins[p]['url']
	return full_addr

def deploy():
	data = get_servers()
	host = env.host_string
	index = host.index('@')
	index = index + 1
	host = host[index:]
	wp_dir = data[host]['wordpress']
	check_for_wp_cli(host)
	check_wp_version(wp_dir)
	check_wp_plugins(wp_dir)
