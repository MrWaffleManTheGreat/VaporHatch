import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = 1466324052837798005

PRODUCTS = {
    "fogerkit": {
        "name": "Foger Switch Pro 30K KIT",
        "url": "https://www.vaporhatch.com/products/foger-switch-pro-30k?variant=49948988866856",
        "last_stock": set()
    },
    "herox": {
        "name": "Hero X 30K",
        "url": "https://www.vaporhatch.com/products/hero-x-coming-soon?variant=49127221395752",
        "last_stock": set()
    },
    "razTN9000": {
        "name": "Raz TN9000",
        "url": "https://www.vaporhatch.com/products/raz-tn9000-1",
        "last_stock": set()
    },
    "fogerpod": {
        "name": "Foger Switch Pro 30K POD",
        "url": "https://www.vaporhatch.com/products/foger-switch-pro-30k-pod?variant=50326308421928",
        "last_stock": set()
    },
    "geekbar": {
        "name": "Geek Bar Pulse 15000",
        "url": "https://www.vaporhatch.com/products/geek-bar-pulse-disposable-vape-15000-puffs",
        "last_stock": set()
    }
}

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def get_in_stock_flavors(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    fieldset = soup.find("fieldset", class_="product-form__input")
    if not fieldset:
        return set()

    return {
        inp.get("value")
        for inp in fieldset.find_all("input", {"type": "radio"})
        if "disabled" not in inp.get("class", []) and inp.get("value")
    }

@bot.event
async def on_ready():
    await bot.tree.sync()
    check_stock_loop.start()
    print(f"Logged in as {bot.user}")

@tasks.loop(minutes=30)
async def check_stock_loop():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    for product in PRODUCTS.values():
        current_stock = get_in_stock_flavors(product["url"])
        new_items = current_stock - product["last_stock"]

        if new_items:
            await channel.send(
                f"🚨 **{product['name']} RESTOCKED!**\n"
                "```" + "\n".join(f"- {i}" for i in sorted(new_items)) + "```"
            )

        product["last_stock"] = current_stock

@bot.tree.command(name="stock", description="Check vape stock")
@app_commands.choices(
    product=[
        app_commands.Choice(name="Foger Switch Pro 30K (POD)", value="fogerpod"),
        app_commands.Choice(name="Geek Bar Pulse 15000", value="geekbar"),
        app_commands.Choice(name="Foger Switch Pro 30K (KIT)", value="fogerkit"),
        app_commands.Choice(name="RAZ TN9000", value="razTN9000"),
        app_commands.Choice(name="Hero X 30K", value="herox"),
    ]
)
async def stock(interaction: discord.Interaction, product: app_commands.Choice[str]):
    data = PRODUCTS[product.value]
    flavors = get_in_stock_flavors(data["url"])

    if flavors:
        msg = "```" + f"{data['name']}\nIN STOCK:\n" + "\n".join(f"- {f}" for f in sorted(flavors)) + "```"
    else:
        msg = f"**{data['name']}**\n❌ **All flavors are OUT OF STOCK**"

    await interaction.response.send_message(msg)

@bot.tree.command(name="help", description="Show commands")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Commands**\n"
        "/stock – Check current stock\n"
        "/help – Show this menu",
        ephemeral=True
    )

bot.run(TOKEN)
