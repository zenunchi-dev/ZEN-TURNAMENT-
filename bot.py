import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio
import os

# === REPARAT PENTRU RENDER (KEEP ALIVE + PORT DINAMIC) ===
app = Flask('')

@app.route('/')
def home(): 
    return "Online"

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive(): 
    t = Thread(target=run)
    t.daemon = True
    t.start()

# === DEFINIRE BOT ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# ================= CONFIGURARE ID-URI =================
TOURNAMENT_CATEGORY_ID = 1481418592217206885 # Categoria unde se fac Ticketele
ANNOUNCE_CHANNEL_ID = 1481418592217206885
LOG_CHANNEL_ID = 1481418592217206885 

# Date globale pentru turneu
tournament_players = []
tournament_data = {} 
tournament_matches = {"calificari": [], "semifinale": [], "finala": []}
tournament_status = "închis"

# ================= MODAL ÎNSCRIERE (ÎN TICKET) =================

class TournamentRegisterModal(discord.ui.Modal, title="FORMULAR ÎNSCRIERE"):
    game_id = discord.ui.TextInput(label="ID JOC", placeholder="Ex: 12345678", min_length=5, max_length=15)
    device = discord.ui.TextInput(label="DEVICE", placeholder="Ex: Android / iOS / Tabletă")
    profile_url = discord.ui.TextInput(label="LINK POZĂ PROFIL", placeholder="Pune link-ul pozei (Imgur/Discord)")

    async def on_submit(self, interaction: discord.Interaction):
        global tournament_players, tournament_data
        
        user_id = interaction.user.id
        tournament_players.append(user_id)
        tournament_data[user_id] = {
            "game_id": self.game_id.value,
            "device": self.device.value,
            "profile_url": self.profile_url.value
        }

        # Log pentru Staff
        log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_chan:
            log_embed = discord.Embed(title="📥 ÎNSCRIERE NOUĂ CONFIRMATĂ", color=discord.Color.green())
            log_embed.add_field(name="Utilizator", value=f"<@{user_id}>", inline=True)
            log_embed.add_field(name="ID Joc", value=self.game_id.value, inline=True)
            log_embed.add_field(name="Device", value=self.device.value, inline=True)
            log_embed.set_image(url=self.profile_url.value)
            await log_chan.send(embed=log_embed)

        await interaction.response.send_message(f"✅ Datele au fost salvate! Acest ticket se va închide în 10 secunde.", ephemeral=False)
        
        # Așteptăm puțin și ștergem ticketul automat
        await asyncio.sleep(10)
        await interaction.channel.delete()

# ================= SISTEM TICKET (LA APĂSARE BUTON) =================

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNSCRIE-TE ÎN TURNEU", style=discord.ButtonStyle.success, custom_id="tr_join_btn", emoji="🏆")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise!", ephemeral=True)
        if interaction.user.id in tournament_players:
            return await interaction.response.send_message("❌ Ești deja înscris!", ephemeral=True)
        if len(tournament_players) >= 8:
            return await interaction.response.send_message("❌ Turneul este plin!", ephemeral=True)

        # Creare canal tip Ticket
        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        
        # Permisiuni: doar user-ul și staff-ul văd canalul
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ticket_name = f"inscrieri-{interaction.user.name}"
        channel = await guild.create_voice_channel(name=ticket_name, category=category, overwrites=overwrites) # Create as text/voice based on category type, but usually create_text_channel is better:
        
        # Corecție: Creăm canal de text pentru ticket
        ticket_channel = await guild.create_text_channel(name=ticket_name, category=category, overwrites=overwrites)

        await interaction.response.send_message(f"✅ Ticket creat! Mergi aici: {ticket_channel.mention}", ephemeral=True)

        # Trimitem butonul de formular în ticket
        view = discord.ui.View()
        btn = discord.ui.Button(label="COMPLETEAZĂ FORMULARUL", style=discord.ButtonStyle.primary)
        
        async def btn_callback(inter):
            await inter.response.send_modal(TournamentRegisterModal())
        
        btn.callback = btn_callback
        view.add_item(btn)

        embed = discord.Embed(title="ÎNSCRIERE TURNEU", description="Apasă butonul de mai jos pentru a trimite datele tale.", color=discord.Color.blue())
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=view)

# ================= ADMIN PANEL & COMENZI =================

class TournamentAdminPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="DESCHIDE ÎNSCRIERI", style=discord.ButtonStyle.success, custom_id="admin_open")
    async def open_reg(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status, tournament_players, tournament_data
        tournament_status, tournament_players, tournament_data = "înscrieri", [], {}
        await interaction.response.send_message("✅ Înscrierile deschise!", ephemeral=True)

    @discord.ui.button(label="GENEREAZĂ CALIFICĂRI", style=discord.ButtonStyle.danger, custom_id="admin_gen")
    async def start_tr(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(tournament_players) < 8:
            return await interaction.response.send_message(f"❌ Ai nevoie de 8 oameni!", ephemeral=True)
        random.shuffle(tournament_players)
        p = tournament_players
        tournament_matches["calificari"] = [[p[0], p[1]], [p[2], p[3]], [p[4], p[5]], [p[6], p[7]]]
        embed = discord.Embed(title="🏆 BRACKETS TURNEU", color=0xffd700)
        for i, m in enumerate(tournament_matches["calificari"]):
            embed.add_field(name=f"Meciul {i+1}", value=f"⚔️ <@{m[0]}> vs <@{m[1]}>", inline=False)
        chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL_ID)
        if chan: await chan.send(embed=embed)
        await interaction.response.send_message("✅ Tabel generat!", ephemeral=True)

    @discord.ui.button(label="RESET TOTAL", style=discord.ButtonStyle.secondary, custom_id="admin_reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_players, tournament_status, tournament_data
        tournament_players, tournament_status, tournament_data = [], "închis", {}
        await interaction.response.send_message("🧹 Resetat.", ephemeral=True)

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 TURNEU STANDOFF 2 🏆", description="Apasă butonul de mai jos pentru a deschide un **Ticket de Înscriere**.", color=0xff0000)
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    await ctx.send("🛡️ **ADMIN PANEL**", view=TournamentAdminPanel(), ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")
    bot.add_view(TournamentJoinView())
    bot.add_view(TournamentAdminPanel())

# === PORNIRE ===
keep_alive()
token = os.getenv("DISCORD_TOKEN")
if token: bot.run(token)
