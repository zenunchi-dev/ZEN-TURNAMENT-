import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import random
import asyncio
import os
import re

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
STAFF_ROLE_ID = 1481794622752555072       
OWNER_ID = 1466541122636611759            
REJECT_ROLE_ID = 1481789988654940272      
TOURNAMENT_ROLE_ID = 1481418649196560414  
SPECIAL_USER_ID = 810609759324471306     

# State Turneu
tournament_players = []
bracket_slots = {i: "[LIBER]" for i in range(1, 18)}
tournament_status = "închis"
last_table_msg_id = None 

# --- LOGICĂ TABEL TEXT ---
def generate_bracket_text(last_user="Nimeni"):
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
        f"Ultimul update: {last_user}\n"
        "```"
    )
    return text

async def update_table(user_name="Nimeni"):
    global last_table_msg_id
    tabel_ch = bot.get_channel(TABEL_MECIURI_CH_ID)
    if tabel_ch:
        if last_table_msg_id:
            try:
                old_msg = await tabel_ch.fetch_message(last_table_msg_id)
                await old_msg.delete()
            except: pass
        new_msg = await tabel_ch.send(generate_bracket_text(user_name))
        last_table_msg_id = new_msg.id

# ================= VIEWS PERSISTENTE =================

class StaffReviewView(discord.ui.View):
    def __init__(self, player_id=None):
        super().__init__(timeout=None)
        self.player_id = player_id

    @discord.ui.button(label="ACCEPTĂ", style=discord.ButtonStyle.success, emoji="✅", custom_id="accept_v3")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (any(r.id == STAFF_ROLE_ID for r in interaction.user.roles) or interaction.user.id == OWNER_ID):
            return await interaction.response.send_message("❌ Doar Staff!", ephemeral=True)

        free = [i for i in range(1, 11) if bracket_slots[i] == "[LIBER]"]
        if not free: return await interaction.response.send_message("❌ Tabel plin!", ephemeral=True)

        p_id = self.player_id or int(interaction.message.content.split('<@')[1].split('>')[0])
        target = interaction.guild.get_member(p_id)
        
        slot = random.choice(free)
        bracket_slots[slot] = f"{target.name}"
        await update_table(target.name)
        await interaction.response.send_message(f"✅ {target.name} adăugat pe {slot}!")

    @discord.ui.button(label="REJECTĂ", style=discord.ButtonStyle.danger, emoji="❌", custom_id="reject_v3")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (any(r.id == STAFF_ROLE_ID for r in interaction.user.roles) or interaction.user.id == OWNER_ID):
            return await interaction.response.send_message("❌ Doar Staff!", ephemeral=True)

        p_id = self.player_id or int(interaction.message.content.split('<@')[1].split('>')[0])
        target = interaction.guild.get_member(p_id)
        rej_role = interaction.guild.get_role(REJECT_ROLE_ID)
        
        if rej_role:
            await target.add_roles(rej_role)
            await interaction.response.send_message(f"❌ Respins 12h.")
            async def remove_later():
                await asyncio.sleep(43200)
                try: await target.remove_roles(rej_role)
                except: pass
            bot.loop.create_task(remove_later())

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ÎNCHIDE TICKET", style=discord.ButtonStyle.danger, custom_id="close_v3", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(r.id == STAFF_ROLE_ID for r in interaction.user.roles) or interaction.user.id in [OWNER_ID, SPECIAL_USER_ID]:
            await interaction.response.send_message("🔒 Se închide...")
            await asyncio.sleep(3)
            await interaction.channel.delete()

class TournamentJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, custom_id="join_v3")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournament_status
        if tournament_status != "înscrieri":
            return await interaction.response.send_message("❌ Înscrieri închise!", ephemeral=True)
        
        if any(role.id == REJECT_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Ai Reject recent!", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TOURNAMENT_CATEGORY_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_member(OWNER_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ch = await guild.create_text_channel(name=f"🎫-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket: {ch.mention}", ephemeral=True)
        await ch.send(content=f"{interaction.user.mention}", view=StaffReviewView(interaction.user.id))
        await ch.send("Control:", view=TicketControlView())

# ================= COMENZI WIN / SET =================

@bot.command(name="win", aliases=["set"])
async def set_winner(ctx, slot: int, member: discord.Member):
    if not (any(r.id == STAFF_ROLE_ID for r in ctx.author.roles) or ctx.author.id == OWNER_ID):
        return await ctx.send("❌ Nu ai permisiune!")
    
    if slot in bracket_slots:
        bracket_slots[slot] = f"{member.name}"
        await update_table(member.name)
        await ctx.send(f"✅ {member.name} a fost pus pe locul {slot}!")
    else:
        await ctx.send("❌ Loc invalid (1-17)!")

# ================= ALTE COMENZI ADMIN =================

@bot.command()
@commands.is_owner()
async def setup_tournament(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏆 TURNEU STANDOFF 2", description="Apasă butonul pentru înscriere.", color=0xff0000)
    await ctx.send(embed=embed, view=TournamentJoinView())

@bot.command()
@commands.is_owner()
async def admin_tr(ctx):
    v = discord.ui.View()
    b_on = discord.ui.Button(label="START", style=discord.ButtonStyle.green)
    async def on_c(i):
        global tournament_status
        tournament_status = "înscrieri"
        await i.response.send_message("✅ START!", ephemeral=True)
    b_on.callback = on_c
    b_off = discord.ui.Button(label="STOP", style=discord.ButtonStyle.red)
    async def off_c(i):
        global tournament_status
        tournament_status = "închis"
        await i.response.send_message("🛑 STOP!", ephemeral=True)
    b_off.callback = off_c
    v.add_item(b_on); v.add_item(b_off)
    await ctx.send("Control Turneu:", view=v, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TournamentJoinView())
    bot.add_view(TicketControlView())
    bot.add_view(StaffReviewView())
    print(f"✅ Bot Online!")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
