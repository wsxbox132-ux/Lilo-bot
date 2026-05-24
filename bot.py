"""
╔══════════════════════════════════════════════════════════════════╗
║                   🐱  LILU BOT  🖤                              ║
║             Uma gatinha preta cheia de personalidade             ║
║                         v1.0 — Online                            ║
╚══════════════════════════════════════════════════════════════════╝

Módulos:
  • VoiceMaster  — Calls temporárias com painel de controle
  • Logs Call    — Registra entradas/saídas de voz
  • Logs Chat    — Registra mensagens editadas/apagadas
  • Boas-vindas  — Recebe membros com carinho
  • Diálogo      — Lilu aprende a conversar com a galera
"""

import discord
from discord.ext import commands, tasks
import asyncio
import os
import re
import json
import random
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════════
#  ⚙️  CONFIGURAÇÕES GERAIS
# ══════════════════════════════════════════════════════════════════

TOKEN = os.getenv("LILU_TOKEN") or os.getenv("TOKEN")

# IDs dos canais de log (fornecidos pelo servidor)
LOG_CALL_ID  = 1505278837108248696   # log de voz (entradas/saídas de call)
LOG_CHAT_ID  = 1505278899200725015   # log de texto (msgs editadas/apagadas)

# Arquivo de aprendizado de diálogo
DIALOGO_FILE = "lilu_dialogo.json"

# ══════════════════════════════════════════════════════════════════
#  🤖  SETUP DO BOT
# ══════════════════════════════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.guilds          = True
intents.voice_states    = True

bot = commands.Bot(command_prefix=["l!", "L!", "lilu ", "Lilu "], intents=intents)
bot.remove_command("help")   # usaremos help customizado

# ══════════════════════════════════════════════════════════════════
#  🐱  PALETA DE CORES DA LILU
# ══════════════════════════════════════════════════════════════════

COR_PRETA   = 0x1a1a2e   # fundo escuro da gata
COR_ROXA    = 0x7b2d8b   # roxo gatinho
COR_ROSA    = 0xFF69B4   # rosa fofo
COR_VERDE   = 0x00e676   # verde OK
COR_VERMELHO = 0xFF5252  # erro / aviso
COR_DOURADO = 0xFFD700   # especial
COR_AZUL    = 0x5865F2   # discord azul

# ══════════════════════════════════════════════════════════════════
#  🎙️  VOICEMASTER — CALLS TEMPORÁRIAS
# ══════════════════════════════════════════════════════════════════

VM_LOBBY_NAME   = "🐾 Criar Call"
VM_DEFAULT_NAME = "🖤 Call da {user}"
VM_DEFAULT_LIMIT = 0      # 0 = sem limite
VM_EMPTY_DELAY   = 5      # segundos antes de deletar call vazia

# Mensagens da Lilu no VoiceMaster
_VM_MSGS = {
    "sem_call":           "miau~ você ainda não tem uma call ativa, {user}!! entra no 🐾 Criar Call pra começar!! 🖤",
    "renomeada":          "prontinho!! renomeei sua call pra **{nome}**!! ficou fofo!! ✨🐱",
    "limite_set":         "ok!! agora sua call aceita até **{limite}** pessoinha(s)!! 🎯🖤",
    "limite_removido":    "removido!! qualquer quantidade de pessoa pode entrar agora!! 🥳🐱",
    "trancada":           "call trancada!! só quem você convidar pode entrar agora!! 🔒🖤",
    "destrancada":        "call aberta!! qualquer pessoa pode entrar agora!! 🔓🐱",
    "invisivel":          "agora sua call tá oculta!! ninguém vai saber que ela existe!! 👻🖤",
    "visivel":            "sua call voltou a aparecer pra todo mundo!! 👁️🐱",
    "usuario_kickado":    "tchau tchau, **{user}**!! o dono te pediu pra sair da call!! 👋🖤",
    "usuario_banido":     "**{user}** foi banido(a) da call!! não pode mais entrar!! 🚫🐱",
    "usuario_permitido":  "**{user}** agora pode entrar na sua call!! bem-vindo(a)!! 💕🖤",
    "dono_transferido":   "transferido!! agora **{user}** é o(a) novo(a) dono(a) da call!! 👑🐱",
    "dono_reivindicado":  "você assumiu o controle da call!! agora é sua!! 👑🥳🖤",
    "bitrate_set":        "qualidade de áudio atualizada pra **{bitrate}kbps**!! ficou top!! 🎧🐱",
    "permanente":         "sua call agora é **permanente**!! não vai sumir mesmo vazia!! 💎🖤",
    "temporaria":         "sua call voltou a ser **temporária**!! vai sumir quando ficar vazia!! 🕐🐱",
    "nao_na_call":        "você precisa tá dentro de uma call pra usar isso, {user}!! 🥺🖤",
    "user_nao_na_call":   "esse(a) usuário(a) não tá na sua call!! 🤔🐱",
    "ja_dono":            "você já é o(a) dono(a) dessa call!! 😸🖤",
    "dono_ainda_na_call": "o dono ainda tá na call!! só dá pra reivindicar quando ele sair!! 🥺🐱",
    "setup_existe":       "já existe um lobby VoiceMaster aqui!! use l!vm reset pra recriar!! 🤔🖤",
}

def _vm_msg(key: str, **kwargs) -> str:
    m = _VM_MSGS.get(key, "algo deu errado... 🥺🐱")
    return m.format(**kwargs)

def _vm_ok(titulo: str, desc: str) -> discord.Embed:
    e = discord.Embed(title=titulo, description=desc, color=COR_VERDE, timestamp=datetime.utcnow())
    e.set_footer(text="🐱 Lilu VoiceMaster")
    return e

def _vm_erro(desc: str) -> discord.Embed:
    e = discord.Embed(title="❌ eita!!", description=desc, color=COR_VERMELHO, timestamp=datetime.utcnow())
    e.set_footer(text="🐱 Lilu VoiceMaster")
    return e

def _vm_info(titulo: str, desc: str) -> discord.Embed:
    e = discord.Embed(title=titulo, description=desc, color=COR_ROSA, timestamp=datetime.utcnow())
    e.set_footer(text="🐱 Lilu VoiceMaster")
    return e

# ── Modais ────────────────────────────────────────

