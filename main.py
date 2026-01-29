import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import json
import time
import re

# ==========================
# CONFIG
# ==========================

TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = 1466324052837798005  # channel for alerts
OWNER_ID = 123456789012345678  # REPLACE WITH YOUR DISCORD USER ID

# File to store custom products
CUSTOM_PRODUCTS_FILE = "custom_products.json"

# Default products
PRODUCTS = {
    "fogerkit": {
        "name": "Foger Switch Pro 30K KIT",
        "url": "https://www.vaporhatch.com/products/foger-switch-pro-30k?variant=49948988866856",
        "last_stock": set(),
        "initialized": False,
        "is_custom": False,
        "site": "vaporhatch"
    },
    "herox": {
        "name": "Hero X 30K",
        "url": "https://www.vaporhatch.com/products/hero-x-coming-soon?variant=49127221395752",
        "last_stock": set(),
        "initialized": False,
        "is_custom": False,
        "site": "vaporhatch"
    },
    "raztn9000": {
        "name": "RAZ TN9000",
        "url": "https://www.vaporhatch.com/products/raz-tn9000-1",
        "last_stock": set(),
        "initialized": False,
        "is_custom": False,
        "site": "vaporhatch"
    },
    "fogerpod": {
        "name": "Foger Switch Pro 30K POD",
        "url": "https://www.vaporhatch.com/products/foger-switch-pro-30k-pod?variant=50326308421928",
        "last_stock": set(),
        "initialized": False,
        "is_custom": False,
        "site": "vaporhatch"
    },
    "geekbar": {
        "name": "Geek Bar Pulse 15000",
        "url": "https://www.vaporhatch.com/products/geek-bar-pulse-disposable-vape-15000-puffs",
        "last_stock": set(),
        "initialized": False,
        "is_custom": False,
        "site": "vaporhatch"
    }
}

# ==========================
# DATA MANAGEMENT
# ==========================

def load_custom_products():
    """Load custom products from JSON file"""
    try:
        if os.path.exists(CUSTOM_PRODUCTS_FILE):
            with open(CUSTOM_PRODUCTS_FILE, 'r') as f:
                custom_products = json.load(f)
                for key, product in custom_products.items():
                    # Convert list back to set for last_stock
                    product["last_stock"] = set(product.get("last_stock", []))
                    product["initialized"] = product.get("initialized", False)
                    product["is_custom"] = True
                    # Ensure site is set
                    if "site" not in product:
                        product["site"] = detect_site_from_url(product["url"])
                    PRODUCTS[key] = product
            print(f"Loaded {len(custom_products)} custom products")
    except Exception as e:
        print(f"Error loading custom products: {e}")

def save_custom_products():
    """Save custom products to JSON file"""
    custom_products = {}
    for key, product in PRODUCTS.items():
        if product.get("is_custom", False):
            # Convert set to list for JSON serialization
            product_copy = product.copy()
            product_copy["last_stock"] = list(product["last_stock"])
            custom_products[key] = product_copy
    
    try:
        with open(CUSTOM_PRODUCTS_FILE, 'w') as f:
            json.dump(custom_products, f, indent=2)
    except Exception as e:
        print(f"Error saving custom products: {e}")

def generate_product_key(url):
    """Generate a unique key for a product based on URL"""
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()[:8]

def detect_site_from_url(url):
    """Detect which site the URL belongs to"""
    if "vaporhatch.com" in url:
        return "vaporhatch"
    elif "drsmoke.com" in url:
        return "drsmoke"
    else:
        return "unknown"

