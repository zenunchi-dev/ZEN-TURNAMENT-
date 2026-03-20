import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio
import os
import re

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

# === CONFIG ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# ID-URI (păstrate exact)
TICKET_CATEGORY_ID      = 1481418592217206885
TABEL_MECIURI_CH_ID     = 1481418744956850392 
STAFF_ROLE_ID           = 1466541122636611759
OWNER_ID                = 1466541122636611759
REJECT_ROLE_ID          = 1481789988654940272
ACCEPT_ROLE_ID          = 1484534027342974976
SPECIAL_USER_ID         = 810609759324471306

# Canalul care devine invizibil după 8 înscrieri
CANAL_INSCRIERI_ID      = 1481418649196560414

# Stare înscrieri + contor
inscrieri_deschise      = False
numar_inscrieri         = 0
MAX_INSCRIERI           = 8

# Model înscriere (neschimbat)
MODEL_INSCRIERE = """
**Înscriere ZEN 2v2**

**Echipă:** (________________)

**Juc. 1**  
Nick/ID: (_______________)  
Profil: (_______________)  
Discord: (_______________)

**Juc. 2**  
Nick/ID: (_______________)  
Profil: (_______________)  
Discord: (_______________)

(Trimite formularul completat mai jos)
"""

# ================= VIEWS (neschimbate) =================

class StaffTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff!", ephemeral=True)

        user = interaction.channel.topic
        if not user: return
        member = interaction.guild.get_member(int(user))

        rol_accept = interaction.guild.get_role(ACCEPT_ROLE_ID)
        if rol_accept and member:
            await member.add_roles(rol_accept)
            await interaction.response.send_message(f"Acceptat! Rol {rol_accept.name} acordat.")
            await asyncio.sleep(24 * 3600)
            try:
                await member.remove_roles(rol_accept)
            except:
                pass

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff!", ephemeral=True)

        user = interaction.channel.topic
        if not user: return
        member = interaction.guild.get_member(int(user))

        rol_reject = interaction.guild.get_role(REJECT_ROLE_ID)
        if rol_reject and member:
            await member.add_roles(rol_reject)
            await interaction.response.send_message(f"Respins! Rol {rol_reject.name} acordat.")
            await asyncio.sleep(24 * 3600)
            try:
                await member.remove_roles(rol_reject)
            except:
                pass

    @discord.ui.button(label="ÎNCHIDE", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff!", ephemeral=True)
        await interaction.response.send_message("Ticket închis în 5 secunde...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# ================= COMENZI + LOGICĂ ÎNSCRIERI =================

@bot.command()
async def ok(ctx):
    global inscrieri_deschise
    if ctx.author.id != OWNER_ID and not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
        return await ctx.send("Doar persoana autorizată poate folosi #ok.")

    inscrieri_deschise = not inscrieri_deschise
    status = "**DESCHISE**" if inscrieri_deschise else "**ÎNCHISE**"
    await ctx.send(f"Înscrierile sunt acum {status}.")

@bot.event
async def on_message(message):
    if message.author.bot: return
    await bot.process_commands(message)

    if not inscrieri_deschise:
        return

    if "ticket" not in message.content.lower():
        return

    global numar_inscrieri
    if numar_inscrieri >= MAX_INSCRIERI:
        await message.reply("Locurile s-au ocupat (maxim 8). Înscrieri închise.")
        
        # Facem canalul invizibil (nu ștergem)
        try:
            canal_inscrieri = message.guild.get_channel(CANAL_INSCRIERI_ID)
            if canal_inscrieri:
                # Deny view pentru toată lumea (@everyone)
                await canal_inscrieri.set_permissions(
                    message.guild.default_role,
                    overwrite=discord.PermissionOverwrite(view_channel=False)
                )
                # Dacă vrei să rămână vizibil doar pentru staff, adaugă asta:
                await canal_inscrieri.set_permissions(
                    message.guild.get_role(STAFF_ROLE_ID),
                    overwrite=discord.PermissionOverwrite(view_channel=True)
                )
                print(f"Canalul {CANAL_INSCRIERI_ID} a devenit invizibil după 8 înscrieri.")
        except Exception as e:
            print(f"Eroare la modificarea permisiunilor: {e}")
        return

    guild = message.guild
    category = guild.get_channel(TICKET_CATEGORY_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        message.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }

    channel = await guild.create_text_channel(
        name=f"ticket-{message.author.name}",
        category=category,
        topic=str(message.author.id),
        overwrites=overwrites
    )

    numar_inscrieri += 1

    await channel.send(
        f"{message.author.mention} – completează formularul de înscriere:",
        content=MODEL_INSCRIERE,
        view=StaffTicketView()
    )

    await message.reply(f"Ticket creat: {channel.mention}", delete_after=10)

@bot.event
async def on_ready():
    print(f"{bot.user} → Online | Prefix: #")
    keep_alive()

bot.run(os.getenv("DISCORD_TOKEN"))