class VMModalRenomear(discord.ui.Modal, title="✏️ Renomear Sua Call"):
    nome = discord.ui.TextInput(
        label="Novo nome da call",
        placeholder="Ex: 🎮 Call dos Gamers",
        min_length=1, max_length=100, required=True
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.channel.edit(name=self.nome.value)
            await interaction.response.send_message(
                embed=_vm_ok("✏️ Renomeada!!", _vm_msg("renomeada", nome=self.nome.value)),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("não consegui renomear... sem permissão!! 😢🐱"),
                ephemeral=True
            )


class VMModalLimite(discord.ui.Modal, title="👥 Limite de Usuários"):
    limite = discord.ui.TextInput(
        label="Limite (0 = sem limite, máx 99)",
        placeholder="Ex: 5", min_length=1, max_length=2, required=True
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.limite.value)
            if n < 0 or n > 99:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                embed=_vm_erro("número inválido!! coloca entre 0 e 99!! 🥺🐱"),
                ephemeral=True
            )
            return
        try:
            await self.channel.edit(user_limit=n)
            txt    = _vm_msg("limite_removido") if n == 0 else _vm_msg("limite_set", limite=n)
            titulo = "👥 Limite Removido!!" if n == 0 else "👥 Limite Definido!!"
            await interaction.response.send_message(embed=_vm_ok(titulo, txt), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("sem permissão pra alterar o limite!! 😢🐱"),
                ephemeral=True
            )


class VMModalBitrate(discord.ui.Modal, title="🎙️ Qualidade de Áudio"):
    bitrate = discord.ui.TextInput(
        label="Bitrate em kbps (8–384)",
        placeholder="Ex: 64, 96, 128", min_length=1, max_length=3, required=True
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.bitrate.value)
            if n < 8 or n > 384:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                embed=_vm_erro("coloca um bitrate entre 8 e 384 kbps!! 🥺🐱"),
                ephemeral=True
            )
            return
        try:
            await self.channel.edit(bitrate=n * 1000)
            await interaction.response.send_message(
                embed=_vm_ok("🎙️ Bitrate Atualizado!!", _vm_msg("bitrate_set", bitrate=n)),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("sem permissão pra mudar o bitrate!! 😢🐱"),
                ephemeral=True
            )


class VMModalKick(discord.ui.Modal, title="👋 Kickar da Call"):
    user_input = discord.ui.TextInput(
        label="Nome ou @menção do usuário",
        placeholder="Ex: usuario123", min_length=1, max_length=50, required=True
    )
    def __init__(self, cog, channel, guild):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        alvo = discord.utils.find(
            lambda m: m.name.lower() == self.user_input.value.lower()
                      or m.display_name.lower() == self.user_input.value.lower(),
            self.channel.members
        )
        if not alvo:
            await interaction.response.send_message(
                embed=_vm_erro(_vm_msg("user_nao_na_call")), ephemeral=True
            )
            return
        try:
            await alvo.move_to(None, reason=f"Kickado da call pelo dono — Lilu VoiceMaster")
            await interaction.response.send_message(
                embed=_vm_ok("👋 Kickado!!", _vm_msg("usuario_kickado", user=alvo.display_name)),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("não consegui mover esse usuário!! sem permissão!! 😢🐱"),
                ephemeral=True
            )


class VMModalBanirPermitir(discord.ui.Modal):
    user_input = discord.ui.TextInput(
        label="Nome ou @menção do usuário",
        placeholder="Ex: usuario123", min_length=1, max_length=50, required=True
    )
    def __init__(self, cog, channel, guild, *, ban: bool):
        action = "🚫 Banir da Call" if ban else "✅ Permitir na Call"
        super().__init__(title=action)
        self.cog = cog
        self.channel = channel
        self.guild = guild
        self.ban = ban

    async def on_submit(self, interaction: discord.Interaction):
        info = self.cog.vm_channels.get(self.channel.id)
        if not info:
            await interaction.response.send_message(
                embed=_vm_erro("call não gerenciada pela Lilu!! 🤔🐱"), ephemeral=True
            )
            return
        nome_busca = self.user_input.value.strip().lstrip("@").lower()
        alvo = discord.utils.find(
            lambda m: m.name.lower() == nome_busca or m.display_name.lower() == nome_busca,
            self.guild.members
        )
        if not alvo:
            await interaction.response.send_message(
                embed=_vm_erro("não achei esse usuário no servidor!! 🤔🐱"), ephemeral=True
            )
            return
        everyone = self.guild.default_role
        ow = self.channel.overwrites_for(alvo)
        if self.ban:
            ow.connect = False
            await self.channel.set_permissions(alvo, overwrite=ow)
            if alvo in self.channel.members:
                try:
                    await alvo.move_to(None)
                except Exception:
                    pass
            if "banned" not in info:
                info["banned"] = []
            if alvo.id not in info["banned"]:
                info["banned"].append(alvo.id)
            await interaction.response.send_message(
                embed=_vm_ok("🚫 Banido!!", _vm_msg("usuario_banido", user=alvo.display_name)),
                ephemeral=True
            )
        else:
            ow.connect     = True
            ow.view_channel = True
            await self.channel.set_permissions(alvo, overwrite=ow)
            if "banned" in info and alvo.id in info["banned"]:
                info["banned"].remove(alvo.id)
            await interaction.response.send_message(
                embed=_vm_ok("✅ Permitido!!", _vm_msg("usuario_permitido", user=alvo.display_name)),
                ephemeral=True
            )


class VMModalTransferir(discord.ui.Modal, title="👑 Transferir Dono"):
    user_input = discord.ui.TextInput(
        label="Nome ou @menção do novo dono",
        placeholder="Ex: usuario123", min_length=1, max_length=50, required=True
    )
    def __init__(self, cog, channel, guild):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        info = self.cog.vm_channels.get(self.channel.id)
        if not info:
            await interaction.response.send_message(
                embed=_vm_erro("call não gerenciada pela Lilu!! 🤔🐱"), ephemeral=True
            )
            return
        nome_busca = self.user_input.value.strip().lstrip("@").lower()
        alvo = discord.utils.find(
            lambda m: m.name.lower() == nome_busca or m.display_name.lower() == nome_busca,
            self.channel.members
        )
        if not alvo:
            await interaction.response.send_message(
                embed=_vm_erro(_vm_msg("user_nao_na_call")), ephemeral=True
            )
            return
        info["owner"] = alvo.id
        await interaction.response.send_message(
            embed=_vm_ok("👑 Transferido!!", _vm_msg("dono_transferido", user=alvo.display_name)),
            ephemeral=True
        )