def get_product_name_from_url(url):
    """Extract product name from URL or page title"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        site = detect_site_from_url(url)
        
        if site == "vaporhatch":
            # VaporHatch: try to get product name from page
            title = soup.find('title')
            if title:
                name = title.text.strip()
                # Clean up the title
                if '|' in name:
                    name = name.split('|')[0].strip()
                return name
            
            # Fallback: use URL path
            import urllib.parse
            path = urllib.parse.urlparse(url).path
            if path:
                parts = path.strip('/').split('/')
                if parts:
                    product_slug = parts[-1]
                    # Convert slug to readable name
                    name = product_slug.replace('-', ' ').title()
                    return name
        
        elif site == "drsmoke":
            # DrSmoke: get product name from h1 tag
            h1 = soup.find('h1', class_='h2 product-single__title')
            if h1:
                name = h1.text.strip()
                return name
            
            # Alternative: try meta title
            title = soup.find('title')
            if title:
                name = title.text.strip()
                if '|' in name:
                    name = name.split('|')[0].strip()
                return name
        
        # Fallback for unknown sites
        import urllib.parse
        path = urllib.parse.urlparse(url).path
        if path:
            parts = path.strip('/').split('/')
            if parts and len(parts) > 1:
                product_slug = parts[-1]
                name = product_slug.replace('-', ' ').title()
                return name
        
        return "Custom Product"
    except:
        return "Custom Product"

# ==========================
# BOT SETUP
# ==========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ==========================
# SCRAPERS - VAPORHATCH
# ==========================

def get_vaporhatch_in_stock_flavors(url):
    try:
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
    except Exception as e:
        print(f"Error scraping VaporHatch {url}: {e}")
        return set()

def get_vaporhatch_price(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        price = soup.find("span", class_="price-item--regular")
        return price.text.strip() if price else "Unknown"
    except:
        return "Unknown"

# ==========================
# SCRAPERS - DR SMOKE
# ==========================

def get_drsmoke_in_stock_flavors(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Find select element with variants
        select = soup.find('select', class_=lambda x: x and x.startswith('variant__input'))
        if not select:
            # Alternative: look for any select with variant in class
            select = soup.find('select', class_=lambda x: x and 'variant' in x.lower())
        
        in_stock = set()
        
        if select:
            # Get all options that are not disabled
            for option in select.find_all('option'):
                if 'disabled' not in option.attrs:
                    value = option.get('value', '').strip()
                    if value and value != "Title":
                        in_stock.add(value)
        
        # If no select found, check for single product with inventory
        if not in_stock:
            # Try to get product title for single variant products
            h1 = soup.find('h1', class_='h2 product-single__title')
            if h1:
                product_name = h1.text.strip()
                # Check if there's inventory
                inventory_div = soup.find('div', id=lambda x: x and x.startswith('ProductInventory'))
                if inventory_div:
                    inventory_text = inventory_div.text.strip().lower()
                    if 'in stock' in inventory_text or 'available' in inventory_text:
                        in_stock.add(product_name)
        
        return in_stock
    except Exception as e:
        print(f"Error scraping DrSmoke {url}: {e}")
        return set()

def get_drsmoke_price(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Try multiple price selectors for DrSmoke
        price_selectors = [
            'span.product__price',
            'span.price-item--regular',
            'span.money',
            'span.current_price',
            'span[itemprop="price"]'
        ]
        
        for selector in price_selectors:
            price = soup.select_one(selector)
            if price:
                price_text = price.text.strip()
                # Clean up price text
                price_text = re.sub(r'[^\d\.$€£]', '', price_text)
                return price_text if price_text else "Unknown"
        
        return "Unknown"
    except:
        return "Unknown"

def get_drsmoke_inventory_count(url):
    """Get inventory count for DrSmoke products"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Find inventory div
        inventory_div = soup.find('div', id=lambda x: x and x.startswith('ProductInventory'))
        if inventory_div:
            inventory_text = inventory_div.text.strip()
            # Extract number from text like "8 in stock"
            match = re.search(r'(\d+)\s*(?:in stock|available|left)', inventory_text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    except:
        return None

# ==========================
# UNIVERSAL SCRAPER FUNCTIONS
# ==========================

def get_in_stock_flavors(url):
    """Universal function to get in-stock flavors based on site"""
    site = detect_site_from_url(url)
    
    if site == "vaporhatch":
        return get_vaporhatch_in_stock_flavors(url)
    elif site == "drsmoke":
        return get_drsmoke_in_stock_flavors(url)
    else:
        print(f"Unknown site for URL: {url}")
        return set()

def get_price(url):
    """Universal function to get price based on site"""
    site = detect_site_from_url(url)
    
    if site == "vaporhatch":
        return get_vaporhatch_price(url)
    elif site == "drsmoke":
        return get_drsmoke_price(url)
    else:
        return "Unknown"

def get_inventory_info(url):
    """Get additional inventory information if available"""
    site = detect_site_from_url(url)
    
    if site == "drsmoke":
        count = get_drsmoke_inventory_count(url)
        if count is not None:
            return f"{count} in stock"
    
    return ""

def get_stock_for_url(url):
    """Get stock and price for any given URL"""
    flavors = get_in_stock_flavors(url)
    price = get_price(url)
    name = get_product_name_from_url(url)
    inventory_info = get_inventory_info(url)
    
    return {
        "name": name,
        "flavors": flavors,
        "price": price,
        "url": url,
        "inventory_info": inventory_info,
        "site": detect_site_from_url(url)
    }

# ==========================
# EVENTS
# ==========================

@bot.event
async def on_ready():
    # Load custom products before starting
    load_custom_products()
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Start the stock check loop
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

    for product_id, product in list(PRODUCTS.items()):
        try:
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
            inventory_info = get_inventory_info(product["url"])

            if restocked:
                message = f"🚨 **{product['name']} RESTOCKED!**\n"
                message += f"💲 **Price:** {price}\n"
                
                if inventory_info:
                    message += f"📦 **Inventory:** {inventory_info}\n"
                
                message += f"🔗 {product['url']}\n"
                
                if restocked:
                    message += "```" + "\n".join(f"- {i}" for i in sorted(restocked)) + "```"
                
                await channel.send(message)

            if sold_out:
                message = f"❌ **{product['name']} SOLD OUT**\n"
                message += f"💲 **Price:** {price}\n"
                
                if inventory_info:
                    message += f"📦 **Last Inventory:** {inventory_info}\n"
                
                message += f"🔗 {product['url']}\n"
                
                if sold_out:
                    message += "```" + "\n".join(f"- {i}" for i in sorted(sold_out)) + "```"
                
                await channel.send(message)

            product["last_stock"] = current_stock
            
        except Exception as e:
            print(f"Error checking {product['name']}: {e}")

# ==========================
# SLASH COMMANDS
# ==========================

@bot.tree.command(name="sync", description="Sync slash commands (Owner only)")
async def sync(interaction: discord.Interaction):
    """Sync slash commands to Discord"""
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ Synced {len(synced)} commands globally.", ephemeral=True)
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        await interaction.followup.send(f"❌ Error syncing commands: {e}", ephemeral=True)

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
    inventory_info = get_inventory_info(data["url"])

    if flavors:
        msg = (
            "```"
            f"{data['name']}\n"
            f"Price: {price}\n"
        )
        
        if inventory_info:
            msg += f"Inventory: {inventory_info}\n"
            
        msg += (
            "IN STOCK:\n"
            + "\n".join(f"- {f}" for f in sorted(flavors))
            + "```"
            f"\n🔗 {data['url']}"
        )
    else:
        msg = (
            f"**{data['name']}**\n"
            f"💲 **Price:** {price}\n"
        )
        
        if inventory_info:
            msg += f"📦 **Inventory:** {inventory_info}\n"
            
        msg += (
            f"🔗 {data['url']}\n"
            "❌ **All flavors/variants are OUT OF STOCK**"
        )

    await interaction.response.send_message(msg)

@bot.tree.command(name="addurl", description="Add a new product URL to monitor")
@app_commands.describe(url="The product URL to monitor")
async def addurl(interaction: discord.Interaction, url: str):
    # Validate URL
    supported_sites = ["vaporhatch.com", "drsmoke.com"]
    if not any(site in url for site in supported_sites):
        await interaction.response.send_message(
            f"❌ **Error:** Only the following sites are supported:\n"
            f"• vaporhatch.com\n"
            f"• drsmoke.com",
            ephemeral=True
        )
        return
    
    # Check if URL already exists
    for existing_product in PRODUCTS.values():
        if existing_product["url"] == url:
            await interaction.response.send_message(
                f"❌ **Already monitoring:** This URL is already being monitored as '{existing_product['name']}'",
                ephemeral=True
            )
            return
    
    # Get product name
    await interaction.response.defer()
    
    try:
        name = get_product_name_from_url(url)
        product_key = generate_product_key(url)
        site = detect_site_from_url(url)
        
        # Add to PRODUCTS
        PRODUCTS[product_key] = {
            "name": name,
            "url": url,
            "last_stock": set(),
            "initialized": False,
            "is_custom": True,
            "site": site
        }
        
        # Save to file
        save_custom_products()
        
        await interaction.followup.send(
            f"✅ **Added to monitoring:** {name}\n"
            f"🌐 **Site:** {site.title()}\n"
            f"🔗 {url}\n"
            f"📊 This product will now be checked every 30 minutes for stock changes.\n"
            f"🆔 Product ID: `{product_key}`\n"
            f"📝 Use `/listcustom` to see all custom products."
        )
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ **Error adding URL:** {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="stockurl", description="Check stock for any supported URL")
@app_commands.describe(url="The product URL to check")
async def stockurl(interaction: discord.Interaction, url: str):
    # Validate URL
    supported_sites = ["vaporhatch.com", "drsmoke.com"]
    if not any(site in url for site in supported_sites):
        await interaction.response.send_message(
            f"❌ **Error:** Only the following sites are supported:\n"
            f"• vaporhatch.com\n"
            f"• drsmoke.com",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        stock_data = get_stock_for_url(url)
        flavors = stock_data["flavors"]
        
        if flavors:
            msg = (
                "```"
                f"{stock_data['name']}\n"
                f"Price: {stock_data['price']}\n"
            )
            
            if stock_data["inventory_info"]:
                msg += f"Inventory: {stock_data['inventory_info']}\n"
                
            msg += (
                "IN STOCK:\n"
                + "\n".join(f"- {f}" for f in sorted(flavors))
                + "```"
                f"\n🔗 {url}"
            )
        else:
            msg = (
                f"**{stock_data['name']}**\n"
                f"💲 **Price:** {stock_data['price']}\n"
            )
            
            if stock_data["inventory_info"]:
                msg += f"📦 **Inventory:** {stock_data['inventory_info']}\n"
                
            msg += (
                f"🔗 {url}\n"
                "❌ **All flavors/variants are OUT OF STOCK**"
            )
        
        await interaction.followup.send(msg)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ **Error checking URL:** {str(e)}\n"
            f"Make sure the URL is a valid product page from a supported site.",
            ephemeral=True
        )

@bot.tree.command(name="listcustom", description="List all custom products being monitored")
async def listcustom(interaction: discord.Interaction):
    custom_products = []
    for key, product in PRODUCTS.items():
        if product.get("is_custom", False):
            site_emoji = "🌐" if product.get("site") == "drsmoke" else "🔥"
            custom_products.append(
                f"• **{product['name']}**\n"
                f"  {site_emoji} {product.get('site', 'unknown').title()}\n"
                f"  🔗 {product['url']}\n"
                f"  🆔 `{key}`"
            )
    
    if custom_products:
        msg = "**Custom Products Being Monitored:**\n\n" + "\n\n".join(custom_products)
    else:
        msg = "No custom products are being monitored yet. Use `/addurl` to add one."
    
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="removeurl", description="Remove a custom product from monitoring")
@app_commands.describe(product_id="The product ID to remove (use /listcustom to see IDs)")
async def removeurl(interaction: discord.Interaction, product_id: str):
    if product_id in PRODUCTS and PRODUCTS[product_id].get("is_custom", False):
        product_name = PRODUCTS[product_id]["name"]
        del PRODUCTS[product_id]
        save_custom_products()
        
        await interaction.response.send_message(
            f"✅ **Removed:** {product_name} is no longer being monitored.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ **Not found:** No custom product with ID `{product_id}`.\n"
            f"Use `/listcustom` to see available IDs.",
            ephemeral=True
        )

@bot.tree.command(name="help", description="Show commands")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Commands**\n"
        "/stock – Check pre-defined product stock\n"
        "/stockurl – Check stock for any supported URL\n"
        "/addurl – Add a new product URL to monitor\n"
        "/listcustom – List all custom products being monitored\n"
        "/removeurl – Remove a custom product from monitoring\n"
        "/sync – Sync commands (Owner only)\n"
        "/help – Show this menu\n\n"
        "**Supported Sites:**\n"
        "• vaporhatch.com\n"
        "• drsmoke.com",
        ephemeral=True
    )

# ==========================
# START BOT
# ==========================

if __name__ == "__main__":
    # IMPORTANT: Replace with your Discord User ID
    print("WARNING: Please replace OWNER_ID with your Discord User ID!")
    print("Find your Discord ID: User Settings → Advanced → Developer Mode ON → Right-click your profile → Copy ID")
    
    if OWNER_ID == 123456789012345678:
        print("\n❌ ERROR: You must replace OWNER_ID with your actual Discord User ID!")
        print("The bot will still run, but /sync command won't work.")
    
    bot.run(TOKEN)
