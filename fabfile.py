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

# Set servers dynamically
servers = get_servers()
for s in servers:
	print(s)
	address = s
	user = servers[s]['user']
	full_addr = "%s@%s" % (user, address)
	env.hosts.append(full_addr)

# Actual flannel
def show_themes(data):
	config = file(data)
	data = yaml.load(config)
	for y in data['Themes']:
		name = y['name']
		print(name)

def check_wp_version(wp_dir):
	with cd(wp_dir):
		v = sudo('wp core version')
	config = get_config()
	version = config['Application']['WordPress']['version'] 
	if v == version:
		sys.exit('WordPress is okay!')
	else:
		upgrade_wordpress(wp_dir, version)

def check_wp_plugins(wp_dir):
	plugins = get_plugins()
	for p in plugins:
		expected = plugins[p]['version']
		with cd(wp_dir):
			v = sudo('wp plugin get %s --field=version' % (p))
		if v == plugins[p]['version']:
			print('Plugin %s is okay!' %s (p))
		else:
			sys.exit('Plugin %s is at the wrong version. Expected %s but was %s' % (p, expected, v ))

def upgrade_wordpress(wp_dir, version):
	with settings(sudo_user):
		with cd(wp_dir):
			sudo('wp core update --version=%s --force' % version)

def check_for_wp_cli(host):
	servers = get_servers()
	server = servers[host]['wp-cli']
	cli = sudo('which wp')
	if cli != server:
		sys.exit('You should install wp-cli, it\'s damn handy.')

def deploy():
	data = get_servers()
	host = env.host_string
	index = host.index('@')
	index = index + 1
	host = host[index:]
	wp_dir = data[host]['wordpress']
	with settings(sudo_user="root"):
		check_for_wp_cli(host)
		check_wp_version(wp_dir)
		check_wp_plugins(wp_dir)
