import discord
from discord.ext import commands
import requests
import os
from dotenv import load_dotenv
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv(dotenv_path='C:/Users/Thomas/Desktop/Bot Stuff/.env')


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def card(ctx, *, args):
      headers = {'User-Agent': 'boooot', 'Accept': 'application/json'}

      # Check if user specified a set with | separator
      # e.g. !card llanowar elves | M19
      if '|' in args:
        card_name, set_code = args.split('|')
        card_name = card_name.strip()
        set_code = set_code.strip()
        url = f'https://api.scryfall.com/cards/named?fuzzy={card_name}&set={set_code}'
      else:
           card_name = args.strip()
           url = f'https://api.scryfall.com/cards/named?fuzzy={card_name}'

      response = requests.get(url, headers=headers)

      if response.status_code == 200:
            data = response.json()

            name = data['name']
            image = data['image_uris']['normal']
            set_name = data['set_name']
            prices = data['prices']

            usd = prices.get('usd', 'N/A')
            usd_foil = prices.get('usd_foil', 'N/A')

            #Find legality
            legalities = data['legalities']
            legal_formats = [fmt.capitalize() for fmt, status in legalities.items() if status == 'legal']
            legal_str = ', '.join(legal_formats) if legal_formats else 'None'

            embed = discord.Embed(title=name)
            embed.set_image(url=image)
            embed.add_field(name='Price', value=f'${usd}')
            embed.add_field(name='Foil Price', value=f'${usd_foil}')
            embed.add_field(name='Legal in', value=legal_str, inline=False)

            await ctx.send(embed=embed)
      else:
            await ctx.send(f'Card not found: {card_name}')

bot.run(os.getenv('DISCORD_TOKEN'))