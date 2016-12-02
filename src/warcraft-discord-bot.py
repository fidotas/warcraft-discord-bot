#!/usr/bin/python
#

import discord
import asyncio
import logging
import urllib.request
import json
import sys

# Bot Configuration
settings = {
	'DiscordGuildToken': 'MjU0MDc5NTc0NTEyNTAwNzM2.CyJ2MQ.maZ_XZBAeCchFfDpLzM-JtOroJY',
	'BlizzardAPIKey': 'tmmf988hfysd6x4yuvwedypyxjcqd6pc',
	'GuildNewsChannelName': 'general',
	'GuildNewsRefreshPeriod': 24,
	'LogLevel': 'DEBUG',
	'LogFile': 'warcraft-discord-bot.log'
}

# Globals
logger = ''
client = discord.Client()
cache = {}
qualityColours = [ 0xCCCCCC, 0xFFFFFF, 0x00FF00, 0x0000FF, 0xB833FF, 0xFFC300 ]

def setupLogging():
	global settings, logger
	logger = logging.getLogger('discord')
	logger.setLevel(logging.INFO)
	if 'LogLevel' in settings.keys():
		if settings['LogLevel'].lower() == 'critical':
			logger.setLevel(logging.CRITICAL)
		elif settings['LogLevel'].lower() == 'error':
			logger.setLevel(logging.ERROR)
		elif settings['LogLevel'].lower() == 'warning':
			logger.setLevel(logging.WARNING)
		elif settings['LogLevel'].lower() == 'debug':
			logger.setLevel(logging.DEBUG)
	if 'LogFile' in settings.keys():
		handler = logging.FileHandler(filename=settings['LogFile'], encoding='utf-8', mode='a')
		handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
		logger.addHandler(handler)
	handler = logging.StreamHandler()
	handler.setLevel(logging.INFO)
	logger.addHandler(handler)

def refreshCache():
	global cache, settings, logger
	# Realm list
	try:
		response = urllib.request.urlopen('https://us.api.battle.net/wow/realm/status?locale=en_US&apikey=%s' % settings['BlizzardAPIKey'])
		html = response.read().decode('utf-8')
		logger.debug('Blizzard realm status query returned: %s' % html)
		data = json.loads(html)
		if isinstance(data, dict) and 'realms' in data.keys():
			cache['realms'] = [r['name'].lower() for r in data['realms']]
			logger.info('%d realms extracted from Blizzard API' % len(cache['realms']))
			logger.debug('Realm list: %s' % ", ".join(cache['realms']))
		else:
			logger.warning('Blizzard realm status query returned a datatype of %s when I expected dict.' % type(data))
	except urllib.error.HTTPError as e:
		logger.warning('The attempt to refresh the list of available WOW realms resulted in HTTP error [%s]: %s.' % (e.code, e.read()))
	except urllib.error.URLError as e:
		logger.warning('The Blizzard API server was unavailable: %s.' % e.reason)
	# Character races
	try:
		response = urllib.request.urlopen('https://us.api.battle.net/wow/data/character/races?locale=en_US&apikey=%s' % settings['BlizzardAPIKey'])
		html = response.read().decode('utf-8')
		logger.debug('Blizzard data query returned: %s' % html)
		data = json.loads(html)
		if isinstance(data, dict) and 'races' in data.keys():
			cache['races'] = {r['id']: dict({'side': r['side'], 'name': r['name'], 'mask': r['mask'], 'id': r['id']}) for r in data['races']}
			logger.info('%d races extracted from Blizzard API' % len(cache['races'].keys()))
			logger.debug('Race list: %s' % ", ".join([r['name'] for r in cache['races'].values()]))
		else:
			logger.warning('Blizzard character race query returned a datatype of %s when I expected dict.' % type(data))
	except urllib.error.HTTPError as e:
		logger.warning('The attempt to refresh the list of available character races resulted in HTTP error [%s]: %s.' % (e.code, e.read()))
	except urllib.error.URLError as e:
		logger.warning('The Blizzard API server was unavailable: %s.' % e.reason)
	# Character classes
	try:
		response = urllib.request.urlopen('https://us.api.battle.net/wow/data/character/classes?locale=en_US&apikey=%s' % settings['BlizzardAPIKey'])
		html = response.read().decode('utf-8')
		logger.debug('Blizzard data query returned: %s' % html)
		data = json.loads(html)
		if isinstance(data, dict) and 'classes' in data.keys():
			cache['classes'] = {r['id']: dict({'powerType': r['powerType'], 'name': r['name'], 'mask': r['mask'], 'id': r['id']}) for r in data['classes']}
			logger.info('%d classes extracted from Blizzard API' % len(cache['races'].keys()))
			logger.debug('Class list: %s' % ", ".join([r['name'] for r in cache['races'].values()]))
		else:
			logger.warning('Blizzard character class query returned a datatype of %s when I expected dict.' % type(data))
	except urllib.error.HTTPError as e:
		logger.warning('The attempt to refresh the list of available character classes resulted in HTTP error [%s]: %s.' % (e.code, e.read()))
	except urllib.error.URLError as e:
		logger.warning('The Blizzard API server was unavailable: %s.' % e.reason)

