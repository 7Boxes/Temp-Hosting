import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import difflib
import random
import re
from typing import Literal, Optional

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration
CONFIG_FILE = "bot_config.json"
DEFAULT_CONFIG = {
    "report_channel": None,
    "embed_color": 0x3498db,
    "admin_roles": []
}

# Load pet data
def load_pet_data():
    try:
        with open("/storage/emulated/0/Download/Place_85896571713843_Script_1750291259.txt", "r", encoding="utf-8") as f:
            content = f.read()
            # Extract the Lua table part
            start = content.find("{")
            end = content.rfind("}") + 1
            lua_table = content[start:end]
            
            # Convert Lua table to Python dict
            pets = {}
            pet_entries = [e.strip() for e in lua_table.split("\n") if "=" in e]
            
            for entry in pet_entries:
                if not entry.strip():
                    continue
                    
                # Split name and data
                name_part, data_part = entry.split("=", 1)
                name = name_part.strip().strip('"').strip("'").strip("[").strip("]").strip()
                
                # Parse the PetBuilder chain
                pet_data = {
                    "name": name,
                    "rarity": "Common",
                    "stats": {},
                    "images": [],
                    "limited": False,
                    "tags": []
                }
                
                # Process each method call
                methods = [m.strip() for m in data_part.split(":") if m.strip()]
                for method in methods[1:]:  # Skip the initial new()
                    if "(" in method:
                        method_name = method.split("(")[0]
                        args_part = method.split("(")[1].split(")")[0]
                        args = [a.strip().strip('"').strip("'") for a in args_part.split(",") if a.strip()]
                        
                        if method_name == "Rarity":
                            pet_data["rarity"] = args[0]
                        elif method_name == "Stat":
                            stat_name = args[0]
                            stat_value = float(args[1]) if "." in args[1] else int(args[1])
                            pet_data["stats"][stat_name] = stat_value
                        elif method_name == "Image":
                            pet_data["images"] = args
                        elif method_name == "Limited":
                            pet_data["limited"] = True
                        elif method_name == "Tag":
                            pet_data["tags"].extend([tag.strip('"').strip("'") for tag in args])
                        elif method_name == "HideInTerminal":
                            pet_data["hide_in_terminal"] = True
                
                pets[name] = pet_data
                
            return pets
    except Exception as e:
        print(f"Error loading pet data: {e}")
        return {}

# Load config
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return DEFAULT_CONFIG.copy()

# Save config
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# Global variables
pet_data = load_pet_data()
config = load_config()

# Helper functions
def get_embed(title="", description="", color=None):
    if color is None:
        color = config.get("embed_color", 0x3498db)
    embed = discord.Embed(title=title, description=description, color=color)
    if random.random() < 0.01:  # 1% chance
        embed.set_footer(text="made by jajtxs_")
    return embed

def is_admin(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
        return True
    admin_roles = config.get("admin_roles", [])
    return any(role.id in admin_roles for role in interaction.user.roles)

def fuzzy_search(query, choices, cutoff=0.6):
    results = []
    for choice in choices:
        ratio = difflib.SequenceMatcher(None, query.lower(), choice.lower()).ratio()
        if ratio >= cutoff:
            results.append((choice, ratio))
    results.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in results]

def get_pet_variants(pet_name):
    variants = {
        "Normal": None,
        "Shiny": None,
        "Mythic": None,
        "Shiny Mythic": None
    }
    
    pet = pet_data.get(pet_name)
    if not pet or not pet.get("images"):
        return variants
    
    images = pet["images"]
    if len(images) >= 1:
        variants["Normal"] = f"https://ps99.biggamesapi.io/image/{images[0].replace('rbxassetid://', '')}"
    if len(images) >= 2:
        variants["Shiny"] = f"https://ps99.biggamesapi.io/image/{images[1].replace('rbxassetid://', '')}"
    if len(images) >= 3:
        variants["Mythic"] = f"https://ps99.biggamesapi.io/image/{images[2].replace('rbxassetid://', '')}"
    if len(images) >= 4:
        variants["Shiny Mythic"] = f"https://ps99.biggamesapi.io/image/{images[3].replace('rbxassetid://', '')}"
    
    return variants

