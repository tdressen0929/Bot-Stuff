import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import requests
import os
from dotenv import load_dotenv
import ssl
from datetime import time, date
import re
from zoneinfo import ZoneInfo

ssl._create_default_https_context = ssl._create_unverified_context

HEADERS = {'User-Agent': 'boooot', 'Accept': 'application/json'}

DAILY_CARD_CHANNEL_ID = int(os.getenv('CHANNEL_TOKEN'))
load_dotenv()
# ^ if bot breaks, probably was this code

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

keyword_list = []

#-----------------------------------------HELPERS------------------------------------------------------

def get_card_image(data):
     #Returns iamge URL to help with double faced cards
     if 'image_uris' in data:
          return data['image_uris']['normal']
     if 'card_faces' in data and 'image_uris' in data['card_faces'][0]:
          return data['card_faces'][0]['image_uris']['normal']
     return None

def get_legal_formats(data):
     legal = [fmt.capitalize() for fmt, status in data['legalities'].items() if status == 'legal']
     return ', '.join(legal) if legal else 'None'


def get_cheapest_print(card_name, secret_lair_only=False):
      #Get all prints of a card
      response = requests.get(f'https://api.scryfall.com/cards/search', params={'q': f'!"{card_name}"', 'unique': 'prints'}, headers=HEADERS)

      if response.status_code != 200:
          return None

      cards = response.json().get('data', [])

      if secret_lair_only:
          #filters for only secret lair cards
          cards = [c for c in cards if c.get('set', '').startswith('sl')]
      else:
          #filter out secret lair prints
          cards = [c for c in cards if not c.get('set', '').startswith('sl')]

      if not cards:
           return None

      #find cheapest printing regardless of foil or not
      cheapest = None
      cheapest_price = float('inf')

      for c in cards:
           prices = c.get('prices', {})
           usd = float(prices.get('usd') or 'inf')
           usd_foil = float(prices.get('usd_foil') or 'inf')
           lowest = min(usd, usd_foil)

           if lowest < cheapest_price:
                cheapest_price = lowest
                cheapest = c
                cheapest['cheapest_price'] = lowest
                cheapest['cheapest_type'] = 'Foil' if usd_foil < usd else 'Normal'

      return cheapest

def build_cheapest_button(name, secret_lair_only=False):
     label = 'Find Cheapest SL Printing' if secret_lair_only else 'Find Cheapest Printing'
     button = Button(label=label, style=discord.ButtonStyle.red)

     async def button_callback(interaction):
          await interaction.response.defer()
          cheapest = get_cheapest_print(name, secret_lair_only=secret_lair_only)

          if cheapest:
               prefix = 'SL ' if secret_lair_only else ''
               embed = discord.Embed(title=f'Cheapest {prefix} Printing: {cheapest["name"]} - {cheapest["set_name"]}')
               image = get_card_image(cheapest)
               if image:
                    embed.set_image(url=image)
               embed.add_field(name='Cheapest Printing', value=f'{cheapest["cheapest_type"]}: ${cheapest["cheapest_price"]:.2f}')
               await interaction.followup.send(embed=embed)
          else:
               await interaction.followup.send('Could not find any prints')

     button.callback = button_callback
     view = View(timeout=None)
     view.add_item(button)
     return view

def get_newest_set_code():
     response = requests.get('https://api.scryfall.com/sets', headers=HEADERS)

     if response.status_code != 200:
          return None

     today = date.today().isoformat()

     released = [s for s in response.json().get('data', []) if s.get('released_at') and s['released_at'] <= today and s.get('set_type') in ('core', 'expansion')]

     if not released:
          return None

     newest = max(released, key=lambda s: s['released_at'])
     return newest['code']


def find_reminder_text(cards, keyword_name):
     #Matches a line starting wit hthe keyword, the the reminder text in parentheses
     pattern = re.compile(rf'^{re.escape(keyword_name)}\b[^\n(]*\(([^)]+)\)', re.IGNORECASE | re.MULTILINE)

     for card in cards:
          #Double faced keep their text inside card-faces
          texts = [card.get('oracle_text', '')]
          texts += [face.get('oracle_text', '') for face in card.get('card_faces', [])]

          for text in texts:
               match = pattern.search(text)
               if match:
                    return match.group(1)
     return None

