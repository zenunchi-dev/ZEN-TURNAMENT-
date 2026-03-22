import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import asyncio
import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont

# === SERVER PENTRU RAILWAY ===
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
STAFF_ROLE_ID           = 1466541122636611759  # Singurul rol care poate folosi comenzile
ACCEPT_ROLE_ID          = 1484534027342974976
REJECT_ROLE_ID          = 1481789988654940272
CHANNEL_BRACKET_ID      = 1481418744956850392 

# URL Imagine și Font
IMAGE_URL = "https://cdn.discordapp.com/attachments/1481418744956850392/1485083252065570917/file_00000000a92c720aaca2f08e5e197849.png"
FONT_URL = "https://github.com/googlefonts/rajdhani/raw/main/fonts/Rajdhani-Bold.ttf"

# Coordonate ajustate pentru a acoperi textul "Echipa X" de pe imagine
positions = {
    "A1": (125, 245), "A2": (125, 335), "A3": (125, 492), "A4": (125, 582),
    "B1": (875, 245), "B2": (875, 335), "B3": (875, 492), "B4": (875, 582),
    "SW1": (285, 290), "SW2": (285, 537), "SW3": (715, 290), "SW4": (715, 537),
    "F1": (445, 415), "F2": (555, 415),
    # Listele de jos (Grupa A / Grupa B)
    "L_A1": (410, 755), "L_A2": (410, 788), "L_A3": (410, 821), "L_A4": (410, 854),
    "L_B1": (620, 755), "L_B2": (620, 788), "L_B3": (620, 821), "L_B4": (620, 854)
}

bracket_data = {slot: "" for slot in positions.keys()}
last_bracket_msg_id = None # Memorează ID-ul ultimului mesaj trimis

# ================= LOGICĂ IMAGINE =================

async def generate_bracket_image():
    async with aiohttp.ClientSession() as session:
        async with session.get(IMAGE_URL) as resp:
            if resp.status != 200: return None
            img_data = await resp.read()
            img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        async with session.get(FONT_URL) as resp_f:
            font = ImageFont.truetype(io.BytesIO(await resp_f.read()), 22) if resp_f.status == 200 else ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    
    # Desenăm peste locurile marcate
    for slot, team in bracket_data.items():
        if team:
            text = str(team).upper()
            x, y = positions[slot]
            
            # Acoperim textul vechi cu un mic dreptunghi alb (opțional, dar recomandat)
            # draw.rectangle([x-50, y-10, x+50, y+10], fill="white")
            
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((x - w//2, y - h//2), text, fill="black", font=font)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def update_bracket_msg(ctx):
    global last_bracket_msg_id
    channel = bot.get_channel(CHANNEL_BRACKET_ID)
    if not channel: return

    # Ștergem mesajul vechi dacă există
    if last_bracket_msg_id:
        try:
            old_msg = await channel.fetch_message(last_bracket_msg_id)
            await old_msg.delete()
        except: pass

    file = await generate_bracket_image()
    if file:
        new_msg = await channel.send(file=discord.File(file, "zen_bracket.png"))
        last_bracket_msg_id = new_msg.id

# ================= CHECK STAFF =================

def is_staff():
    async def predicate(ctx):
        has_role = any(r.id == STAFF_ROLE_ID for r in ctx.author.roles)
        if not has_role:
            await ctx.send("❌ Nu ai permisiunea de a folosi această comandă!", delete_after=5)
        return has_role
    return commands.check(predicate)

# ================= VIEW-URI TICKET (Neschimbate) =================

class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="ACCEPTAT", style=discord.ButtonStyle.success, emoji="✅", custom_id="zen_accept_ticket")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles): return
        user_id = interaction.channel.topic
        member = interaction.guild.get_member(int(user_id))
        rol = interaction.guild.get_role(ACCEPT_ROLE_ID)
        if rol and member: await member.add_roles(rol)
        await interaction.response.send_message(f"Acceptat de {interaction.user.mention}")

    @discord.ui.button(label="REJECTAT", style=discord.ButtonStyle.danger, emoji="❌", custom_id="zen_reject_ticket")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles): return
        user_id = interaction.channel.topic
        member = interaction.guild.get_member(int(user_id))
        rol = interaction.guild.get_role(REJECT_ROLE_ID)
        if rol and member: await member.add_roles(rol)
        await interaction.response.send_message(f"Respins de {interaction.user.mention}")

    @discord.ui.button(label="Închide Ticket", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="zen_close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles): return
        await interaction.channel.delete()

class InscriereButtonView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, emoji="🏆", custom_id="zen_inscriere_2v2")
    async def inscriere(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        channel = await guild.create_text_channel(name=f"ticket-{interaction.user.name}", category=category, topic=str(interaction.user.id), overwrites=overwrites)
        await channel.send(f"{interaction.user.mention}\nÎnscriere ZEN 2v2 - Completează datele echipei.", view=TicketControlView())
        await interaction.response.send_message(f"Ticket creat: {channel.mention}", ephemeral=True)

# ================= COMENZI TABELĂ (DOAR STAFF) =================

@bot.command()
@is_staff()
async def setup_inscrieri(ctx):
    await ctx.send(embed=discord.Embed(title="ZEN Tournament", description="Apasă 🏆 pentru înscriere"), view=InscriereButtonView())

@bot.command()
@is_staff()
async def set(ctx, slot: str, *, name: str):
    slot = slot.upper()
    if slot in positions:
        bracket_data[slot] = name
        # Dacă setăm baza (A1-B4), punem numele și în lista de jos
        if slot.startswith(("A", "B")) and len(slot) == 2:
            list_slot = f"L_{slot}"
            bracket_data[list_slot] = name
            
        await update_bracket_msg(ctx)
        await ctx.message.delete()
    else:
        await ctx.send("❌ Slot invalid!", delete_after=3)

@bot.command()
@is_staff()
async def win(ctx, slot: str):
    slot = slot.upper()
    mapping = {
        "A1":"SW1", "A2":"SW1", "A3":"SW2", "A4":"SW2",
        "B1":"SW3", "B2":"SW3", "B3":"SW4", "B4":"SW4",
        "SW1":"F1", "SW2":"F1", "SW3":"F2", "SW4":"F2"
    }
    if slot in bracket_data and slot in mapping:
        target = mapping[slot]
        bracket_data[target] = bracket_data[slot]
        await update_bracket_msg(ctx)
        await ctx.message.delete()

@bot.command()
@is_staff()
async def reset(ctx):
    global bracket_data
    bracket_data = {slot: "" for slot in positions.keys()}
    await update_bracket_msg(ctx)
    await ctx.send("🧹 Bracket resetat!", delete_after=5)

@bot.event
async def on_ready():
    bot.add_view(InscriereButtonView())
    bot.add_view(TicketControlView())
    keep_alive()
    print("Botul este gata!")

bot.run(os.getenv("DISCORD_TOKEN"))