# Commands
@bot.tree.command(name="top", description="Show top pets by stat")
@app_commands.describe(stat="Which stat to sort by")
async def top(interaction: discord.Interaction, stat: Literal["Bubbles", "Coins", "Gems", "Tickets"]):
    # Filter pets that have the selected stat
    valid_pets = [pet for pet in pet_data.values() if stat in pet["stats"]]
    
    if not valid_pets:
        await interaction.response.send_message(embed=get_embed("Error", f"No pets found with {stat} stat."))
        return
    
    # Sort by the stat (descending)
    sorted_pets = sorted(valid_pets, key=lambda x: x["stats"][stat], reverse=True)
    
    # Create pages
    pages = []
    for i in range(0, len(sorted_pets), 10):
        page_pets = sorted_pets[i:i+10]
        description = "\n".join(
            f"**{idx + i + 1}.** {pet['name']} - {pet['stats'][stat]:,} {stat} ({pet['rarity']})"
            for idx, pet in enumerate(page_pets)
        )
        pages.append(get_embed(f"Top Pets by {stat}", description))
    
    if not pages:
        await interaction.response.send_message(embed=get_embed("Error", "No pets found."))
        return
    
    # Send first page with navigation
    await interaction.response.send_message(embed=pages[0], view=PaginatorView(pages))

@bot.tree.command(name="fuzzy", description="Fuzzy search for pets")
@app_commands.describe(query="Search term")
async def fuzzy(interaction: discord.Interaction, query: str):
    pet_names = list(pet_data.keys())
    results = fuzzy_search(query, pet_names)
    
    if not results:
        await interaction.response.send_message(embed=get_embed("No Results", "No pets matched your search."))
        return
    
    # Create pages
    pages = []
    for i in range(0, min(50, len(results)), 10):
        page_pets = results[i:i+10]
        description = "\n".join(
            f"**{idx + i + 1}.** {name}" 
            for idx, name in enumerate(page_pets)
        )
        pages.append(get_embed(f"Fuzzy Search Results for '{query}'", description))
    
    await interaction.response.send_message(embed=pages[0], view=PaginatorView(pages))

@bot.tree.command(name="search", description="Search pets by attribute")
@app_commands.describe(
    attribute="Attribute to search by",
    query="Value to search for"
)
async def search(
    interaction: discord.Interaction, 
    attribute: Literal["rarity", "stats", "tag", "limited"], 
    query: str
):
    results = []
    
    for pet in pet_data.values():
        if attribute == "rarity":
            if query.lower() == pet["rarity"].lower():
                results.append(pet)
        elif attribute == "stats":
            if query in pet["stats"]:
                results.append(pet)
        elif attribute == "tag":
            if any(query.lower() == tag.lower() for tag in pet.get("tags", [])):
                results.append(pet)
        elif attribute == "limited":
            if pet["limited"]:
                results.append(pet)
    
    if not results:
        await interaction.response.send_message(embed=get_embed("No Results", "No pets matched your search."))
        return
    
    # Create pages
    pages = []
    for i in range(0, len(results), 10):
        page_pets = results[i:i+10]
        description = "\n".join(
            f"**{pet['name']}** ({pet['rarity']})" + 
            (f" - Tags: {', '.join(pet['tags'])}" if pet.get('tags') else "") +
            (f" - Limited" if pet['limited'] else "")
            for pet in page_pets
        )
        pages.append(get_embed(f"Pets with {attribute} matching '{query}'", description))
    
    await interaction.response.send_message(embed=pages[0], view=PaginatorView(pages))

@bot.tree.command(name="view", description="View details and images for a pet")
@app_commands.describe(pet_name="Name of the pet to view")
async def view(interaction: discord.Interaction, pet_name: str):
    pet = pet_data.get(pet_name)
    if not pet:
        # Try fuzzy match
        matches = fuzzy_search(pet_name, list(pet_data.keys()))
        if matches:
            pet = pet_data[matches[0]]
            pet_name = matches[0]  # Use the matched name
    
    if not pet:
        await interaction.response.send_message(embed=get_embed("Error", f"Pet '{pet_name}' not found."))
        return
    
    # Send stats first
    stats_desc = "\n".join(f"{stat}: {value:,}" for stat, value in pet["stats"].items())
    stats_embed = get_embed(
        f"{pet_name} ({pet['rarity']})",
        f"**Stats:**\n{stats_desc}\n\n" +
        (f"**Tags:** {', '.join(pet['tags'])}\n" if pet.get('tags') else "") +
        ("**Limited**" if pet['limited'] else "")
    )
    
    if pet.get("images"):
        variants = get_pet_variants(pet_name)
        if variants["Normal"]:
            stats_embed.set_thumbnail(url=variants["Normal"])
    
    await interaction.response.send_message(embed=stats_embed)
    
    # Send each variant image in separate messages
    if pet.get("images"):
        variants = get_pet_variants(pet_name)
        for variant, url in variants.items():
            if url:
                embed = get_embed(f"{pet_name} - {variant}", "")
                embed.set_thumbnail(url=url)
                await interaction.followup.send(embed=embed)

