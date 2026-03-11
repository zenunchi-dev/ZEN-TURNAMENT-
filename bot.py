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
TOURNAMENT_CATEGORY_ID = 1481418592217206885 
ANNOUNCE_CHANNEL_ID = 1481418592217206885
LOG_CHANNEL_ID = 1481418592217206885 # Poți schimba cu ID-ul unui canal unde vrei să vezi dovezile (ID joc + Poză)

# Date globale pentru turneu
tournament_players = []
tournament_data = {} # Stocăm datele despre ID, device etc.
tournament_matches = {"calificari": [], "semifinale": [], "finala": []}
tournament_status = "închis"

# ================= MODAL ÎNSCRIERE DETALIATĂ =================

class TournamentRegisterModal(discord.ui.Modal, title="ÎNSCRIERE TURNEU STANDOFF 2"):
    game_id = discord.ui.TextInput(label="ID JOC", placeholder="Ex: 12345678", min_length=5, max_length=15)
    device = discord.ui.TextInput(label="DEVICE (Telefon/Tabletă)", placeholder="Ex: iPhone 13 / iPad Pro", min_length=2)
    profile_url = discord.ui.TextInput(label="LINK POZĂ PROFIL (Imgur/Discord Link)", placeholder="Pune link-ul pozei cu profilul tău", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        global tournament_players, tournament_data
        
        user_id = interaction.user.id
        tournament_players.append(user_id)
        tournament_data[user_id] = {
            "game_id": self.game_id.value,
            "device": self.device.value,
            "profile_url": self.profile_url.value
        }

        # Trimitem confirmare la jucător
        await interaction.response.send_message(f"✅ Te-ai înscris cu succes, <@{user_id}>!", ephemeral=True)

        # Trimitem log pentru Staff
        log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_chan:
            log_embed = discord.Embed(title="📥 ÎNSCRIERE NOUĂ", color=discord.Color.blue())
            log_embed.add_field(name="Utilizator", value=f"<@{user_id}>", inline=True)
            log_embed.add_field(name="ID Joc", value=self.game_id.value, inline=True)
            log_embed.add_field(name="Device", value=self.device.value, inline=True)
            log_embed.set_image(url=self.profile_url.value)
            await log_chan.send(embed=log_embed)

        # Update la mesajul de înscriere (număr participanți)
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"Participanți: {len(tournament_players)} / 8")
        await interaction.message.edit(embed=embed)

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

        # Deschidem formularul (Modal)
        await interaction.response.send_modal(TournamentRegisterModal())

class TournamentAdminPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="DESCHIDE ÎNSCRIERI", style=discord.ButtonStyle.success, custom_id="admin_open")
    async def open_reg(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status, tournament_players, tournament_data
        tournament_status, tournament_players, tournament_data = "înscrieri", [], {}
        await interaction.response.send_message("✅ Înscrierile turneului au fost deschise!", ephemeral=True)

    @discord.ui.button(label="GENEREAZĂ CALIFICĂRI", style=discord.ButtonStyle.danger, custom_id="admin_gen")
    async def start_tr(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(tournament_players) < 8:
            return await interaction.response.send_message(f"❌ Ai nevoie de 8 oameni!", ephemeral=True)
        
        random.shuffle(tournament_players)
        p = tournament_players
        tournament_matches["calificari"] = [[p[0], p[1]], [p[2], p[3]], [p[4], p[5]], [p[6], p[7]]]
        
        embed = discord.Embed(title="🏆 TURNEU STANDOFF 2 - BRACKETS", color=0xffd700)
        for i, m in enumerate(tournament_matches["calificari"]):
            p1_id = tournament_data[m[0]]['game_id']
            p2_id = tournament_data[m[1]]['game_id']
            embed.add_field(name=f"Meciul {i+1}", value=f"⚔️ <@{m[0]}> (ID: {p1_id}) **vs** <@{m[1]}> (ID: {p2_id})", inline=False)
        
        chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL_ID)
        if chan:
            await chan.send(content="@everyone Meciurile din calificări au fost stabilite!", embed=embed)
            await interaction.response.send_message("✅ Tabelul a fost generat!", ephemeral=True)

    @discord.ui.button(label="RESET TOTAL", style=discord.ButtonStyle.secondary, custom_id="admin_reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_players, tournament_status, tournament_data
        tournament_players, tournament_status, tournament_data = [], "închis", {}
        await interaction.response.send_message("🧹 Datele turneului au fost resetate.", ephemeral=True)

# ================= COMENZI OWNER =================

@bot.command()
@commands.is_owner()
async def voice(ctx):
    await ctx.message.delete()
    over = {ctx.guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}
    cat = await ctx.guild.create_category("📊 STATISTICI SERVER", overwrites=over)
    await ctx.guild.create_voice_channel(f"👤 Membri: {ctx.guild.member_count}", category=cat)
    await ctx.guild.create_voice_channel(f"🚀 Boosts: {ctx.guild.premium_subscription_count}", category=cat)

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="🏆 TURNEU STANDOFF 2 🏆",
        description="Apasă butonul de mai jos pentru a te înscrie!\nVa trebui să introduci ID-ul tău, Device-ul și un link către poza de profil.",
        color=0xff0000
    )
    embed.set_footer(text=f"Participanți: {len(tournament_players)} / 8")
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
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
                except: pass

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

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ EROARE: Nu am găsit variabila DISCORD_TOKEN!")
