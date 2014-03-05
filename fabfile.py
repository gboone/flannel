from __future__ import with_statement
from fabric.api import *
from fabric.contrib.console import confirm
import yaml

env.hosts = ['']
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

def get_config():
	config = file('config.yaml')
	data = yaml.load(config)
	return data

def get_servers():
	data = get_config()
	return data['Servers']

def show_themes(data):
	config = file(data)
	data = yaml.load(config)
	for y in data['Themes']:
		name = y['name']
		print(name)
def check_wp_version(wp_dir):
	with cd(wp_dir):
		sudo('wp core version')

def deploy():
	data = get_servers()
	wp_dir = data['build']['wordpress']
	with settings(sudo_user="root"):
		check_wp_version(wp_dir)