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
last_table_msg_id = None

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

async def update_table(user_name="Nimeni", game_id="N/A"):
    global last_table_msg_id
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if not tabel_ch: return

    if last_table_msg_id:
        try:
            old_msg = await tabel_ch.fetch_message(last_table_msg_id)
            await old_msg.delete()
        except: pass

    new_msg = await tabel_ch.send(generate_bracket_text(user_name, game_id))
    last_table_msg_id = new_msg.id

# ================= SISTEM TICKET (ACCEPT/REJECT) =================

class StaffReviewView(discord.ui.View):
    def __init__(self, player, game_id):
        super().__init__(timeout=None)
        self.player = player
        self.game_id = game_id

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_players
        free_slots = [i for i in range(1, 11) if bracket_slots[i] == "[LIBER]"]
        
        if not free_slots:
            return await interaction.response.send_message("❌ Nu mai sunt locuri libere în tabel!", ephemeral=True)
        
        slot = random.choice(free_slots)
        bracket_slots[slot] = f"{self.player.name}({self.game_id})"
        tournament_players.append(self.player.id)
        tournament_data[self.player.id] = {"user_name": self.player.name, "game_id": self.game_id}

        await update_table(self.player.name, self.game_id)
        await interaction.response.send_message(f"✅ {self.player.mention} a fost acceptat pe locul {slot}!")
        await self.player.send(f"🏆 Ai fost acceptat în turneu pe locul {slot}!")
        self.stop()

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(REJECT_ROLE_ID)
        if role:
            await self.player.add_roles(role)
            await interaction.response.send_message(f"❌ {self.player.mention} a fost respins. Rolul va fi scos peste 12h.")
            
            async def remove_role_later(member, role_obj):
                await asyncio.sleep(43200) # 12 ore
                try: await member.remove_roles(role_obj)
                except: pass
            
            bot.loop.create_task(remove_role_later(self.player, role))
        
        await self.player.send("❌ Înscrierea ta la turneu a fost respinsă.")
        self.stop()

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if is_staff or interaction.user.id == SPECIAL_USER_ID or interaction.user.id == interaction.guild.owner_id:
            await interaction.response.send_message("🔒 Închidere...")
            await asyncio.sleep(3)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ Doar staff-ul poate închide ticketul!", ephemeral=True)

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, custom_id="tr_join_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrierile sunt închise!", ephemeral=True)
        
        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
        }

        ticket_channel = await guild.create_text_channel(name=f"🎫-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Verifică ticketul: {ticket_channel.mention}", ephemeral=True)
        
        await ticket_channel.send(f"{interaction.user.mention}, trimite ID-ul și Screenshot-ul.", view=TicketControlView())

        def check(m): return m.author == interaction.user and m.channel == ticket_channel and len(m.attachments) > 0
        try:
            msg = await bot.wait_for("message", check=check, timeout=600)
            game_id = re.search(r'\d{5,10}', msg.content).group(0) if re.search(r'\d{5,10}', msg.content) else "N/A"
            
            # Trimite cererea către staff în același ticket
            await ticket_channel.send("⏳ Cererea ta este analizată de staff...", view=StaffReviewView(interaction.user, game_id))
        except: pass

# ================= COMENZI STAFF =================

@bot.command()
async def set(ctx, pozitie: int, member: discord.Member):
    is_staff = any(role.id == STAFF_ROLE_ID for role in ctx.author.roles)
    if is_staff or ctx.author.id == SPECIAL_USER_ID:
        p_data = tournament_data.get(member.id, {"game_id": "N/A"})
        bracket_slots[pozitie] = f"{member.name}({p_data['game_id']})"
        await update_table(member.name, p_data['game_id'])
        await ctx.send(f"✅ Poziția {pozitie} actualizată.")

@bot.command()
async def win(ctx, pozitie: int, member: discord.Member):
    await set(ctx, pozitie, member)

@bot.command()
async def lose(ctx, member: discord.Member):
    if member.id in tournament_players: tournament_players.remove(member.id)
    banned_players.append(member.id)
    await ctx.message.add_reaction("💀")

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.send(embed=discord.Embed(title="🏆 ÎNSCRIERI TURNEU", color=0xff0000), view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    view = discord.ui.View()
    async def s_cb(i): 
        global tournament_status
        tournament_status = "înscrieri"
        await i.response.send_message("Pornit!")
    btn = discord.ui.Button(label="START", style=discord.ButtonStyle.green)
    btn.callback = s_cb
    view.add_item(btn)
    await ctx.send("Panou Admin:", view=view)

@bot.event
async def on_ready():
    bot.add_view(TournamentJoinView())
    bot.add_view(TicketControlView())
    print(f"✅ Bot Online: {bot.user}")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