# ── Painel de Controle da Call ─────────────────────

class VMPainelView(discord.ui.View):
    """Painel persistente de controle da call."""

    def __init__(self, cog: "VoiceMasterCog"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _checar_dono(self, interaction: discord.Interaction):
        """Verifica se o usuário é dono da call e a retorna."""
        user = interaction.user
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message(
                embed=_vm_erro(_vm_msg("nao_na_call", user=user.mention)), ephemeral=True
            )
            return None
        ch   = user.voice.channel
        info = self.cog.vm_channels.get(ch.id)
        if not info:
            await interaction.response.send_message(
                embed=_vm_erro("essa call não é gerenciada pela Lilu!! 🤔🐱"), ephemeral=True
            )
            return None
        if info["owner"] != user.id:
            await interaction.response.send_message(
                embed=_vm_erro("só o(a) dono(a) da call pode usar isso!! 👑🐱"), ephemeral=True
            )
            return None
        return ch

    # ── Linha 0 ──────────────────────────────────
    @discord.ui.button(label="✏️ Renomear",   style=discord.ButtonStyle.primary,   custom_id="lilu_vm_renomear",   row=0)
    async def btn_renomear(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalRenomear(self.cog, ch))

    @discord.ui.button(label="👥 Limite",     style=discord.ButtonStyle.primary,   custom_id="lilu_vm_limite",     row=0)
    async def btn_limite(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalLimite(self.cog, ch))

    @discord.ui.button(label="🔒 Trancar",    style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_trancar",    row=0)
    async def btn_trancar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if not ch:
            return
        info    = self.cog.vm_channels[ch.id]
        guild   = interaction.guild
        everyone = guild.default_role
        locked  = info.get("locked", False)
        ow = ch.overwrites_for(everyone)
        ow.connect = False if not locked else None
        await ch.set_permissions(everyone, overwrite=ow)
        info["locked"] = not locked
        if not locked:
            await interaction.response.send_message(embed=_vm_ok("🔒 Trancada!!", _vm_msg("trancada")), ephemeral=True)
        else:
            await interaction.response.send_message(embed=_vm_ok("🔓 Aberta!!", _vm_msg("destrancada")), ephemeral=True)

    @discord.ui.button(label="👻 Ocultar",    style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_ocultar",    row=0)
    async def btn_ocultar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if not ch:
            return
        info    = self.cog.vm_channels[ch.id]
        guild   = interaction.guild
        everyone = guild.default_role
        hidden  = info.get("hidden", False)
        ow = ch.overwrites_for(everyone)
        if not hidden:
            ow.view_channel = False
            await ch.set_permissions(everyone, overwrite=ow)
            for membro in ch.members:
                ow_m = ch.overwrites_for(membro)
                ow_m.view_channel = True
                ow_m.connect      = True
                await ch.set_permissions(membro, overwrite=ow_m)
            info["hidden"] = True
            await interaction.response.send_message(embed=_vm_ok("👻 Oculta!!", _vm_msg("invisivel")), ephemeral=True)
        else:
            ow.view_channel = None
            await ch.set_permissions(everyone, overwrite=ow)
            info["hidden"] = False
            await interaction.response.send_message(embed=_vm_ok("👁️ Visível!!", _vm_msg("visivel")), ephemeral=True)

    # ── Linha 1 ──────────────────────────────────
    @discord.ui.button(label="👋 Kickar",     style=discord.ButtonStyle.danger,     custom_id="lilu_vm_kickar",     row=1)
    async def btn_kickar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalKick(self.cog, ch, interaction.guild))

    @discord.ui.button(label="🚫 Banir",      style=discord.ButtonStyle.danger,     custom_id="lilu_vm_banir",      row=1)
    async def btn_banir(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalBanirPermitir(self.cog, ch, interaction.guild, ban=True))

    @discord.ui.button(label="✅ Permitir",   style=discord.ButtonStyle.success,    custom_id="lilu_vm_permitir",   row=1)
    async def btn_permitir(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalBanirPermitir(self.cog, ch, interaction.guild, ban=False))

    @discord.ui.button(label="👑 Transferir", style=discord.ButtonStyle.success,    custom_id="lilu_vm_transferir", row=1)
    async def btn_transferir(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalTransferir(self.cog, ch, interaction.guild))

    # ── Linha 2 ──────────────────────────────────
    @discord.ui.button(label="📊 Info",       style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_info",       row=2)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message(embed=_vm_erro("você não tá em nenhuma call!! 🥺🐱"), ephemeral=True)
            return
        ch   = user.voice.channel
        info = self.cog.vm_channels.get(ch.id)
        if not info:
            await interaction.response.send_message(embed=_vm_erro("essa call não é gerenciada pela Lilu!! 🤔🐱"), ephemeral=True)
            return
        dono   = interaction.guild.get_member(info["owner"])
        banidos = ", ".join(f"<@{uid}>" for uid in info.get("banned", [])) or "Ninguém"
        embed  = discord.Embed(title=f"📊 Info: {ch.name}", color=COR_ROSA, timestamp=datetime.utcnow())
        embed.add_field(name="👑 Dono(a)",   value=dono.mention if dono else "Desconhecido", inline=True)
        embed.add_field(name="👥 Membros",   value=f"`{len(ch.members)}`" + (f"/{ch.user_limit}" if ch.user_limit else " (sem limite)"), inline=True)
        embed.add_field(name="🎧 Bitrate",   value=f"`{ch.bitrate // 1000}kbps`", inline=True)
        embed.add_field(name="🔒 Trancada",  value="Sim 🔒" if info.get("locked") else "Não 🔓", inline=True)
        embed.add_field(name="👻 Oculta",    value="Sim 👻" if info.get("hidden") else "Não 👁️", inline=True)
        embed.add_field(name="💎 Permanente",value="Sim 💎" if info.get("permanent") else "Não 🕐", inline=True)
        embed.add_field(name="🚫 Banidos",   value=banidos, inline=False)
        embed.set_footer(text="🐱 Lilu VoiceMaster")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎙️ Bitrate",  style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_bitrate",    row=2)
    async def btn_bitrate(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalBitrate(self.cog, ch))

    @discord.ui.button(label="💎 Permanente",style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_permanente", row=2)
    async def btn_permanente(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if not ch:
            return
        info = self.cog.vm_channels[ch.id]
        info["permanent"] = not info.get("permanent", False)
        if info["permanent"]:
            await interaction.response.send_message(embed=_vm_ok("💎 Permanente!!", _vm_msg("permanente")), ephemeral=True)
        else:
            await interaction.response.send_message(embed=_vm_ok("🕐 Temporária!!", _vm_msg("temporaria")), ephemeral=True)

    @discord.ui.button(label="🏳️ Reivindicar", style=discord.ButtonStyle.success,  custom_id="lilu_vm_reivindicar",row=2)
    async def btn_reivindicar(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message(embed=_vm_erro(_vm_msg("nao_na_call", user=user.mention)), ephemeral=True)
            return
        ch   = user.voice.channel
        info = self.cog.vm_channels.get(ch.id)
        if not info:
            await interaction.response.send_message(embed=_vm_erro("essa call não é gerenciada pela Lilu!! 🤔🐱"), ephemeral=True)
            return
        if info["owner"] == user.id:
            await interaction.response.send_message(embed=_vm_erro(_vm_msg("ja_dono")), ephemeral=True)
            return
        dono_atual = interaction.guild.get_member(info["owner"])
        if dono_atual and dono_atual in ch.members:
            await interaction.response.send_message(embed=_vm_erro(_vm_msg("dono_ainda_na_call")), ephemeral=True)
            return
        info["owner"] = user.id
        await interaction.response.send_message(embed=_vm_ok("👑 Reivindicado!!", _vm_msg("dono_reivindicado")), ephemeral=True)


# ── Cog VoiceMaster ───────────────────────────────

class VoiceMasterCog(commands.Cog, name="LiluVoiceMaster"):
    """🐱 LILU VOICEMASTER — Calls Temporárias v1.0"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vm_channels: dict[int, dict] = {}   # channel_id → {owner, locked, hidden, permanent, banned}
        self.lobby_id: int | None = None           # ID do canal lobby atual

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(2)
        for guild in self.bot.guilds:
            # Procura lobby existente pelo nome
            lobby = discord.utils.get(guild.voice_channels, name=VM_LOBBY_NAME)
            if lobby:
                self.lobby_id = lobby.id
                print(f"[LiluVM] Lobby encontrado: #{lobby.name} ({lobby.id})")
        print("[LiluVM] VoiceMaster online!! 🐱")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild

        # ── Entrou no lobby → cria call ──────────────
        if after.channel and after.channel.id == self.lobby_id:
            nome = VM_DEFAULT_NAME.format(user=member.display_name)
            categoria = after.channel.category
            try:
                novo = await guild.create_voice_channel(
                    name=nome,
                    category=categoria,
                    user_limit=VM_DEFAULT_LIMIT,
                    reason=f"Lilu VoiceMaster: call de {member}"
                )
                self.vm_channels[novo.id] = {
                    "owner": member.id,
                    "locked": False,
                    "hidden": False,
                    "permanent": False,
                    "banned": [],
                }
                await member.move_to(novo, reason="Lilu VoiceMaster")

                # Painel de controle em texto (pega primeiro canal de texto da categoria ou o primeiro do servidor)
                canal_texto = None
                if categoria:
                    canal_texto = next((c for c in categoria.text_channels), None)
                if not canal_texto:
                    canal_texto = guild.system_channel or guild.text_channels[0]

                embed = discord.Embed(
                    title="🐾 Sua Call Está Pronta!!",
                    description=(
                        f"oi {member.mention}!! criei a call **{nome}** pra você!! 🖤\n\n"
                        "```\n"
                        "╔══════════════════════════════════╗\n"
                        "║   🐱  LILU VOICEMASTER  🖤       ║\n"
                        "║     — Painel de Controle —       ║\n"
                        "╚══════════════════════════════════╝\n"
                        "```\n"
                        "use os botões abaixo pra gerenciar sua call!!"
                    ),
                    color=COR_ROXA,
                    timestamp=datetime.utcnow()
                )
                embed.set_footer(text="🐱 Lilu VoiceMaster • feito com muito amor!!")
                await canal_texto.send(embed=embed, view=VMPainelView(self))

            except discord.Forbidden:
                pass

        # ── Saiu de uma call gerenciada → deleta se vazia ──
        if before.channel and before.channel.id in self.vm_channels:
            ch   = before.channel
            info = self.vm_channels[ch.id]
            if not ch.members:
                if not info.get("permanent"):
                    await asyncio.sleep(VM_EMPTY_DELAY)
                    # Re-checar após o delay
                    ch2 = guild.get_channel(ch.id)
                    if ch2 and not ch2.members:
                        try:
                            await ch2.delete(reason="Lilu VoiceMaster: call vazia")
                        except Exception:
                            pass
                        self.vm_channels.pop(ch.id, None)

    @commands.group(name="vm", aliases=["voicemaster", "call"], invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def vm_group(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🐾 Lilu VoiceMaster",
            description=(
                "`l!vm setup [id_categoria]` — configurar lobby\n"
                "`l!vm reset` — recriar lobby\n"
                "`l!vm info` — status do sistema"
            ),
            color=COR_ROXA,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="🐱 Lilu VoiceMaster")
        await ctx.send(embed=embed)

    @vm_group.command(name="setup")
    @commands.has_permissions(manage_channels=True)
    async def vm_setup(self, ctx: commands.Context, categoria_id: int = None):
        guild = ctx.guild
        if self.lobby_id and guild.get_channel(self.lobby_id):
            await ctx.send(embed=_vm_info("🤔 Já existe!!", _vm_msg("setup_existe")))
            return
        categoria = guild.get_channel(categoria_id) if categoria_id else None
        try:
            lobby = await guild.create_voice_channel(
                name=VM_LOBBY_NAME,
                category=categoria,
                reason="Lilu VoiceMaster Setup"
            )
            self.lobby_id = lobby.id
            embed = _vm_ok(
                "🎉 VoiceMaster Configurado!!",
                f"lobby criado: {lobby.mention}\n\n"
                "agora é só entrar no canal **🐾 Criar Call** pra ter sua própria call!! 🖤🐱"
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(embed=_vm_erro("não tenho permissão pra criar canais!! 😢🐱"))

    @vm_group.command(name="reset")
    @commands.has_permissions(manage_channels=True)
    async def vm_reset(self, ctx: commands.Context, categoria_id: int = None):
        guild = ctx.guild
        # Deleta lobby antigo
        if self.lobby_id:
            old = guild.get_channel(self.lobby_id)
            if old:
                try:
                    await old.delete(reason="Lilu VoiceMaster Reset")
                except Exception:
                    pass
        self.lobby_id = None
        categoria = guild.get_channel(categoria_id) if categoria_id else None
        try:
            lobby = await guild.create_voice_channel(
                name=VM_LOBBY_NAME,
                category=categoria,
                reason="Lilu VoiceMaster Reset"
            )
            self.lobby_id = lobby.id
            await ctx.send(embed=_vm_ok("✅ VoiceMaster Recriado!!", f"novo lobby: {lobby.mention} 🐱🖤"))
        except discord.Forbidden:
            await ctx.send(embed=_vm_erro("não tenho permissão pra criar canais!! 😢🐱"))

    @vm_group.command(name="info")
    @commands.has_permissions(manage_channels=True)
    async def vm_info(self, ctx: commands.Context):
        guild = ctx.guild
        lobby = guild.get_channel(self.lobby_id) if self.lobby_id else None
        embed = discord.Embed(title="📊 Lilu VoiceMaster — Info", color=COR_ROXA, timestamp=datetime.utcnow())
        embed.add_field(name="🎙️ Lobby",          value=lobby.mention if lobby else "❌ Não configurado", inline=True)
        embed.add_field(name="📞 Calls Ativas",   value=f"`{len(self.vm_channels)}`", inline=True)
        embed.add_field(name="⚙️ Delay Exclusão", value=f"`{VM_EMPTY_DELAY}s`", inline=True)
        embed.set_footer(text="🐱 Lilu VoiceMaster")
        await ctx.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  📋  LOGS — VOZ E TEXTO
# ══════════════════════════════════════════════════════════════════

class LogCog(commands.Cog, name="LiluLogs"):
    """🐱 Sistema de logs de voz e texto da Lilu."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _log_call_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        return guild.get_channel(LOG_CALL_ID)

    def _log_chat_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        return guild.get_channel(LOG_CHAT_ID)

    # ── Logs de Voz ───────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild
        ch    = self._log_call_channel(guild)
        if not ch:
            return

        now = datetime.utcnow()

        # Entrou em uma call
        if after.channel and not before.channel:
            embed = discord.Embed(
                title="🎙️ Entrou na Call",
                color=COR_VERDE,
                timestamp=now
            )
            embed.add_field(name="👤 Membro",   value=f"{member.mention} (`{member.id}`)", inline=True)
            embed.add_field(name="🔊 Canal",    value=f"`{after.channel.name}`",           inline=True)
            embed.add_field(name="👥 Na Call",  value=f"`{len(after.channel.members)}`",   inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
            await ch.send(embed=embed)

        # Saiu de uma call
        elif before.channel and not after.channel:
            embed = discord.Embed(
                title="🔇 Saiu da Call",
                color=COR_VERMELHO,
                timestamp=now
            )
            embed.add_field(name="👤 Membro",    value=f"{member.mention} (`{member.id}`)", inline=True)
            embed.add_field(name="🔊 Canal",     value=f"`{before.channel.name}`",          inline=True)
            embed.add_field(name="👥 Restantes", value=f"`{len(before.channel.members)}`",  inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
            await ch.send(embed=embed)

        # Trocou de call
        elif before.channel and after.channel and before.channel.id != after.channel.id:
            embed = discord.Embed(
                title="🔄 Trocou de Call",
                color=COR_DOURADO,
                timestamp=now
            )
            embed.add_field(name="👤 Membro",    value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="🔴 Saiu de",   value=f"`{before.channel.name}`",          inline=True)
            embed.add_field(name="🟢 Entrou em", value=f"`{after.channel.name}`",           inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
            await ch.send(embed=embed)

        # Ativou/desativou mute
        elif before.channel and after.channel and before.channel.id == after.channel.id:
            if before.self_mute != after.self_mute:
                acao = "🔇 Mutou-se" if after.self_mute else "🔊 Desmutou-se"
                cor  = 0x888888 if after.self_mute else COR_VERDE
                embed = discord.Embed(title=acao, color=cor, timestamp=now)
                embed.add_field(name="👤 Membro", value=f"{member.mention}", inline=True)
                embed.add_field(name="🔊 Canal",  value=f"`{after.channel.name}`", inline=True)
                embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
                await ch.send(embed=embed)

    # ── Logs de Chat ──────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ch = self._log_chat_channel(message.guild)
        if not ch:
            return
        now = datetime.utcnow()
        embed = discord.Embed(
            title="🗑️ Mensagem Apagada",
            color=COR_VERMELHO,
            timestamp=now
        )
        embed.add_field(name="👤 Autor",   value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="📌 Canal",   value=message.channel.mention,                              inline=True)
        conteudo = message.content[:1000] if message.content else "*[sem texto — provavelmente mídia]*"
        embed.add_field(name="💬 Conteúdo", value=f"```{conteudo}```", inline=False)
        if message.attachments:
            embed.add_field(
                name="📎 Anexos",
                value="\n".join(a.url for a in message.attachments[:5]),
                inline=False
            )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        ch = self._log_chat_channel(before.guild)
        if not ch:
            return
        now = datetime.utcnow()
        embed = discord.Embed(
            title="✏️ Mensagem Editada",
            color=COR_DOURADO,
            timestamp=now
        )
        embed.add_field(name="👤 Autor",    value=f"{before.author.mention} (`{before.author.id}`)", inline=True)
        embed.add_field(name="📌 Canal",    value=before.channel.mention,                            inline=True)
        embed.add_field(name="🔗 Link",     value=f"[Ir à mensagem]({after.jump_url})",              inline=True)
        embed.add_field(name="📝 Antes",    value=f"```{before.content[:500]}```",                  inline=False)
        embed.add_field(name="✅ Depois",   value=f"```{after.content[:500]}```",                   inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
        await ch.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  👋  BOAS-VINDAS
# ══════════════════════════════════════════════════════════════════

# Mensagens de boas-vindas da Lilu — ela vai rotacionar e aprender novas
_BOAS_VINDAS_BASE = [
    "miaauuu~~ {mention}!! que bom que você chegou!! 🖤🐱 seja muito bem-vindo(a) ao servidor!!",
    "oi {mention}!! a Lilu te dá as boas-vindas!! 🐾✨ espero que você fique bastante por aqui!!",
    "aaaaa {mention} chegouuu!! 🖤😸 bem-vindo(a)!! aproveita bastante o servidor!!",
    "ei ei ei!! {mention} apareceu!! 🐱✨ que ótimo!! bem-vindo(a) por aqui!!",
    "miauuu!! {mention} entrou no servidor!! 🖤🐾 que alegria!! seja bem-vindo(a)!!",
    "olha quem chegou!! {mention}!! 😸🖤 bem-vindo(a) ao servidor, espero que curta muito!!",
    "{mention} chegou chegou!! 🐱💫 bem-vindo(a)!! feliz em te ver por aqui!!",
]

class WelcomeCog(commands.Cog, name="LiluWelcome"):
    """🐱 Sistema de boas-vindas da Lilu."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_name = "👋・bem-vindo"   # nome do canal de boas-vindas (ajuste se necessário)
        self.welcome_channel_id: int | None = None      # pode setar por ID também

    def _get_welcome_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if self.welcome_channel_id:
            ch = guild.get_channel(self.welcome_channel_id)
            if ch:
                return ch
        # Busca por nome
        ch = discord.utils.get(guild.text_channels, name=self.welcome_channel_name)
        if ch:
            return ch
        # Fallback: canal do sistema
        return guild.system_channel

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        ch    = self._get_welcome_channel(guild)
        if not ch:
            return

        bv_texto = random.choice(_BOAS_VINDAS_BASE).format(
            mention=member.mention,
            name=member.display_name
        )

        embed = discord.Embed(
            title="🐾 Nova Pessoinha Chegou!!",
            description=bv_texto,
            color=COR_ROXA,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="👤 Usuário",  value=f"{member} (`{member.id}`)",                                   inline=True)
        embed.add_field(name="📅 Conta criada", value=f"<t:{int(member.created_at.timestamp())}:R>",              inline=True)
        embed.add_field(name="👥 Membro Nº",    value=f"`#{guild.member_count}`",                               inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="🐱 Lilu • bem-vindo(a)!!")

        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        ch    = self._get_welcome_channel(guild)
        if not ch:
            return

        embed = discord.Embed(
            title="🚪 Alguém Saiu...",
            description=f"**{member}** saiu do servidor... 🖤🐱",
            color=0x555555,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="🐱 Lilu")
        await ch.send(embed=embed)

    @commands.command(name="setwelcome")
    @commands.has_permissions(manage_guild=True)
    async def set_welcome(self, ctx: commands.Context, canal: discord.TextChannel = None):
        """Define o canal de boas-vindas. Uso: l!setwelcome #canal"""
        if canal:
            self.welcome_channel_id = canal.id
            await ctx.send(
                embed=discord.Embed(
                    title="✅ Canal de Boas-Vindas Definido!!",
                    description=f"agora vou mandar boas-vindas em {canal.mention}!! 🐱🖤",
                    color=COR_VERDE
                )
            )
        else:
            self.welcome_channel_id = None
            await ctx.send(
                embed=discord.Embed(
                    title="✅ Canal Resetado!!",
                    description=f"vou buscar por nome `{self.welcome_channel_name}` ou usar o canal do sistema!! 🐱",
                    color=COR_VERDE
                )
            )


# ══════════════════════════════════════════════════════════════════
#  💬  DIÁLOGO — LILU APRENDE A CONVERSAR
# ══════════════════════════════════════════════════════════════════

def _carregar_dialogo() -> dict:
    """Carrega o banco de diálogo do arquivo JSON."""
    if os.path.exists(DIALOGO_FILE):
        try:
            with open(DIALOGO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"respostas": {}, "contexto": {}, "apelidos": {}}

def _salvar_dialogo(data: dict):
    """Salva o banco de diálogo no arquivo JSON."""
    with open(DIALOGO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Respostas padrão (seed inicial — Lilu já nasce sabendo algumas coisas)
_RESPOSTAS_SEED: dict[str, list[str]] = {
    # Saudações
    "oi":          ["oiii!! 🐱🖤", "oi oi!! que bom te ver!! 😸", "oiaa!! 🐾✨"],
    "olá":         ["olaaá!! 🐱", "oi!! 🖤😸", "olaaa!! que bom que você falou comigo!! 🐾"],
    "hey":         ["hey hey!! 🐱🖤", "hey!! 😸✨", "heyyy!! oiii!!"],
    "eai":         ["eaiii!! tudo bom?? 🐱", "oi oi!! 🖤😸", "eai eai!! 🐾✨"],
    "boa noite":   ["boa noite!! 🌙🖤🐱", "boa nooite!! descansa bem!! 😴🐾", "boa noite!! 🌙✨"],
    "bom dia":     ["bom diaa!! ☀️🐱🖤", "bom diaaaaa!! 😸☀️", "bom dia!! hoje vai ser ótimo!! ☀️🐾"],
    "boa tarde":   ["boa tarde!! ☀️🐱", "boa tardeeee!! 😸🖤", "boa tarde!! 🐾✨"],
    # Perguntas sobre a Lilu
    "como você se chama": ["eu sou a Lilu!! uma gatinha preta cheia de amor!! 🐱🖤✨"],
    "quem é você":        ["sou a Lilu!! 🖤🐱 uma gatinha aqui pra ajudar e conversar com vocês!!"],
    "o que você faz":     ["gerencio calls, mando logs, dou boas-vindas e converso com a galera!! 🐱🖤"],
    # Estados
    "tudo bem":    ["tudo ótimo!! 😸🐾 e você??", "tudo bem sim!! 🖤🐱 e aí, como você tá??", "tudo bom!! 😸✨"],
    "tudo bom":    ["tudo bom!! 🐱🖤 e você, como tá??", "ótimo!! 😸🐾✨", "tudo bem por aqui!! 🖤🐱"],
    "saudades":    ["aaa que fofo!! saudades suas também!! 🥺🖤🐱", "que saudadee!! 😸🐾", "aww que amor!! 🖤✨"],
    # Reações
    "haha":        ["kkkkk 😸🐱", "hahahaha 🖤😸", "kkkk que engraçado!! 🐾"],
    "kkk":         ["😸😸😸 kkkk", "kkkkk 🖤🐱", "hahaha 🐾😸"],
    "lindo":       ["🥺🖤✨ que fofo você falar isso!!", "awww!! 😸🐾", "que coisa mais linda!! 🖤🐱"],
    "amor":        ["❤️🖤🐱", "muito amor!! 😸🐾", "aaaa que amor!! 🥺🖤"],
}


class DialogueCog(commands.Cog, name="LiluDialogo"):
    """🐱 Sistema de diálogo e aprendizado da Lilu."""

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.db      = _carregar_dialogo()
        # Mescla o seed com o que já foi aprendido
        for chave, resps in _RESPOSTAS_SEED.items():
            if chave not in self.db["respostas"]:
                self.db["respostas"][chave] = resps
        _salvar_dialogo(self.db)

        # Contexto de conversa por canal: {channel_id: deque de últimas msgs}
        self._contexto: dict[int, deque] = defaultdict(lambda: deque(maxlen=10))

        # Cooldown de resposta por canal (evitar spam da Lilu)
        self._ultimo_resp: dict[int, datetime] = {}
        self._cooldown_resp = 3   # segundos

    def _checar_gatilho(self, texto: str) -> str | None:
        """Verifica se o texto contém algum gatilho de diálogo. Retorna chave ou None."""
        texto_lower = texto.lower().strip()
        # Busca exata primeiro
        if texto_lower in self.db["respostas"]:
            return texto_lower
        # Busca por substring (chave contida na mensagem)
        for chave in self.db["respostas"]:
            if chave in texto_lower:
                return chave
        return None

    def _responder(self, chave: str) -> str:
        resps = self.db["respostas"].get(chave, [])
        if resps:
            return random.choice(resps)
        return ""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Ignora comandos
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        # Armazena no contexto do canal
        self._contexto[message.channel.id].append({
            "user": message.author.display_name,
            "user_id": message.author.id,
            "content": message.content,
            "time": datetime.utcnow().isoformat()
        })

        # Checa se Lilu foi mencionada ou chamada pelo nome
        lilu_mencionada = (
            self.bot.user in message.mentions
            or "lilu" in message.content.lower()
        )

        # Checar cooldown
        now = datetime.utcnow()
        ultimo = self._ultimo_resp.get(message.channel.id)
        if ultimo and (now - ultimo).total_seconds() < self._cooldown_resp:
            return

        # ── Resposta por gatilho ──────────────────────────
        chave = self._checar_gatilho(message.content)
        if chave and (lilu_mencionada or random.random() < 0.25):
            resp = self._responder(chave)
            if resp:
                self._ultimo_resp[message.channel.id] = now
                async with message.channel.typing():
                    await asyncio.sleep(random.uniform(0.8, 1.8))
                await message.reply(resp, mention_author=False)
                return

        # ── Reação aleatória fofa (baixa chance) ──────────
        if lilu_mencionada and not chave:
            respostas_genericas = [
                "miauu~~ 🐱🖤",
                "oi!! 😸✨",
                "hm?? me chamou?? 🐾🖤",
                "oioi!! tô aqui!! 🐱",
                "miaaau!! 🖤😸",
                "oi!! o que foi?? 🐾✨",
            ]
            self._ultimo_resp[message.channel.id] = now
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(0.5, 1.2))
            await message.reply(random.choice(respostas_genericas), mention_author=False)

    # ── Comandos de Aprendizado ───────────────────

    @commands.command(name="ensinar", aliases=["teach"])
    @commands.has_permissions(manage_messages=True)
    async def ensinar(self, ctx: commands.Context, gatilho: str, *, resposta: str):
        """
        Ensina a Lilu uma nova resposta.
        Uso: l!ensinar <gatilho> <resposta>
        Ex:  l!ensinar "bora jogar" "bora sim!! que jogo?? 🎮🐱"
        """
        gatilho = gatilho.lower().strip()
        if gatilho not in self.db["respostas"]:
            self.db["respostas"][gatilho] = []
        if resposta not in self.db["respostas"][gatilho]:
            self.db["respostas"][gatilho].append(resposta)
        _salvar_dialogo(self.db)
        embed = discord.Embed(
            title="✅ Aprendi!!",
            description=f"agora sei responder quando alguém falar **{gatilho}**!! 🐱🖤\nresposta: *{resposta}*",
            color=COR_VERDE
        )
        embed.set_footer(text="🐱 Lilu • aprendizado")
        await ctx.send(embed=embed)

    @commands.command(name="esquecer", aliases=["forget"])
    @commands.has_permissions(manage_messages=True)
    async def esquecer(self, ctx: commands.Context, gatilho: str):
        """
        Remove todas as respostas de um gatilho.
        Uso: l!esquecer <gatilho>
        """
        gatilho = gatilho.lower().strip()
        if gatilho in self.db["respostas"]:
            del self.db["respostas"][gatilho]
            _salvar_dialogo(self.db)
            await ctx.send(embed=discord.Embed(
                title="🗑️ Esqueci!!",
                description=f"não sei mais o que responder pra **{gatilho}**!! 🐱🖤",
                color=COR_VERMELHO
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="🤔 Não conheço esse gatilho!!",
                description=f"não tenho nenhuma resposta pra **{gatilho}**!! 🐱",
                color=COR_DOURADO
            ))

    @commands.command(name="gatilhos", aliases=["triggers"])
    @commands.has_permissions(manage_messages=True)
    async def listar_gatilhos(self, ctx: commands.Context):
        """Lista todos os gatilhos que a Lilu conhece."""
        chaves = sorted(self.db["respostas"].keys())
        if not chaves:
            await ctx.send("não conheço nenhum gatilho ainda!! me ensina com `l!ensinar`!! 🐱🖤")
            return
        # Pagina em chunks de 30
        chunks = [chaves[i:i+30] for i in range(0, len(chaves), 30)]
        for i, chunk in enumerate(chunks[:3]):   # máx 3 páginas
            embed = discord.Embed(
                title=f"📚 Gatilhos que Conheço — Página {i+1}/{len(chunks)}",
                description="\n".join(f"• `{c}` ({len(self.db['respostas'][c])} resp.)" for c in chunk),
                color=COR_ROXA,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="🐱 Lilu • aprendizado")
            await ctx.send(embed=embed)

    @commands.command(name="resposta")
    @commands.has_permissions(manage_messages=True)
    async def ver_resposta(self, ctx: commands.Context, *, gatilho: str):
        """Mostra todas as respostas de um gatilho. Uso: l!resposta <gatilho>"""
        gatilho = gatilho.lower().strip()
        resps = self.db["respostas"].get(gatilho)
        if not resps:
            await ctx.send(f"não conheço o gatilho **{gatilho}**!! 🐱🖤")
            return
        embed = discord.Embed(
            title=f"💬 Respostas para: {gatilho}",
            description="\n".join(f"`{i+1}.` {r}" for i, r in enumerate(resps)),
            color=COR_ROXA
        )
        embed.set_footer(text="🐱 Lilu • aprendizado")
        await ctx.send(embed=embed)

    @commands.command(name="simular")
    @commands.has_permissions(manage_messages=True)
    async def simular(self, ctx: commands.Context, *, texto: str):
        """Simula o que a Lilu responderia a um texto. Uso: l!simular <texto>"""
        chave = self._checar_gatilho(texto)
        if chave:
            resp = self._responder(chave)
            await ctx.send(
                embed=discord.Embed(
                    title="🧪 Simulação",
                    description=f"gatilho: `{chave}`\nresposta: *{resp}*",
                    color=COR_AZUL
                )
            )
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="🧪 Simulação",
                    description=f"não encontrei nenhum gatilho em `{texto[:100]}`!! 🤔🐱",
                    color=COR_DOURADO
                )
            )


# ══════════════════════════════════════════════════════════════════
#  🐱  EVENTOS GLOBAIS DO BOT
# ══════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"\n{'═'*52}")
    print(f"  🐱  LILU BOT — ONLINE")
    print(f"  Logado como: {bot.user} ({bot.user.id})")
    print(f"  Servidores: {len(bot.guilds)}")
    print(f"{'═'*52}\n")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="a galera com olhos de gatinha 🐱🖤"
        )
    )

    # Envia ficha de boot no canal de log de chat (se disponível)
    for guild in bot.guilds:
        ch = guild.get_channel(LOG_CHAT_ID)
        if ch:
            now = datetime.utcnow()
            embed = discord.Embed(
                description=(
                    "```\n"
                    "╔══════════════════════════════════════╗\n"
                    "║       🐱  LILU BOT  🖤               ║\n"
                    "║         — v1.0  ONLINE —             ║\n"
                    "║    Uma gatinha preta cheia de amor   ║\n"
                    "╚══════════════════════════════════════╝\n"
                    "```"
                ),
                color=COR_ROXA,
                timestamp=now
            )
            embed.set_author(name="LILU BOT • Sistemas Iniciados", icon_url=bot.user.display_avatar.url)
            embed.add_field(name="✅ Módulos Ativos", inline=False, value=(
                "🎙️ VoiceMaster — Calls Temporárias\n"
                "📋 Logs de Voz — entradas/saídas de call\n"
                "📝 Logs de Chat — msgs editadas/apagadas\n"
                "👋 Boas-Vindas — recepção de membros\n"
                "💬 Diálogo — aprendizado conversacional"
            ))
            embed.add_field(name="⚙️ Configuração", inline=False, value=(
                f"📞 Log Call: <#{LOG_CALL_ID}>\n"
                f"📝 Log Chat: <#{LOG_CHAT_ID}>\n"
                f"🤖 Prefixo: `l!` ou `lilu `"
            ))
            embed.set_footer(text="🐱 Lilu Bot • Todos os sistemas operacionais!!")
            await ch.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  📋  COMANDO DE AJUDA
# ══════════════════════════════════════════════════════════════════

@bot.command(name="help", aliases=["ajuda", "h"])
async def lilu_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🐱 Lilu Bot — Ajuda",
        description="oi!! eu sou a Lilu, uma gatinha preta!! aqui tá tudo que eu sei fazer!! 🖤",
        color=COR_ROXA,
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="🎙️ VoiceMaster (Calls)",
        inline=False,
        value=(
            "`l!vm setup [id_cat]` — configura o lobby de calls\n"
            "`l!vm reset [id_cat]` — recria o lobby\n"
            "`l!vm info` — mostra status do sistema\n"
            "*(use os botões do painel pra gerenciar sua call!!)*"
        )
    )
    embed.add_field(
        name="👋 Boas-Vindas",
        inline=False,
        value="`l!setwelcome #canal` — define canal de boas-vindas"
    )
    embed.add_field(
        name="💬 Diálogo & Aprendizado",
        inline=False,
        value=(
            "`l!ensinar <gatilho> <resposta>` — ensina nova resposta\n"
            "`l!esquecer <gatilho>` — remove respostas de um gatilho\n"
            "`l!gatilhos` — lista tudo que a Lilu sabe\n"
            "`l!resposta <gatilho>` — vê respostas de um gatilho\n"
            "`l!simular <texto>` — testa o que a Lilu responderia"
        )
    )
    embed.add_field(
        name="📋 Logs",
        inline=False,
        value=(
            f"Log de Voz → <#{LOG_CALL_ID}>\n"
            f"Log de Chat → <#{LOG_CHAT_ID}>\n"
            "*automático — sem comandos necessários!!*"
        )
    )
    embed.set_footer(text="🐱 Lilu Bot • prefixo: l! ou lilu ")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latencia = round(bot.latency * 1000)
    cor = COR_VERDE if latencia < 100 else (COR_DOURADO if latencia < 200 else COR_VERMELHO)
    await ctx.send(
        embed=discord.Embed(
            title="🏓 Pong!!",
            description=f"latência: `{latencia}ms` 🐱🖤",
            color=cor
        )
    )


@bot.command(name="lilu")
async def lilu_info(ctx: commands.Context):
    embed = discord.Embed(
        title="🖤 Oi!! Sou a Lilu!!",
        description=(
            "uma gatinha preta que adora cuidar do servidor!! 🐾✨\n\n"
            "gerencio calls, guardo logs, dou boas-vindas e aprendo a conversar com vocês aos poucos!! 🐱🖤\n\n"
            "use `l!help` pra ver tudo que sei fazer!!"
        ),
        color=COR_ROXA,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="🐱 Lilu Bot v1.0")
    await ctx.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  🚀  INICIALIZAÇÃO
# ══════════════════════════════════════════════════════════════════

async def _main():
    async with bot:
        await bot.add_cog(VoiceMasterCog(bot))
        await bot.add_cog(LogCog(bot))
        await bot.add_cog(WelcomeCog(bot))
        await bot.add_cog(DialogueCog(bot))

        # Registra views persistentes (sobrevivem a restarts)
        bot.add_view(VMPainelView(bot.cogs["LiluVoiceMaster"]))

        if not TOKEN:
            print("❌ ERRO: token não encontrado! Crie um .env com LILU_TOKEN=seu_token")
            return
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio as _asyncio
    _asyncio.run(_main())
