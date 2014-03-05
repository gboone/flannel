from fabric.api import local
import yaml

def prepare_deploy():
	local('git add . && git commit')
	local('git push')

def hello():
	print("Hello world!")

def get_config():
	import yaml
	config = file('config.yaml', 'r')
	yaml = yaml.load(config)

def show_themes(data):
	config = file(data)
	data = yaml.load(config)
	for y in data['Themes']:
		name = y['name']
		print(name)