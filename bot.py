import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import asyncio
import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont

# === SERVER PENTRU RAILWAY (Keep Alive) ===
app = Flask('')
@app.route('/')
def home(): return "Bot Online"
def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# === CONFIG BOT UNIFICAT ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# === ID-URI TICKET & ROLURI ===
TICKET_CATEGORY_ID      = 1481418592217206885
STAFF_ROLE_ID           = 1466541122636611759 
ACCEPT_ROLE_ID          = 1484534027342974976
REJECT_ROLE_ID          = 1481789988654940272

# === CONFIG TABELĂ / BRACKET ===
CHANNEL_BRACKET_ID = 1481418744956850392 
IMAGE_URL = "https://cdn.discordapp.com/attachments/1481418744956850392/1485083252065570917/file_00000000a92c720aaca2f08e5e197849.png?ex=69c0930e&is=69bf418e&hm=7f1202378fea409ea82d2639aa811eda500b535128bf529a51dc126d29db74c9&"
FONT_URL = "https://github.com/googlefonts/rajdhani/raw/main/fonts/Rajdhani-Bold.ttf"

last_bracket_message_id = None

# Coordonate și dimensiuni zone de acoperire (Centru X, Centru Y)
positions = {
    "A1": (132, 245), "A2": (132, 335), "A3": (132, 492), "A4": (132, 582),
    "B1": (868, 245), "B2": (868, 335), "B3": (868, 492), "B4": (868, 582),
    "SW1": (285, 290), "SW2": (285, 537), "SW3": (715, 290), "SW4": (715, 537),
    "F1": (445, 415), "F2": (555, 415)
}

bracket_data = {slot: "" for slot in positions.keys()}

MODEL_INSCRIERE = """
**Înscriere ZEN 2v2**

**Echipă:** (________________)

**Juc. 1** Nick/ID: (_______________)  
Profil: (_______________)  
Discord: (_______________)

**Juc. 2** Nick/ID: (_______________)  
Profil: (_______________)  
Discord: (_______________)

(Trimite formularul completat mai jos)
"""

# ================= LOGICĂ IMAGINE TABELĂ =================

async def generate_bracket_image():
    async with aiohttp.ClientSession() as session:
        async with session.get(IMAGE_URL) as resp:
            if resp.status != 200: return None
            img_data = await resp.read()
            img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        async with session.get(FONT_URL) as resp_font:
            # Am mărit fontul la 28 pentru a fi "la fel de mare"
            font = ImageFont.truetype(io.BytesIO(await resp_font.read()), 28) if resp_font.status == 200 else ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    
    for slot, team in bracket_data.items():
        if team:
            x, y = positions[slot]
            # 1. Desenăm un dreptunghi alb pentru a "șterge" textul original (Echipa A1, etc.)
            # Dimensiunea dreptunghiului este adaptată zonei de text din imagine
            left, top, right, bottom = x - 55, y - 15, x + 55, y + 15
            draw.rectangle([left, top, right, bottom], fill="#F8F8F8") # Culoarea fundalului din imagine
            
            # 2. Scriem noul nume de echipă
            text = str(team).upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((x - w//2, y - h//2 - 2), text, fill="black", font=font)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def send_updated_bracket(ctx):
    global last_bracket_message_id
    channel = bot.get_channel(CHANNEL_BRACKET_ID)
    if not channel: return

    if last_bracket_message_id:
        try:
            old_msg = await channel.fetch_message(last_bracket_message_id)
            await old_msg.delete()
        except: pass

    file_data = await generate_bracket_image()
    if file_data:
        new_msg = await channel.send(file=discord.File(file_data, "bracket.png"))
        last_bracket_message_id = new_msg.id
    
    try: await ctx.message.delete()
    except: pass

# ================= VIEW-URI TICKET =================

class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="ACCEPTAT", style=discord.ButtonStyle.success, emoji="✅", custom_id="zen_accept_ticket")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff-ul poate folosi acest buton!", ephemeral=True)
        user_id = interaction.channel.topic
        if not user_id: return
        member = interaction.guild.get_member(int(user_id))
        rol = interaction.guild.get_role(ACCEPT_ROLE_ID)
        if rol and member:
            await member.add_roles(rol)
            await interaction.response.send_message(f"{interaction.user.mention} a **acceptat** participantul {member.mention}! Rol acordat.")
        await interaction.response.defer()

    @discord.ui.button(label="REJECTAT", style=discord.ButtonStyle.danger, emoji="❌", custom_id="zen_reject_ticket")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff-ul poate folosi acest buton!", ephemeral=True)
        user_id = interaction.channel.topic
        if not user_id: return
        member = interaction.guild.get_member(int(user_id))
        rol = interaction.guild.get_role(REJECT_ROLE_ID)
        if rol and member:
            await member.add_roles(rol)
            await interaction.response.send_message(f"{interaction.user.mention} a **respins** participantul {member.mention}! Rol acordat.")
        await interaction.response.defer()

    @discord.ui.button(label="Închide Ticket", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="zen_close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff-ul poate închide ticket-ul!", ephemeral=True)
        await interaction.response.send_message("Ticket-ul se închide în 5 secunde...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class InscriereButtonView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, emoji="🏆", custom_id="zen_inscriere_2v2")
    async def inscriere(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(r.id == REJECT_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Ai fost respins recent și nu poți crea ticket nou.", ephemeral=True)
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category: return await interaction.response.send_message("Categoria de tickete nu a fost găsită!", ephemeral=True)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
        }
        channel = await guild.create_text_channel(name=f"ticket-{interaction.user.name}", category=category, topic=str(interaction.user.id), overwrites=overwrites)
        await channel.send(f"{interaction.user.mention}\n\n{MODEL_INSCRIERE}", view=TicketControlView())
        await interaction.response.send_message(f"Ticket-ul tău a fost creat: {channel.mention}", ephemeral=True)

# ================= COMENZI STAFF =================

@bot.command()
async def setup_inscrieri(ctx):
    if not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles): return
    embed = discord.Embed(title="ZEN Tournament 2v2", description="Apasă butonul🏆 pentru a te înscrie.", color=0x00ff00)
    await ctx.send(embed=embed, view=InscriereButtonView())

@bot.command()
async def set(ctx, slot: str, *, name: str):
    if not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles): return
    slot = slot.upper()
    if slot in positions:
        bracket_data[slot] = name
        await send_updated_bracket(ctx)

@bot.command()
async def win(ctx, slot: str):
    if not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles): return
    slot = slot.upper()
    mapping = {
        "A1":"SW1", "A2":"SW1", "A3":"SW2", "A4":"SW2",
        "B1":"SW3", "B2":"SW3", "B3":"SW4", "B4":"SW4",
        "SW1":"F1", "SW2":"F1", "SW3":"F2", "SW4":"F2"
    }
    if slot in bracket_data and bracket_data[slot] and slot in mapping:
        bracket_data[mapping[slot]] = bracket_data[slot]
        await send_updated_bracket(ctx)

@bot.command()
async def reset(ctx):
    if not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles): return
    global bracket_data
    bracket_data = {slot: "" for slot in positions.keys()}
    await send_updated_bracket(ctx)

@bot.event
async def on_ready():
    print(f"{bot.user} → Online")
    bot.add_view(InscriereButtonView())
    bot.add_view(TicketControlView())
    keep_alive()

bot.run(os.getenv("DISCORD_TOKEN"))
