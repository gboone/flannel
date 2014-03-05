from __future__ import with_statement
from fabric.api import *
from fabric.contrib.console import confirm
from sysconfig import *
import yaml

def get_config():
	config = file('config.yaml')
	data = yaml.load(config)
	return data

def get_servers():
	data = get_config()
	return data['Servers']

servers = get_servers()
for s in servers:
	print(s)
	address = servers[s]['address']
	user = servers[s]['user']
	full_addr = "%s@%s" % (user, address)
	env.hosts.append(full_addr)

def prepare_deploy():
	local('git add . && git commit')
	local('git push')

def stash_and_fetch():
	local('git stash')
	local('git fetch')

def checkout_updated():
	local('git checkout origin')

def hello():
	print("Hello world!")

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
	if v == config['Application']['WordPress']['version']:
		v = True
	else:
		v= False
	return v

def upgrade_wordpress(wp_dir):
	with settings(sudo_user):
		with cd(wp_dir):
			sudo('wp core upgrade')

def deploy():
	data = get_servers()
	wp_dir = data['build']['wordpress']
	with settings(sudo_user="root"):
		v = check_wp_version(wp_dir)
	if v:
		sys.exit('WordPress is okay!')
	else:
		upgrade_wordpress(wp_dir)
