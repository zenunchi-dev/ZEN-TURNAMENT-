import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio

# === ADAUGAT PENTRU RENDER (KEEP ALIVE) ===
app = Flask('')
@app.route('/')
def home(): return "Online"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run).start()

# === DEFINIRE BOT (NECESARĂ PENTRU COMENZI) ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# ================= CONFIGURARE ID-URI =================
TOURNAMENT_CATEGORY_ID = 1481418592217206885  # ID-ul dat de tine
ANNOUNCE_CHANNEL_ID = 1481418592217206885     # Poți schimba dacă vrei alt canal de anunțuri
VERSION = "6.0"

# Date globale pentru turneu
tournament_players = []
tournament_matches = {"calificari": [], "semifinale": [], "finala": []}
tournament_status = "închis"

# ================= CLASE UI PERSISTENTE =================

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNSCRIE-TE ÎN TURNEU", style=discord.ButtonStyle.success, custom_id="tr_join_btn", emoji="🏆")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise momentan!", ephemeral=True)
        if interaction.user.id in tournament_players:
            return await interaction.response.send_message("❌ Ești deja înscris!", ephemeral=True)
        if len(tournament_players) >= 8:
            return await interaction.response.send_message("❌ Turneul este deja plin (8/8)!", ephemeral=True)

        tournament_players.append(interaction.user.id)
        
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"Participanți: {len(tournament_players)} / 8")
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f"✅ Te-ai înscris cu succes! ({len(tournament_players)}/8)", ephemeral=True)

class TournamentAdminPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="DESCHIDE ÎNSCRIERI", style=discord.ButtonStyle.success, custom_id="admin_open")
    async def open_reg(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status, tournament_players
        tournament_status, tournament_players = "înscrieri", []
        await interaction.response.send_message("✅ Înscrierile turneului au fost deschise!", ephemeral=True)

    @discord.ui.button(label="GENEREAZĂ CALIFICĂRI", style=discord.ButtonStyle.danger, custom_id="admin_gen")
    async def start_tr(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(tournament_players) < 8:
            return await interaction.response.send_message(f"❌ Ai nevoie de 8 oameni! (Momentan: {len(tournament_players)})", ephemeral=True)
        
        random.shuffle(tournament_players)
        p = tournament_players
        # Creăm 4 meciuri de calificare
        tournament_matches["calificari"] = [[p[0], p[1]], [p[2], p[3]], [p[4], p[5]], [p[6], p[7]]]
        
        embed = discord.Embed(title="🏆 TURNEU STANDOFF 2 - BRACKETS", color=0xffd700)
        for i, m in enumerate(tournament_matches["calificari"]):
            embed.add_field(name=f"Meciul {i+1}", value=f"⚔️ <@{m[0]}> **vs** <@{m[1]}>", inline=False)
        
        chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL_ID)
        if chan:
            await chan.send(content="@everyone Meciurile din calificări au fost stabilite!", embed=embed)
            await interaction.response.send_message("✅ Tabelul a fost generat!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Eroare: Nu am găsit canalul de anunțuri!", ephemeral=True)

    @discord.ui.button(label="RESET TOTAL", style=discord.ButtonStyle.secondary, custom_id="admin_reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_players, tournament_status
        tournament_players, tournament_status = [], "închis"
        await interaction.response.send_message("🧹 Datele turneului au fost resetate.", ephemeral=True)

# ================= COMENZI OWNER =================

@bot.command()
@commands.is_owner()
async def voice(ctx):
    """Creează automat categoria de statistici și canalele"""
    await ctx.message.delete()
    over = {ctx.guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}
    cat = await ctx.guild.create_category("📊 STATISTICI SERVER", overwrites=over)
    await ctx.guild.create_voice_channel(f"👤 Membri: {ctx.guild.member_count}", category=cat)
    await ctx.guild.create_voice_channel(f"🚀 Boosts: {ctx.guild.premium_subscription_count}", category=cat)
    await ctx.send("✅ Canalele de statistici au fost create!", delete_after=5)

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    """Trimite panoul de înscrieri"""
    await ctx.message.delete()
    embed = discord.Embed(
        title="🏆 TURNEU STANDOFF 2 🏆",
        description="Ești gata de luptă? Apasă butonul de mai jos pentru a te înscrie!\n\n"
                    "**Locuri disponibile:** 8\n"
                    "**Format:** 1v1 (Single Elimination)",
        color=0xff0000
    )
    embed.set_footer(text=f"Participanți: {len(tournament_players)} / 8")
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    """Panoul tău secret de control"""
    await ctx.send("🛡️ **PANOU CONTROL TURNEU**", view=TournamentAdminPanel(), ephemeral=True)

# ================= AUTOMATIZARE STATS =================

@tasks.loop(minutes=10)
async def update_stats_task():
    for guild in bot.guilds:
        cat = discord.utils.get(guild.categories, name="📊 STATISTICI SERVER")
        if cat:
            channels = cat.voice_channels
            if len(channels) >= 2:
                try:
                    await channels[0].edit(name=f"👤 Membri: {guild.member_count}")
                    await channels[1].edit(name=f"🚀 Boosts: {guild.premium_subscription_count}")
                except Exception as e:
                    print(f"Eroare update statistici: {e}")

# ================= INTEGRARE ON_READY =================

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")
    bot.add_view(TournamentJoinView())
    bot.add_view(TournamentAdminPanel())
    if not update_stats_task.is_running():
        update_stats_task.start()

# === PORNIRE ===
keep_alive()
bot.run("TOKEN_UL_TAU") # Pune token-ul aici
              
