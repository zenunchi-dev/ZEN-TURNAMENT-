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

# === ID-URI TICKET & ROLURI (Păstrate exact ca ale tale) ===
TICKET_CATEGORY_ID      = 1481418592217206885
STAFF_ROLE_ID           = 1466541122636611759
ACCEPT_ROLE_ID          = 1484534027342974976
REJECT_ROLE_ID          = 1481789988654940272

# === CONFIG TABELĂ / BRACKET (Imagine) ===
# ID-ul canalului unde se trimite tabela (din conversația anterioară)
CHANNEL_BRACKET_ID = 1481418744956850392 
IMAGE_URL = "https://cdn.discordapp.com/attachments/1481418744956850392/1485083252065570917/file_00000000a92c720aaca2f08e5e197849.png?ex=69c0930e&is=69bf418e&hm=7f1202378fea409ea82d2639aa811eda500b535128bf529a51dc126d29db74c9&"
FONT_URL = "https://github.com/googlefonts/rajdhani/raw/main/fonts/Rajdhani-Bold.ttf"

# Coordonate calibrate pentru TOATE sloturile (A și B)
positions = {
    # Grupa A (Stânga)
    "A1": (245, 410), "A2": (245, 485),
    "A3": (245, 620), "A4": (245, 695),
    # Grupa B (Dreapta)
    "B1": (865, 410), "B2": (865, 485),
    "B3": (865, 620), "B4": (865, 695),
    # Semifinale (Mijloc)
    "SW1": (390, 448), "SW2": (390, 658), # Câștigători A
    "SW3": (720, 448), "SW4": (720, 658), # Câștigători B
    # Finala (Centru - pastile mici)
    "F1": (530, 553), "F2": (580, 553)
}

# Structură internă date turneu
bracket_data = {slot: "" for slot in positions.keys()}

# Model formular înscriere (Păstrat)
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
        # Descărcăm imaginea de bază
        async with session.get(IMAGE_URL) as resp:
            if resp.status != 200: return None
            img_data = await resp.read()
            img = Image.open(io.BytesIO(img_data)).convert("RGBA")

        # Descărcăm font-ul discret Rajdhani (gaming look)
        async with session.get(FONT_URL) as resp_font:
            font = ImageFont.truetype(io.BytesIO(await resp_font.read()), 22) if resp_font.status == 200 else ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    for slot, team in bracket_data.items():
        if team:
            text = str(team).upper() # Majuscule
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            # Desenăm textul centrat matematic pe pastilă
            draw.text((positions[slot][0] - w//2, positions[slot][1] - h//2), text, fill="black", font=font)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

# ================= VIEW-URI TICKET (Păstrate intacte) =================

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
            await asyncio.sleep(24 * 3600)
            try: await member.remove_roles(rol)
            except: pass
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
            await asyncio.sleep(24 * 3600)
            try: await member.remove_roles(rol)
            except: pass
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

# ================= COMENZI UNIFICATE (Ticket + Bracket) =================

@bot.command()
async def setup_inscrieri(ctx):
    """(Staff/Owner) Creează panoul cu buton de înscriere."""
    if ctx.author.id != 1466541122636611759 and not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
        return await ctx.send("Doar staff/owner poate seta mesajul cu buton.")
    embed = discord.Embed(title="ZEN Tournament 2v2", description="Apasă butonul🏆 pentru a te înscrie în turneu.", color=0x00ff00)
    await ctx.send(embed=embed, view=InscriereButtonView())
    await ctx.send("Mesaj cu buton creat!")

@bot.command()
async def set(ctx, slot: str, *, name: str):
    """Setează o echipă în bracket (Ex: #set A1 TeamAlpha)"""
    slot = slot.upper()
    if slot in ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4"]:
        bracket_data[slot] = name
        file = await generate_bracket_image()
        await ctx.send(f"✅ Slot {slot} setat cu **{name}**!", file=discord.File(file, "bracket.png"))
    else:
        await ctx.send("❌ Slot invalid! Folosește A1-A4 sau B1-B4.")

@bot.command()
async def win(ctx, slot: str):
    """Avansează echipa dintr-un slot (Ex: #win A1)"""
    slot = slot.upper()
    # Logica de avansare automată pentru TOATE meciurile (Grupa A și Grupa B)
    mapping = {
        # Grupa A
        "A1":"SW1", "A2":"SW1", "A3":"SW2", "A4":"SW2",
        # Grupa B
        "B1":"SW3", "B2":"SW3", "B3":"SW4", "B4":"SW4",
        # Finaliști (Din semifinale spre Finală)
        "SW1":"F1", "SW2":"F1", "SW3":"F2", "SW4":"F2"
    }
    if slot in bracket_data and bracket_data[slot] and slot in mapping:
        target = mapping[slot]
        bracket_data[target] = bracket_data[slot]
        file = await generate_bracket_image()
        await ctx.send(f"🏆 **{bracket_data[slot]}** a câștigat și avansează!", file=discord.File(file, "bracket.png"))
    else:
        await ctx.send("❌ Slot invalid sau gol (Finala nu avansează).")

@bot.command()
async def reset(ctx):
    """Resetează tabelul turneului."""
    global bracket_data
    bracket_data = {slot: "" for slot in positions.keys()}
    await ctx.send("🧹 Bracket resetat.")

@bot.event
async def on_ready():
    print(f"{bot.user} → Online | Prefix: #")
    bot.add_view(InscriereButtonView())
    bot.add_view(TicketControlView())
    keep_alive()

bot.run(os.getenv("DISCORD_TOKEN"))
