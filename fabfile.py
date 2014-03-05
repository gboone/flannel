import yaml

def hello():
	print("Hello world!")

def get_config():
	import yaml
	config = file('config.yaml', 'r')
	yaml = yaml.load(config)

def show_themes(yaml):
	for y in yaml['Themes']:
		name = y['name']
		print(name)