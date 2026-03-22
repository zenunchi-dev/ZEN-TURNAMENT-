import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import asyncio
import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont

# === 1. SERVER PENTRU RAILWAY (KEEP ALIVE) ===
# Rezolvă eroarea de pornire prin folosirea corectă a @app.route
app = Flask('')

@app.route('/')
def home(): 
    return "ZEN Bot is Running"

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# === 2. CONFIGURARE BOT ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# ID-uri extrase din cerințele tale
TICKET_CATEGORY_ID      = 1481418592217206885
STAFF_ROLE_ID           = 1466541122636611759 
ACCEPT_ROLE_ID          = 1484534027342974976
REJECT_ROLE_ID          = 1481789988654940272
CHANNEL_BRACKET_ID      = 1481418744956850392 

IMAGE_URL = "https://cdn.discordapp.com/attachments/1481418744956850392/1485083252065570917/file_00000000a92c720aaca2f08e5e197849.png"
FONT_URL = "https://github.com/googlefonts/rajdhani/raw/main/fonts/Rajdhani-Bold.ttf"

last_bracket_message_id = None
bracket_data = {slot: "" for slot in ["A1","A2","A3","A4","B1","B2","B3","B4","SW1","SW2","SW3","SW4","F1","F2"]}

# Coordonate calibrate pentru centrare perfectă
positions = {
    "A1": (132, 245), "A2": (132, 335), "A3": (132, 492), "A4": (132, 582),
    "B1": (868, 245), "B2": (868, 335), "B3": (868, 492), "B4": (868, 582),
    "SW1": (285, 290), "SW2": (285, 537), "SW3": (715, 290), "SW4": (715, 537),
    "F1": (445, 415), "F2": (555, 415)
}

# === 3. LOGICĂ IMAGINE (RADIERĂ + FONT 45) ===
# Rezolvă problema suprapunerii peste "Echipa X"
async def generate_bracket_image():
    async with aiohttp.ClientSession() as session:
        async with session.get(IMAGE_URL) as resp:
            if resp.status != 200: return None
            img = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
        async with session.get(FONT_URL) as resp_f:
            # Mărime font 45 pentru vizibilitate maximă
            font = ImageFont.truetype(io.BytesIO(await resp_f.read()), 45) if resp_f.status == 200 else ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    for slot, team in bracket_data.items():
        if team:
            x, y = positions[slot]
            # RADIERA: Acoperă textul vechi cu culoarea fundalului
            draw.rectangle([x - 90, y - 30, x + 90, y + 30], fill="#F8F8F8")
            
            text = str(team).upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            # Centrare pe axele X și Y
            draw.text((x - w//2, y - h//2 - 5), text, fill="black", font=font)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def update_bracket_msg(ctx):
    global last_bracket_message_id
    channel = bot.get_channel(CHANNEL_BRACKET_ID)
    if not channel: return

    file_data = await generate_bracket_image()
    if file_data:
        if last_bracket_message_id:
            try:
                old_msg = await channel.fetch_message(last_bracket_message_id)
                await old_msg.delete()
            except: pass
        new_msg = await channel.send(file=discord.File(file_data, "bracket.png"))
        last_bracket_message_id = new_msg.id
    try: await ctx.message.delete()
    except: pass

# === 4. SISTEM TICKET (ACCEPT/REJECT) ===
# Implementează logica cerută pentru gestionarea membrilor
class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="ACCEPTAT", style=discord.ButtonStyle.success, emoji="✅", custom_id="zen_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles): return
        member = interaction.guild.get_member(int(interaction.channel.topic))
        rol = interaction.guild.get_role(ACCEPT_ROLE_ID)
        if rol and member: await member.add_roles(rol)
        await interaction.response.send_message(f"✅ {member.mention} a fost acceptat!")

    @discord.ui.button(label="REJECTAT", style=discord.ButtonStyle.danger, emoji="❌", custom_id="zen_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles): return
        member = interaction.guild.get_member(int(interaction.channel.topic))
        rol = interaction.guild.get_role(REJECT_ROLE_ID)
        if rol and member: await member.add_roles(rol)
        await interaction.response.send_message(f"❌ {member.mention} a fost respins!")

    @discord.ui.button(label="Închide", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="zen_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles): return
        await interaction.response.send_message("Se închide...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

class InscriereView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="ÎNSCRIE-TE", style=discord.ButtonStyle.success, emoji="🏆", custom_id="zen_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(r.id == REJECT_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Ești blocat!", ephemeral=True)
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        ch = await guild.create_text_channel(f"ticket-{interaction.user.name}", category=category, topic=str(interaction.user.id), overwrites=overwrites)
        await ch.send(f"{interaction.user.mention} completează formularul!", view=TicketControlView())
        await interaction.response.send_message(f"Ticket creat: {ch.mention}", ephemeral=True)

# === 5. COMENZI STAFF ===
@bot.command()
async def setup_inscrieri(ctx):
    if any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
        await ctx.send("Apasă pentru înscriere:", view=InscriereView())

@bot.command()
async def set(ctx, slot: str, *, name: str):
    if any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
        slot = slot.upper()
        if slot in positions:
            bracket_data[slot] = name
            await update_bracket_msg(ctx)

@bot.command()
async def win(ctx, slot: str):
    if any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
        slot = slot.upper()
        mapping = {"A1":"SW1", "A2":"SW1", "A3":"SW2", "A4":"SW2", "B1":"SW3", "B2":"SW3", "B3":"SW4", "B4":"SW4", "SW1":"F1", "SW2":"F1", "SW3":"F2", "SW4":"F2"}
        if slot in bracket_data and slot in mapping:
            bracket_data[mapping[slot]] = bracket_data[slot]
            await update_bracket_msg(ctx)

@bot.command()
async def reset(ctx):
    if any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
        for s in bracket_data: bracket_data[s] = ""
        await update_bracket_msg(ctx)

# === START ===
@bot.event
async def on_ready():
    print(f"ZEN Bot Online - Toate setările aplicate!")
    bot.add_view(InscriereView())
    bot.add_view(TicketControlView())
    keep_alive()

bot.run(os.getenv("DISCORD_TOKEN"))