@bot.tree.command(name="report", description="Report incorrect data")
@app_commands.describe(
    pet_name="Name of the pet with incorrect data",
    issue="Description of the issue"
)
async def report(interaction: discord.Interaction, pet_name: str, issue: str):
    report_channel_id = config.get("report_channel")
    if not report_channel_id:
        await interaction.response.send_message(
            embed=get_embed("Error", "Report channel not set up. Ask an admin to run /setup."),
            ephemeral=True
        )
        return
    
    report_channel = bot.get_channel(report_channel_id)
    if not report_channel:
        await interaction.response.send_message(
            embed=get_embed("Error", "Report channel not found. Ask an admin to reconfigure."),
            ephemeral=True
        )
        return
    
    embed = get_embed(
        "Data Issue Report",
        f"**Pet:** {pet_name}\n"
        f"**Reported by:** {interaction.user.mention}\n"
        f"**Issue:** {issue}\n\n"
        "Please provide a screenshot of the correct data."
    )
    
    await report_channel.send(embed=embed)
    await interaction.response.send_message(
        embed=get_embed("Report Submitted", "Your report has been sent to the moderators."),
        ephemeral=True
    )

@bot.tree.command(name="setup", description="Set up the server (Admin only)")
async def setup(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            embed=get_embed("Error", "You need admin permissions to run this command."),
            ephemeral=True
        )
        return
    
    # Create channels if they don't exist
    guild = interaction.guild
    category = await guild.create_category("Pet Stats Bot")
    
    # Create report channel
    report_channel = await guild.create_text_channel(
        "bot-reports",
        category=category,
        topic="Channel for reporting incorrect pet data"
    )
    
    # Update config
    config["report_channel"] = report_channel.id
    save_config(config)
    
    await interaction.response.send_message(
        embed=get_embed("Setup Complete", f"Bot channels created. Reports will be sent to {report_channel.mention}.")
    )

@bot.tree.command(name="refresh", description="Reload pet data (Admin only)")
async def refresh(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            embed=get_embed("Error", "You need admin permissions to run this command."),
            ephemeral=True
        )
        return
    
    global pet_data
    pet_data = load_pet_data()
    await interaction.response.send_message(
        embed=get_embed("Data Refreshed", f"Reloaded data for {len(pet_data)} pets.")
    )

@bot.tree.command(name="customize", description="Customize bot settings (Admin only)")
@app_commands.describe(
    embed_color="Hex color for embeds (e.g., #3498db)",
    admin_role="Role to give bot admin permissions"
)
async def customize(
    interaction: discord.Interaction,
    embed_color: Optional[str] = None,
    admin_role: Optional[discord.Role] = None
):
    if not is_admin(interaction):
        await interaction.response.send_message(
            embed=get_embed("Error", "You need admin permissions to run this command."),
            ephemeral=True
        )
        return
    
    if embed_color:
        try:
            # Convert hex color to integer
            if embed_color.startswith("#"):
                embed_color = embed_color[1:]
            color = int(embed_color, 16)
            config["embed_color"] = color
        except ValueError:
            await interaction.response.send_message(
                embed=get_embed("Error", "Invalid color format. Use hex like #3498db."),
                ephemeral=True
            )
            return
    
    if admin_role:
        if "admin_roles" not in config:
            config["admin_roles"] = []
        if admin_role.id not in config["admin_roles"]:
            config["admin_roles"].append(admin_role.id)
    
    save_config(config)
    
    changes = []
    if embed_color:
        changes.append(f"Embed color set to #{hex(config['embed_color'])[2:].zfill(6)}")
    if admin_role:
        changes.append(f"Added {admin_role.mention} as admin role")
    
    if changes:
        await interaction.response.send_message(
            embed=get_embed("Settings Updated", "\n".join(changes))
    else:
        await interaction.response.send_message(
            embed=get_embed("No Changes", "No settings were updated."),
            ephemeral=True
        )

# Paginator View
class PaginatorView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.current_page = 0
        self.max_page = len(pages) - 1
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.max_page
        self.last_page.disabled = self.current_page == self.max_page
        self.page_num.label = f"Page {self.current_page + 1}/{len(self.pages)}"
    
    @discord.ui.button(label="<<", style=discord.ButtonStyle.grey)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="<", style=discord.ButtonStyle.grey)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.grey, disabled=True)
    async def page_num(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass
    
    @discord.ui.button(label=">", style=discord.ButtonStyle.grey)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.max_page, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.grey)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.max_page
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

# Bot events
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Run bot
if __name__ == "__main__":
    bot.run("MTM4NTA1NDE2OTkwMzE0MDk3NA.G5uhqt.yetf545NBnu1zFzIhAB28UHMBpPhBzSyZfHAps")  # Replace with your bot token
