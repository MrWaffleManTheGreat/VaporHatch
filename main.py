import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
from bs4 import BeautifulSoup

# ==========================
# CONFIG
# ==========================

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1466324052837798005  # channel for alerts

PRODUCTS = {
    "fogerkit": {
        "name": "Foger Switch Pro 30K KIT",
        "url": "https://www.vaporhatch.com/products/foger-switch-pro-30k?variant=49948988866856",
        "last_stock": set(),
        "initialized": False
    },
    "herox": {
        "name": "Hero X 30K",
        "url": "https://www.vaporhatch.com/products/hero-x-coming-soon?variant=49127221395752",
        "last_stock": set(),
        "initialized": False
    },
    "raztn9000": {
        "name": "RAZ TN9000",
        "url": "https://www.vaporhatch.com/products/raz-tn9000-1",
        "last_stock": set(),
        "initialized": False
    },
    "fogerpod": {
        "name": "Foger Switch Pro 30K POD",
        "url": "https://www.vaporhatch.com/products/foger-switch-pro-30k-pod?variant=50326308421928",
        "last_stock": set(),
        "initialized": False
    },
    "geekbar": {
        "name": "Geek Bar Pulse 15000",
        "url": "https://www.vaporhatch.com/products/geek-bar-pulse-disposable-vape-15000-puffs",
        "last_stock": set(),
        "initialized": False
    }
}

# ==========================
# BOT SETUP
# ==========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ==========================
# SCRAPERS
# ==========================

def get_in_stock_flavors(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    fieldset = soup.find("fieldset", class_="product-form__input")
    if not fieldset:
        return set()

    in_stock = set()
    for inp in fieldset.find_all("input", {"type": "radio"}):
        if "disabled" not in inp.get("class", []):
            value = inp.get("value")
            if value:
                in_stock.add(value)

    return in_stock


def get_price(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    price = soup.find("span", class_="price-item--regular")
    return price.text.strip() if price else "Unknown"


# ==========================
# EVENTS
# ==========================

@bot.event
async def on_ready():
    await bot.tree.sync()
    check_stock_loop.start()
    print(f"Logged in as {bot.user}")


# ==========================
# BACKGROUND STOCK CHECK
# ==========================

@tasks.loop(minutes=30)
async def check_stock_loop():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    for product in PRODUCTS.values():
        current_stock = get_in_stock_flavors(product["url"])
        previous_stock = product["last_stock"]

        # First run = initialize only
        if not product["initialized"]:
            product["last_stock"] = current_stock
            product["initialized"] = True
            continue

        restocked = current_stock - previous_stock
        sold_out = previous_stock - current_stock
        price = get_price(product["url"])

        if restocked:
            await channel.send(
                f"🚨 **{product['name']} RESTOCKED!**\n"
                f"💲 **Price:** {price}\n"
                f"🔗 {product['url']}\n"
                "```"
                + "\n".join(f"- {i}" for i in sorted(restocked))
                + "```"
            )

        if sold_out:
            await channel.send(
                f"❌ **{product['name']} SOLD OUT**\n"
                f"💲 **Price:** {price}\n"
                f"🔗 {product['url']}\n"
                "```"
                + "\n".join(f"- {i}" for i in sorted(sold_out))
                + "```"
            )

        product["last_stock"] = current_stock


# ==========================
# SLASH COMMANDS
# ==========================

@bot.tree.command(name="stock", description="Check vape stock")
@app_commands.choices(
    product=[
        app_commands.Choice(name="Foger Switch Pro 30K POD", value="fogerpod"),
        app_commands.Choice(name="Foger Switch Pro 30K KIT", value="fogerkit"),
        app_commands.Choice(name="Geek Bar Pulse 15000", value="geekbar"),
        app_commands.Choice(name="RAZ TN9000", value="raztn9000"),
        app_commands.Choice(name="Hero X 30K", value="herox"),
    ]
)
async def stock(interaction: discord.Interaction, product: app_commands.Choice[str]):
    data = PRODUCTS[product.value]
    flavors = get_in_stock_flavors(data["url"])
    price = get_price(data["url"])

    if flavors:
        msg = (
            "```"
            f"{data['name']}\n"
            f"Price: {price}\n"
            "IN STOCK:\n"
            + "\n".join(f"- {f}" for f in sorted(flavors))
            + "```"
            f"\n🔗 {data['url']}"
        )
    else:
        msg = (
            f"**{data['name']}**\n"
            f"💲 **Price:** {price}\n"
            f"🔗 {data['url']}\n"
            "❌ **All flavors are OUT OF STOCK**"
        )

    await interaction.response.send_message(msg)


@bot.tree.command(name="help", description="Show commands")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Commands**\n"
        "/stock – Check product stock\n"
        "/help – Show this menu",
        ephemeral=True
    )


# ==========================
# START BOT
# ==========================

bot.run(TOKEN)
