import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio
import os
import re
import io

# === SERVER PENTRU RENDER ===
app = Flask('')
@app.route('/')
def home(): return "Online"
def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# === CONFIGURARE BOT ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="#", intents=intents)

# ID-URI REVIZUITE
TOURNAMENT_CATEGORY_ID = 1481418592217206885
LOG_CHANNEL_ID = 1481418592217206885
TABEL_MECIURI_CH_ID = 1481418744956850392 
STAFF_ROLE_ID = 1481436643603906600       
SPECIAL_USER_ID = 810609759324471306     
REJECT_ROLE_ID = 1481790057412038738

# State Turneu
tournament_players = []
banned_players = [] 
tournament_data = {} 
tournament_status = "închis"
last_table_msg_id = None # Pentru stergerea mesajului vechi

# --- LOGICĂ TABEL TEXT ---
bracket_slots = {i: "[LIBER]" for i in range(1, 18)}

def generate_bracket_text(last_user="Nimeni", last_id="N/A"):
    text = (
        "```text\n"
        "ROUND 1           SEMIFINALA           FINALA           CAMPION\n\n"
        f"{bracket_slots[1]} ──┐\n"
        f"           ├── {bracket_slots[11]} ──┐\n"
        f"{bracket_slots[2]} ──┘                 │\n"
        f"                             ├── {bracket_slots[15]} ──┐\n"
        f"{bracket_slots[3]} ──┐                 │                  │\n"
        f"           ├── {bracket_slots[12]} ──┘                  │\n"
        f"{bracket_slots[4]} ──┘                                    │\n"
        "                                                │\n"
        f"{bracket_slots[5]} ───────────────────────────────────────┤\n"
        "                                                │\n"
        f"                                                ├── 🏆 {bracket_slots[17]}\n"
        f"{bracket_slots[10]} ──────────────────────────────────────┤\n"
        "                                                │\n"
        f"{bracket_slots[6]} ──┐                                    │\n"
        f"           ├── {bracket_slots[13]} ──┐                  │\n"
        f"{bracket_slots[7]} ──┘                 │                  │\n"
        f"                             ├── {bracket_slots[16]} ──┘\n"
        f"{bracket_slots[8]} ──┐                 │\n"
        f"           ├── {bracket_slots[14]} ──┘\n"
        f"{bracket_slots[9]} ──┘\n\n"
        "=========================================\n"
        f"Ultimul update: Jucătorul {last_user} (ID: {last_id})\n"
        "```"
    )
    return text

async def update_table(last_user="Nimeni", last_id="N/A"):
    global last_table_msg_id
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        if last_table_msg_id:
            try:
                old_msg = await tabel_ch.fetch_message(last_table_msg_id)
                await old_msg.delete()
            except: pass
        new_msg = await tabel_ch.send(generate_bracket_text(last_user, last_id))
        last_table_msg_id = new_msg.id

# ================= SISTEM STAFF (ACCEPT/REJECT) =================

class StaffReviewView(discord.ui.View):
    def __init__(self, player, game_id, ticket_channel):
        super().__init__(timeout=None)
        self.player = player
        self.game_id = game_id
        self.ticket_channel = ticket_channel

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if not (is_staff or interaction.user.id == SPECIAL_USER_ID):
            return await interaction.response.send_message("❌ Nu ai permisiune!", ephemeral=True)

        free_slots = [i for i in range(1, 11) if bracket_slots[i] == "[LIBER]"]
        if not free_slots:
            return await interaction.response.send_message("❌ Tabel plin!", ephemeral=True)

        slot = random.choice(free_slots)
        bracket_slots[slot] = f"{self.player.name}({self.game_id})"
        tournament_players.append(self.player.id)
        tournament_data[self.player.id] = {"user_name": self.player.name, "game_id": self.game_id}

        await update_table(self.player.name, self.game_id)
        await interaction.response.send_message(f"✅ Acceptat pe locul {slot}!")
        await self.player.send(f"🏆 Ai fost acceptat în turneu pe locul {slot}!")
        self.stop()

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if not (is_staff or interaction.user.id == SPECIAL_USER_ID):
            return await interaction.response.send_message("❌ Nu ai permisiune!", ephemeral=True)

        role = interaction.guild.get_role(REJECT_ROLE_ID)
        if role:
            await self.player.add_roles(role)
            await interaction.response.send_message(f"❌ Respins. Rolul va fi scos peste 12h.")
            
            async def remove_role_task():
                await asyncio.sleep(43200) # 12 ore
                try: await self.player.remove_roles(role)
                except: pass
            bot.loop.create_task(remove_role_task())
        
        await self.player.send("❌ Înscrierea ta a fost respinsă.")
        self.stop()

