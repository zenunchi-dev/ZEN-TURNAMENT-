import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import asyncio
import os

# === SERVER PENTRU RAILWAY (Keep Alive) ===
app = Flask('')
@app.route('/')
def home(): return "Bot Înscrieri Online"

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# === CONFIG BOT ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# ID-URI REPREZENTATIVE
TICKET_CATEGORY_ID      = 1481418592217206885
STAFF_ROLE_ID           = 1466541122636611759 
ACCEPT_ROLE_ID          = 1484534027342974976
REJECT_ROLE_ID          = 1481789988654940272

MODEL_INSCRIERE = """
**Înscriere ZEN 2v2**

**Echipă:** (________________)
**Jucător 1:** (_______________)  
**Jucător 2:** (_______________)  
*(Completează datele de mai sus)*
"""

# ================= VIEW TICKETE (BUTOANE) =================

class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅", custom_id="btn_acc")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Lipsă permisiuni!", ephemeral=True)
        
        user_id = interaction.channel.topic
        member = interaction.guild.get_member(int(user_id))
        rol = interaction.guild.get_role(ACCEPT_ROLE_ID)
        
        if rol and member:
            await member.add_roles(rol)
            await interaction.response.send_message(f"✅ Participantul {member.mention} a primit rolul de **Acceptat**.")
        await interaction.response.defer()

    @discord.ui.button(label="RESPINGE", style=discord.ButtonStyle.danger, emoji="❌", custom_id="btn_rej")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Lipsă permisiuni!", ephemeral=True)
        
        user_id = interaction.channel.topic
        member = interaction.guild.get_member(int(user_id))
        rol = interaction.guild.get_role(REJECT_ROLE_ID)
        
        if rol and member:
            await member.add_roles(rol)
            await interaction.response.send_message(f"❌ Participantul {member.mention} a primit rolul de **Respins**.")
        await interaction.response.defer()

    @discord.ui.button(label="ÎNCHIDE", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="btn_cls")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles): return
        await interaction.response.send_message("Ticket-ul se va șterge imediat...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

class InscriereView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="DESCHIDE TICKET", style=discord.ButtonStyle.primary, emoji="📩", custom_id="btn_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verificăm dacă utilizatorul este deja respins
        if any(r.id == REJECT_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Nu poți deschide un ticket deoarece ai fost respins.", ephemeral=True)
        
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        
        channel = await guild.create_text_channel(
            name=f"inscriere-{interaction.user.name}", 
            category=category, 
            topic=str(interaction.user.id), 
            overwrites=overwrites
        )
        
        await channel.send(f"{interaction.user.mention}\n{MODEL_INSCRIERE}", view=TicketControlView())
        await interaction.response.send_message(f"Ticket-ul tău a fost creat aici: {channel.mention}", ephemeral=True)

# ================= COMANDĂ SETUP =================

@bot.command()
async def setup(ctx):
    """Comanda pentru a trimite panoul de înscrieri"""
    if not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles): return
    
    embed = discord.Embed(
        title="Sistem Înscrieri", 
        description="Apasă pe butonul de mai jos pentru a deschide un ticket de înscriere.", 
        color=0x3498db
    )
    await ctx.send(embed=embed, view=InscriereView())

@bot.event
async def on_ready():
    print(f"Botul {bot.user} este pregătit!")
    bot.add_view(InscriereView())
    bot.add_view(TicketControlView())
    keep_alive()

bot.run(os.getenv("DISCORD_TOKEN"))