def load_keywords():
     for endpoint in ('keyword-abilities', 'keyword-actions'):
          r = requests.get(f'https://api.scryfall.com/catalog/{endpoint}', headers=HEADERS)
          if r.status_code == 200:
               keyword_list.extend(r.json().get('data', []))

#----------------------------DAILY CARD-----------------------------

async def post_daily_card():
     qurey = '-t:land'
     newest_set = get_newest_set_code()
     if newest_set:
          query += f' -in:{newest_set}'

     response = requests.get('https://api.scryfall.com/cards/random', params={'q': query}, headers=HEADERS)

     if response.status_code != 200:
          print(f'Daily card request failed: {response.status_code}')
          return

     data = response.json()
     prices = data['prices']

     embed = discord.Embed(title=f'Card of the Day: {data["name"]} - {data["set_name"]}')

     image = get_card_image(data)
     if image:
          embed.set_image(url=image)

     embed.add_field(name='Price', value=f'${prices.get("usd") or "N/A"}')
     embed.add_field(name='Foil Price', value=f'${prices.get("usd_foil" or "N/A")}')
     embed.add_field(name='Legal In', value=get_legal_formats(data), inline=False)

     view = build_cheapest_button(data["name"])

     channel = bot.get_channel(DAILY_CARD_CHANNEL_ID)
     if channel is None:
          try:
               channel = await bot.fetch_channel(DAILY_CARD_CHANNEL_ID)
          except discord.NotFound:
               print(f'Channel {DAILY_CARD_CHANNEL_ID} not found')
          except discord.Forbidden:
               print('boooot does not have permission to see that channel')

     if channel:
          await channel.send(embed=embed, view=view)


#Runs at 7am CDT everyday
@tasks.loop(time=time(hour=12, minute=0, tzinfo=ZoneInfo('America/Chicago')))
async def daily_card():
     print('Printing daily card')
     await post_daily_card()

#----------------------BOT EVENTS--------------------

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not keyword_list:
         load_keywords()

    if not daily_card.is_running():
         daily_card.start()
         print('Daily card loop started')

    #Sync slash commands(potential to take up to an hour)
    await bot.tree.sync()
    print('Slash commands synced')

#--------------------SLASH COMMANDS--------------------

@bot.tree.command(name='card', description='Name of the MtG card you want to search')
async def card(interaction: discord.Interaction, card_name: str, set_code: str = None):
     await interaction.response.defer()

     params = {'fuzzy': card_name}
     if set_code:
          params['set'] = set_code

     response = requests.get('https://api.scryfall.com/cards/named', params=params, headers=HEADERS)

     if response.status_code != 200:
          await interaction.followup.send(f'Card not found: {card_name}')
          return

     data = response.json()
     prices = data['prices']
     is_secret_lair = data.get('set', '').startswith('sl')

     embed = discord.Embed(title=f'{data["name"]} - {data["set_name"]}')

     image = get_card_image(data)
     if image:
          embed.set_image(url=image)

     embed.add_field(name='Price', value=f'${prices.get("usd") or "N/A"}')
     embed.add_field(name='Foil Price', value=f'${prices.get("usd_foil" or "N/A")}')
     embed.add_field(name='Legal In', value=get_legal_formats(data), inline=False)

     view = build_cheapest_button(data["name"], secret_lair_only=is_secret_lair)

     await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name='keyword', description='Grabs reminder text for a keyword')
async def keyword(interaction: discord.Interaction, keyword_name: str):
     await interaction.response.defer()

     response = requests.get('https://api.scryfall.com/cards/search', params={'q': f'keyword:"{keyword_name}"', 'order': 'released', 'dir': 'desc', 'unique': 'cards'}, headers=HEADERS)

     if response.status_code != 200:
          await interaction.followup.send(f'No cards found with the keyword "{keyword_name}"')
          return

     cards = response.json().get('data', [])
     reminder = find_reminder_text(cards, keyword_name)

     if reminder:
          embed = discord.Embed(title=keyword_name.title(), description=reminder)
          await interaction.followup.send(embed=embed)
     else:
          await interaction.followup.send(f'Found cards with "{keyword_name}, but none contained reminder text')

@keyword.autocomplete('keyword_name')
async def keyword_autocomplete(interaction: discord.Interaction, current: str):
     matches = [k for k in keyword_list if current.lower() in k.lower()]
     return [discord.app_commands.Choice(name=k, vlaue=k) for k in matches[:25]]

bot.run(os.getenv('DISCORD_TOKEN'))