def getCharacterGear(name, realm):
	global logger
	try:
		response = urllib.request.urlopen('https://us.api.battle.net/wow/character/%s/%s?fields=items&locale=en_US&apikey=%s' % (realm, name, settings['BlizzardAPIKey']))
		html = response.read().decode('utf-8')
		logger.debug('Blizzard character item query returned: %s' % html)
		data = json.loads(html)
		if isinstance(data, dict):
			return data
		else:
			return "Blizzard API server returned a data structure of type *%s* when I expected dict, sorry." % type(data)
			logger.warning('Blizzard realm status query returned a datatype of %s when I expected dict.' % type(data))
	except urllib.error.HTTPError as e:
		if e.code == 404:
			return "*%s* not found on realm *%s*, sorry." % (name, realm)
		else:
			logger.warning('The attempt to refresh the list of available WOW realms resulted in HTTP error [%s]: %s.' % (e.code, e.read()))
			return "An unexpected error occured: [%s] %s." % (e.code, e.read())
	except urllib.error.URLError as e:
		logger.warning('The Blizzard API server was unavailable: %s.' % e.reason)
		return "The Blizzard API server is unavailable, sorry: %s." % e.reason

def renderCharacterItems(characterData):
	global cache, logger, qualityColours
	if 'items' not in characterData.keys():
		return None
	items = []
	baseIconURL = 'http://media.blizzard.com/wow/icons/56/'
	for item in characterData['items']:
		em = discord.Embed(title=item['name'], description='ilvl %s' % item['itemLevel'], colour=qualityColours[item['quality']], url='')
		em.set_thumbnail(url='%s%s.png' % (baseIconURL, item['icon']))
		items.append(em)
	return items
	
async def bgRefreshCache_task():
	global settings, logger, client
	await client.wait_until_ready()
	while not client.is_closed:
		refreshCache()
		await asyncio.sleep(3600) # Every hour

async def bgGuildNews_task():
	global settings, logger, client
	await client.wait_until_ready()
	guildNewsChannel = discord.utils.get(client.get_all_channels(), name=settings['GuildNewsChannelName'], type='text')
	if guildNewsChannel is None:
		logger.warning('Unable to resolve channel name "%s".' % settings['GuildNewsChannelName'])
		return
	channel = discord.Object(id=guildNewsChannel)
	counter = 0
	while not client.is_closed:
		counter = counter + 1
		await client.send_message(guildNewsChannel, 'Background task has executed %s times!' % counter)
		await asyncio.sleep(settings['GuildNewsRefreshPeriod'] * 60 * 60) # sleep X seconds

@client.event
async def on_ready():
	global settings, logger, client
	logger.info('Logged in as %s [%s].' % (client.user.name, client.user.id))
	for server in client.servers:
		logger.info('\tServer: %s' % server.name)
		for channel in server.channels:
			logger.info('\t\tChannel: [%s] %s' % (channel.type, channel.name))

@client.event
async def on_message(message):
	global cache
	if message.content.startswith('!ping'):
		await client.send_message(message.channel, "PONG! I'm here, I promise!")
	elif message.content.startswith('!gearcheck'):
		elements = message.content.split(' ')
		if len(elements) < 3:
			data = getCharacterGear(elements[1], 'proudmoore') # Without a realm, assume proudmoore our home
		else:
			if elements[2].lower() in cache['realms']:
				data = getCharacterGear(elements[1], elements[2])
			else:
				await client.send_message(message.channel, "*%s* is not a recognised realm name, sorry." % elements[2])
		if data is not None:
			if isinstance(data, dict):
				# Summary announcement
				await client.send_message(message.channel, "**%s** from *%s* is a level %s %s %s with an average item level of %s." % (data['name'], data['realm'], data['level'], cache['races'][data['race']]['name'], cache['classes'][data['class']]['name'], data['items']['averageItemLevel']), tts=True)
				# Detail pane
				#em = discord.Embed(title='title', description='description', colour=0xffffff)
				#em.set_author(name=data['name'], icon_url='http://render-api-us.worldofwarcraft.com/static-render/us/%s' % data['thumbnail'])
				await client.send_message(message.channel, embeds=renderCharacterItems(data))
			else:
				await client.send_message(message.channel, data)

def main():
	global settings, client, logger
	if sys.version_info[0] != 3 and sys.version_info[1] >= 5:
		print("This script requires Python 3.5 or later. Please consider upgrading.")
		exit()
	
	# Configure logging
	setupLogging()
	
	# Connect to Discord
	client.loop.create_task(bgGuildNews_task()) # Guild news announcer
	client.loop.create_task(bgRefreshCache_task()) # Refresh warcraft API cache (item info, realm list, etc.)
	client.run(settings['DiscordGuildToken'])
	
if __name__ == '__main__':
	main()