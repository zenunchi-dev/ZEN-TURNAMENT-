import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import asyncio
import os

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
STAFF_ROLE_ID           = 1466541122636611759
ACCEPT_ROLE_ID          = 1484534027342974976
REJECT_ROLE_ID          = 1481789988654940272

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

# ================= VIEW PENTRU TICKET =================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

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

# ================= VIEW PENTRU ÎNSCRIERE =================

class InscriereButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏆 ÎNSCRIE-TE", style=discord.ButtonStyle.success, emoji="🏆", custom_id="zen_inscriere_2v2")
    async def inscriere(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Blocare pentru cei cu rol rejectat
        if any(r.id == REJECT_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Ai fost respins recent și nu poți crea ticket nou.", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        if not category:
            return await interaction.response.send_message("Categoria de tickete nu a fost găsită!", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,          # permisiune pentru a trimite poze/screenshot-uri
                embed_links=True            # opțional, pentru link-uri cu preview
            ),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            ),
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            topic=str(interaction.user.id),
            overwrites=overwrites
        )

        # Trimite automat mențiune + model + butoane
        await channel.send(
            f"{interaction.user.mention}\n\n{MODEL_INSCRIERE}",
            view=TicketControlView()
        )

        await interaction.response.send_message(f"Ticket-ul tău a fost creat: {channel.mention}", ephemeral=True)

# ================= COMENZI =================

@bot.command()
async def setup_inscrieri(ctx):
    if ctx.author.id != 1466541122636611759 and not any(r.id == STAFF_ROLE_ID for r in ctx.author.roles):
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
    bot.add_view(TicketControlView())
    keep_alive()

bot.run(os.getenv("DISCORD_TOKEN"))