# ================= BUTOANE ORIGINALE TICKET =================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if is_staff or interaction.user.id == SPECIAL_USER_ID or interaction.user.id == interaction.guild.owner_id:
            await interaction.response.send_message("🔒 Închidere în 5 secunde...")
            await asyncio.sleep(5)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ Nu ai permisiune!", ephemeral=True)

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, custom_id="tr_join_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise!", ephemeral=True)
        if interaction.user.id in banned_players or interaction.user.id in tournament_players:
            return await interaction.response.send_message("❌ Nu te poți înscrie!", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        ticket_channel = await guild.create_text_channel(name=f"🎫-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket: {ticket_channel.mention}", ephemeral=True)
        
        embed = discord.Embed(title="📝 ÎNSCRIERE", description="Trimite ID-ul și Screenshot-ul.", color=discord.Color.blue())
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=TicketControlView())

        def check(m): return m.author == interaction.user and m.channel == ticket_channel and len(m.attachments) > 0
        try:
            msg = await bot.wait_for("message", check=check, timeout=600)
            game_id = re.search(r'\d{5,10}', msg.content).group(0) if re.search(r'\d{5,10}', msg.content) else "N/A"
            await ticket_channel.send("⏳ Așteaptă confirmarea staff-ului...", view=StaffReviewView(interaction.user, game_id, ticket_channel))
        except: pass

# ================= COMENZI STAFF & ADMIN ORIGINALE =================

@bot.command()
async def win(ctx, pozitie: int, member: discord.Member):
    if any(role.id == STAFF_ROLE_ID for role in ctx.author.roles) or ctx.author.id == SPECIAL_USER_ID or ctx.author.id == ctx.guild.owner_id:
        p_data = tournament_data.get(member.id, {"game_id": "N/A"})
        bracket_slots[pozitie] = f"{member.name}({p_data['game_id']})"
        await update_table(member.name, p_data['game_id'])
        await ctx.send(f"✅ Jucătorul {member.mention} pus pe {pozitie}!")

@bot.command()
async def set(ctx, pozitie: int, member: discord.Member):
    await win(ctx, pozitie, member)

@bot.command()
async def lose(ctx, member: discord.Member):
    if any(role.id == STAFF_ROLE_ID for role in ctx.author.roles) or ctx.author.id == SPECIAL_USER_ID:
        if member.id in tournament_players: tournament_players.remove(member.id)
        banned_players.append(member.id)
        await ctx.message.add_reaction("💀")

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 STANDOFF 2 - TOURNAMENT 🏆", description="Apasă butonul pentru înscriere.", color=0xff0000)
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    embed = discord.Embed(title="🛡️ PANOU CONTROL OWNER", color=discord.Color.dark_grey())
    view = discord.ui.View()
    
    btn_start = discord.ui.Button(label="START ÎNSCRIERI", style=discord.ButtonStyle.success)
    async def start_callback(inter):
        global tournament_status
        tournament_status = "înscrieri"
        await inter.response.send_message("✅ Pornit!", ephemeral=True)
    btn_start.callback = start_callback
    
    btn_stop = discord.ui.Button(label="STOP ÎNSCRIERI", style=discord.ButtonStyle.danger)
    async def stop_callback(inter):
        global tournament_status
        tournament_status = "închis"
        await inter.response.send_message("🛑 Oprit!", ephemeral=True)
    btn_stop.callback = stop_callback

    btn_reset = discord.ui.Button(label="RESET DATE", style=discord.ButtonStyle.secondary)
    async def reset_callback(inter):
        global tournament_players, banned_players, tournament_data, bracket_slots, last_table_msg_id
        tournament_players, banned_players, tournament_data = [], [], {}
        last_table_msg_id = None
        for i in range(1, 18): bracket_slots[i] = "[LIBER]"
        await inter.response.send_message("🧹 Resetat!", ephemeral=True)
    btn_reset.callback = reset_callback

    view.add_item(btn_start) view.add_item(btn_stop) view.add_item(btn_reset)
    await ctx.send(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TournamentJoinView())
    bot.add_view(TicketControlView())
    print(f"✅ Bot Online: {bot.user}")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
