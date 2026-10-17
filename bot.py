import discord
from discord.ext import commands
from discord.ui import Button, View
import requests
import os
from dotenv import load_dotenv
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv(dotenv_path='C:/Users/Thomas/Desktop/Bot Stuff/.env')


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

def get_cheapest_print(card_name, secret_lair_only=False):
      headers = {'User-Agent': 'boooot', 'Accept': 'application/json'}

      #Get all prints of a card
      response = requests.get(f'https://api.scryfall.com/cards/search?q=!"{card_name}"&unique=prints', headers=headers)

      if response.status_code != 200:
          return None

      cards = response.json().get('data', [])

      if secret_lair_only:
          #filters for only secret lair cards
          cards = [c for c in cards if c.get('set', '').starswith('sl')]
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
            is_secret_lair = data.get('set', '').startswith('sl')

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

            #Change button text if the card is a secret lair card
            if is_secret_lair:
                 button_label = 'Find Cheapest Secret Lair Version'
            else:
                 button_label = 'Find Cheapest Version'

            #Create the button
            button = Button(label=button_label, style=discord.ButtonStyle.blurple)

            async def button_callback(interaction):
                  cheapest = get_cheapest_print(name, secret_lair_only=is_secret_lair)

                  if cheapest:
                        cheapest_embed = discord.Embed(title=f'Cheapest {"Secret Lair " if is_secret_lair else ""}Version: {cheapest["name"]} - {cheapest["set_name"]}')
                        if 'image_uris' in cheapest:
                           cheapest_embed.set_image(url=cheapest['image_uris']['normal'])
                        cheapest_embed.add_field(name='Cheapest Option', value=f'{cheapest["cheapest_type"]}: ${cheapest["cheapest_price"]:.2f}')
                        await interaction.response.send_message(embed=cheapest_embed)
                  else:
                       await interaction.response.send_message('Failed to find prints')
            button.callback = button_callback
            view = View()
            view.add_item(button)

            await ctx.send(embed=embed, view=view)
      else:
            await ctx.send(f'Card not found: {card_name}')

bot.run(os.getenv('DISCORD_TOKEN'))