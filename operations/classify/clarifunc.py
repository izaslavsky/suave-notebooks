# import credentials file
import yaml
with open("config.yml", 'r') as ymlfile:
    cfg = yaml.safe_load(ymlfile)
    
key=cfg['api_creds']['cfy1']
