import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
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

# ID-URI
TICKET_CATEGORY_ID      = 1481418592217206885
TABEL_MECIURI_CH_ID     = 1481418744956850392 
STAFF_ROLE_ID           = 1466541122636611759
OWNER_ID                = 1466541122636611759
REJECT_ROLE_ID          = 1481789988654940272
ACCEPT_ROLE_ID          = 1484534027342974976
CANAL_INSCRIERI_ID      = 1481418649196560414   # canalul unde pui mesajul cu buton

# Model formular
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

# ================= VIEWS =================

class StaffTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅", custom_id="zen_accept_ticket")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff!", ephemeral=True)

        user_id = interaction.channel.topic
        if not user_id: return
        member = interaction.guild.get_member(int(user_id))

        rol = interaction.guild.get_role(ACCEPT_ROLE_ID)
        if rol and member:
            await member.add_roles(rol)
            await interaction.response.send_message(f"Acceptat! Rol acordat – se elimină după 24h.")
            await asyncio.sleep(24 * 3600)
            try: await member.remove_roles(rol)
            except: pass

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, emoji="❌", custom_id="zen_reject_ticket")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff!", ephemeral=True)

        user_id = interaction.channel.topic
        if not user_id: return
        member = interaction.guild.get_member(int(user_id))

        rol = interaction.guild.get_role(REJECT_ROLE_ID)
        if rol and member:
            await member.add_roles(rol)
            await interaction.response.send_message(f"Respins! Rol acordat – se elimină după 24h.")
            await asyncio.sleep(24 * 3600)
            try: await member.remove_roles(rol)
            except: pass

    @discord.ui.button(label="ÎNCHIDE", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="zen_close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Doar staff!", ephemeral=True)
        await interaction.response.send_message("Ticket închis în 5 secunde...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class InscriereButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, emoji="🏆", custom_id="zen_inscriere_2v2")
    async def inscriere(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            topic=str(interaction.user.id),
            overwrites=overwrites
        )

        await channel.send(
            f"{interaction.user.mention} – completează formularul de înscriere:",
            content=MODEL_INSCRIERE,
            view=StaffTicketView()
        )

        await interaction.response.send_message(f"Ticket creat: {channel.mention}", ephemeral=True)

# ================= COMENZI =================

@bot.command()
async def setup_inscrieri(ctx):
    if ctx.author.id != OWNER_ID and not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
        return await ctx.send("Doar staff/owner poate seta mesajul cu buton.")

    embed = discord.Embed(
        title="ZEN Tournament 2v2",
        description="Apasă butonul de mai jos pentru a te înscrie în turneu.",
        color=0x00ff00
    )

    view = InscriereButtonView()
    await ctx.send(embed=embed, view=view)
    await ctx.send("Mesaj cu buton creat!")

@bot.event
async def on_ready():
    print(f"{bot.user} → Online | Prefix: #")
    bot.add_view(InscriereButtonView())
    bot.add_view(StaffTicketView())
    keep_alive()

bot.run(os.getenv("DISCORD_TOKEN"))